"""Quanto falta: estimativa do total a partir da sobreposição entre canais.

É a técnica de captura e recaptura, a mesma de contar peixes num lago. Se o canal A acha
`n1` documentos, o B acha `n2` e `m` estão nos dois, o total estimado é ~ `n1 · n2 / m`.
Aqui se usa a forma de Chapman, que não explode quando `m` é pequeno, e, para três canais
ou mais, o estimador de Chao, que usa quantos documentos foram vistos por um canal só
(`f1`) e por exatamente dois (`f2`) e é um **piso** robusto à heterogeneidade (página
popular é mais fácil de achar que página obscura).

Regras que o código impõe:

- **Canal é o prefixo do id da fonte** (`wayback:folha` e `wayback:estadao` são o mesmo
  canal, `wayback`). Domínios do Wayback não se sobrepõem; tratados como canais
  separados, quase todo documento seria "visto por um canal só" e a estimativa explodiria.
- **Só se comparam canais do mesmo estrato.** Cada fonte declara `"estrato"` na
  configuração, e o relatório sai por estrato.
- **A unidade é o documento**, não a URL: o `id` é da URL normalizada e, quando duas URLs
  servem o mesmo texto (`hash_texto` igual), contam uma vez.
- **Janela**: o GDELT só guarda ~90 dias. Par com canal de janela curta só é comparável
  quando `--desde` restringe os dois à mesma janela; fora disso, o relatório mostra o par
  marcado como **não comparável** em vez de um número sem sentido.

As ressalvas vão no relatório porque são parte do número: os canais não são
independentes (todos favorecem o que é popular), e dependência positiva faz a estimativa
ficar **abaixo** do real. Leia como piso. A curva de acumulação (quantos documentos novos
cada rodada trouxe) diz se a busca está saturando, coisa que nenhum estimador diz sozinho.

Entrada: `vistas.csv` (uma linha por observação: documento, canal, fonte, rodada, nível).
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from pathlib import Path

from aletheia.url import normalizar as normalizar_url  # noqa: F401  (reexportado)

# Canais cuja listagem só alcança uma janela curta; comparação sem `--desde` não vale.
JANELA_CURTA = {"gdelt"}


@dataclass
class Par:
    a: str
    b: str
    n1: int
    n2: int
    m: int
    comparavel: bool = True

    @property
    def chapman(self) -> float:
        return (self.n1 + 1) * (self.n2 + 1) / (self.m + 1) - 1

    @property
    def intervalo(self) -> tuple[float, float]:
        n1, n2, m = self.n1, self.n2, self.m
        var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
        dp = math.sqrt(var)
        return max(self.n1 + self.n2 - self.m, self.chapman - 1.96 * dp), self.chapman + 1.96 * dp


@dataclass
class Estimativa:
    por_canal: dict[str, set[str]]
    curva: list[tuple[str, int, int]] = field(default_factory=list)  # rodada, novas, total
    alinhado: bool = False  # True quando `desde` restringiu todos os canais à mesma janela

    @property
    def observadas(self) -> set[str]:
        return set().union(*self.por_canal.values()) if self.por_canal else set()

    @property
    def frequencias(self) -> Counter:
        """Quantos documentos foram vistos por exatamente k canais."""
        contagem = Counter(u for urls in self.por_canal.values() for u in urls)
        return Counter(contagem.values())

    @property
    def canais_comparaveis(self) -> list[str]:
        return [c for c in sorted(self.por_canal) if self.alinhado or c not in JANELA_CURTA]

    @property
    def chao(self) -> float | None:
        canais = self.canais_comparaveis
        if len(canais) < 2:
            return None
        contagem = Counter(u for c in canais for u in self.por_canal[c])
        s = len(contagem)
        f = Counter(contagem.values())
        f1, f2 = f.get(1, 0), f.get(2, 0)
        return s + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)

    @property
    def pares(self) -> list[Par]:
        return [
            Par(a, b, len(self.por_canal[a]), len(self.por_canal[b]),
                len(self.por_canal[a] & self.por_canal[b]),
                comparavel=self.alinhado or not ({a, b} & JANELA_CURTA))
            for a, b in combinations(sorted(self.por_canal), 2)
        ]  # fmt: skip


def canal(fonte: str) -> str:
    return fonte.split(":", 1)[0]


def calcular(
    vistas: Path,
    nivel_minimo: int = 2,
    estrato_de: Callable[[str], str] = lambda fonte: "geral",
    desde: date | None = None,
) -> dict[str, Estimativa]:
    """Uma estimativa por estrato, a partir de `vistas.csv`. `estrato_de` recebe o id da fonte."""
    por_estrato: dict[str, Estimativa] = {}
    vistas = Path(vistas)
    if not vistas.exists():
        return por_estrato
    with vistas.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    # Documento = hash do texto quando há; senão, o id da URL normalizada.
    unidade = {linha["id"]: (linha.get("hash_texto") or linha["id"]) for linha in linhas}
    por_rodada: dict[str, list[dict]] = {}
    for linha in linhas:
        por_rodada.setdefault(linha["rodada"], []).append(linha)
    acumulado: dict[str, set[str]] = {}
    for rodada in sorted(por_rodada):
        antes = {e: len(v) for e, v in acumulado.items()}
        for linha in por_rodada[rodada]:
            try:
                nivel = int(linha.get("nivel") or 0)
            except ValueError:
                nivel = 0
            if nivel < nivel_minimo:
                continue
            publicado = linha.get("publicado_em") or ""
            if desde and (not publicado or date.fromisoformat(publicado) < desde):
                continue
            estrato = estrato_de(linha["fonte"])
            est = por_estrato.setdefault(estrato, Estimativa({}, alinhado=desde is not None))
            doc = unidade[linha["id"]]
            est.por_canal.setdefault(canal(linha["fonte"]), set()).add(doc)
            acumulado.setdefault(estrato, set()).add(doc)
        for estrato, docs in acumulado.items():
            novas = len(docs) - antes.get(estrato, 0)
            if novas or estrato in por_estrato:
                por_estrato[estrato].curva.append((rodada, novas, len(docs)))
    return por_estrato


def relatorio(estratos: dict[str, Estimativa], desde: date | None = None) -> str:
    linhas = ["# Estimativa de cobertura", ""]
    if desde:
        linhas += [f"Só itens publicados ou capturados a partir de {desde.isoformat()}.", ""]
    if not estratos:
        return "\n".join([*linhas, "Nenhuma rodada com itens triados ainda."]) + "\n"
    for nome, est in sorted(estratos.items()):
        linhas += _estrato(nome, est)
    linhas += [
        "",
        "## Como ler",
        "",
        "Os canais não são independentes, e a dependência puxa a estimativa para baixo: os "
        "números acima são piso. Saturação de verdade é a curva achatar com canais novos "
        "entrando, não só com os mesmos canais repetindo. Par marcado como não comparável "
        "junta um canal de janela curta (GDELT, ~90 dias) com um de janela longa sem "
        "`--desde`: o número sairia enorme e não diria nada.",
    ]
    return "\n".join(linhas) + "\n"


def _estrato(nome: str, est: Estimativa) -> list[str]:
    total = len(est.observadas)
    linhas = [f"## Estrato `{nome}`", "", f"Documentos distintos observados: **{total}**.", ""]

    linhas += ["| Canal | Documentos | Só neste canal |", "|---|---|---|"]
    contagem = Counter(u for urls in est.por_canal.values() for u in urls)
    for canal, urls in sorted(est.por_canal.items()):
        exclusivas = sum(1 for u in urls if contagem[u] == 1)
        marca = "" if canal in est.canais_comparaveis else " (janela curta; fora do piso)"
        linhas.append(f"| `{canal}`{marca} | {len(urls)} | {exclusivas} |")

    if est.chao is not None:
        comparaveis = est.canais_comparaveis
        contagem_c = Counter(u for c in comparaveis for u in est.por_canal[c])
        f = Counter(contagem_c.values())
        observadas_c = len(contagem_c)
        linhas += [
            "",
            "**Total estimado**",
            "",
            f"- **Chao (piso, {len(comparaveis)} canais comparáveis):** {est.chao:,.0f} "
            f"(vistos por um canal só: {f.get(1, 0)}; por exatamente dois: {f.get(2, 0)}).",
            f"- **Cobertura:** no máximo {observadas_c / est.chao:.0%} (observados ÷ piso)."
            if est.chao
            else "",
            "",
            "| Par | n1 | n2 | em comum | Chapman | IC 95% |",
            "|---|---|---|---|---|---|",
        ]
        for p in est.pares:
            if not p.comparavel:
                linhas.append(
                    f"| `{p.a}` × `{p.b}` | {p.n1} | {p.n2} | {p.m} | não comparável | "
                    "use `--desde` |"
                )
                continue
            baixo, alto = p.intervalo
            linhas.append(
                f"| `{p.a}` × `{p.b}` | {p.n1} | {p.n2} | {p.m} | {p.chapman:,.0f} | "
                f"{baixo:,.0f} a {alto:,.0f} |"
            )
        linhas += [
            "",
            "Par sem nada em comum dá estimativa enorme e instável: não diz que o total é "
            "enorme, diz que os dois canais olham para lugares diferentes.",
        ]
    else:
        linhas += [
            "",
            "Com um canal comparável só não há estimativa: é preciso ao menos dois "
            "(canal de janela curta só conta com `--desde`).",
        ]

    linhas += ["", "**Curva de acumulação**", "", "| Rodada | Novos | Total |", "|---|---|---|"]
    linhas += [f"| {r} | {novas} | {acum} |" for r, novas, acum in est.curva]
    return [*linhas, ""]
