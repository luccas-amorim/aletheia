"""O léxico como dado: carregar, validar e casar contra o texto.

Nenhum termo mora em código. O formato está em `lexico.schema.json`, na raiz; a validação
abaixo aplica as mesmas regras sem depender de biblioteca de JSON Schema, e o teste
`test_schema_e_validador_concordam` impede que os dois divirjam em silêncio.

O casamento é por palavra inteira, sem distinguir maiúsculas nem acentos, e tolera
quebra de linha ou espaço duplo onde a forma tem um espaço ("art.  121" casa "art. 121").
Uma ocorrência que cai dentro de uma exclusão do mesmo termo não conta.

Reticências (`…`, um caractere só) numa forma valem até 60 caracteres quaisquer, sem
atravessar ponto e vírgula nem quebra de linha (o ponto atravessa, por causa de
"inc."). Assim "art. 121 … Código Penal" casa "art. 121, § 2º, IV, do Código Penal",
que é como a jurisprudência cita. As exclusões aceitam o mesmo:
"art. 121 … Código Penal Militar" anula a ocorrência que, na verdade, é do CPM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from aletheia.texto import dobrar


class ErroLexico(ValueError):
    def __init__(self, problemas: list[str]) -> None:
        super().__init__("léxico inválido:\n  - " + "\n  - ".join(problemas))
        self.problemas = problemas


@dataclass(frozen=True)
class Termo:
    chave: str
    formas: tuple[str, ...]
    exclusoes: tuple[str, ...] = ()
    peso: float = 1.0
    categorias: tuple[str, ...] = ()
    nota: str | None = None


@dataclass(frozen=True)
class Lexico:
    id: str
    versao: str
    termos: tuple[Termo, ...]
    contexto: tuple[str, ...] = ()  # basta um destes no texto
    descricao: str | None = None


@dataclass(frozen=True)
class Ocorrencia:
    chave: str
    inicio: int
    fim: int


_CHAVES_RAIZ = {"id", "versao", "descricao", "termos", "contexto"}
_CHAVES_TERMO = {"chave", "formas", "exclusoes", "peso", "categorias", "nota"}
_CHAVES_CONTEXTO = {"exige_qualquer", "nota"}


def _lista_de_textos(valor, onde: str, problemas: list[str], minimo: int = 0) -> None:
    if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
        problemas.append(f"{onde}: precisa ser lista de textos não vazios")
    elif len(valor) < minimo:
        problemas.append(f"{onde}: precisa de ao menos {minimo} item")


def validar(dados) -> list[str]:
    """Lista de problemas; vazia quando o léxico é válido."""
    if not isinstance(dados, dict):
        return ["a raiz precisa ser um objeto"]
    problemas: list[str] = []
    for chave in sorted(set(dados) - _CHAVES_RAIZ):
        problemas.append(f"campo desconhecido na raiz: {chave}")
    for chave in ("id", "versao"):
        if not isinstance(dados.get(chave), str) or not dados.get(chave, "").strip():
            problemas.append(f"{chave}: obrigatório, texto não vazio")
    if "descricao" in dados and not isinstance(dados["descricao"], str):
        problemas.append("descricao: precisa ser texto")

    termos = dados.get("termos")
    if not isinstance(termos, list) or not termos:
        problemas.append("termos: obrigatório, lista com ao menos um termo")
        termos = []
    vistas: set[str] = set()
    for i, termo in enumerate(termos):
        onde = f"termos[{i}]"
        if not isinstance(termo, dict):
            problemas.append(f"{onde}: precisa ser objeto")
            continue
        for chave in sorted(set(termo) - _CHAVES_TERMO):
            problemas.append(f"{onde}: campo desconhecido: {chave}")
        chave = termo.get("chave")
        if not isinstance(chave, str) or not chave.strip():
            problemas.append(f"{onde}.chave: obrigatório, texto não vazio")
        elif chave in vistas:
            problemas.append(f"{onde}.chave: repetida ({chave})")
        else:
            vistas.add(chave)
            onde = f"termos[{chave}]"
        _lista_de_textos(termo.get("formas"), f"{onde}.formas", problemas, minimo=1)
        for opcional in ("exclusoes", "categorias"):
            if opcional in termo:
                _lista_de_textos(termo[opcional], f"{onde}.{opcional}", problemas)
        peso = termo.get("peso", 1.0)
        if isinstance(peso, bool) or not isinstance(peso, int | float) or peso <= 0:
            problemas.append(f"{onde}.peso: precisa ser número positivo")
        if "nota" in termo and not isinstance(termo["nota"], str):
            problemas.append(f"{onde}.nota: precisa ser texto")

    contexto = dados.get("contexto")
    if contexto is not None:
        if not isinstance(contexto, dict):
            problemas.append("contexto: precisa ser objeto")
        else:
            for chave in sorted(set(contexto) - _CHAVES_CONTEXTO):
                problemas.append(f"contexto: campo desconhecido: {chave}")
            _lista_de_textos(
                contexto.get("exige_qualquer"), "contexto.exige_qualquer", problemas, 1
            )
    return problemas


def de_dados(dados: dict) -> Lexico:
    problemas = validar(dados)
    if problemas:
        raise ErroLexico(problemas)
    termos = tuple(
        Termo(
            chave=t["chave"],
            formas=tuple(t["formas"]),
            exclusoes=tuple(t.get("exclusoes", ())),
            peso=float(t.get("peso", 1.0)),
            categorias=tuple(t.get("categorias", ())),
            nota=t.get("nota"),
        )
        for t in dados["termos"]
    )
    contexto = tuple((dados.get("contexto") or {}).get("exige_qualquer", ()))
    return Lexico(dados["id"], dados["versao"], termos, contexto, dados.get("descricao"))


def carregar(caminho: str | Path) -> Lexico:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ErroLexico([f"JSON inválido: {erro}"]) from erro
    return de_dados(dados)


# "…" numa forma: até este tanto de qualquer coisa entre as partes. É o que deixa
# "art. 121 … Código Penal" casar "art. 121, § 2º, IV, do Código Penal".
RETICENCIAS = "…"
JANELA_RETICENCIAS = 60


def _trecho(parte: str) -> str:
    return r"\s+".join(map(re.escape, parte.split()))


def _forma(forma: str) -> str:
    partes = [p.strip() for p in dobrar(forma.strip()).split(RETICENCIAS)]
    # Cada parte fecha e abre em fronteira de palavra: "art. 121 … CP" não casa "art. 1210".
    lacuna = rf"(?!\w)[^;\n]{{0,{JANELA_RETICENCIAS}}}?(?<!\w)"
    return lacuna.join(_trecho(p) for p in partes if p)


def _padrao(formas: tuple[str, ...]) -> re.Pattern[str] | None:
    if not formas:
        return None
    # Mais longa primeiro: "art. 121 do Código Penal" ganha de "art. 121" na mesma posição.
    partes = sorted({f.strip() for f in formas}, key=len, reverse=True)
    alternativas = "|".join(_forma(p) for p in partes)
    return re.compile(rf"(?<!\w)(?:{alternativas})(?!\w)")


class Casador:
    """O léxico compilado. Opera sobre texto já dobrado (ver `texto.dobrar`)."""

    def __init__(self, lexico: Lexico) -> None:
        self.lexico = lexico
        self._termos = [(t, _padrao(t.formas), _padrao(t.exclusoes)) for t in lexico.termos]
        self._contexto = _padrao(lexico.contexto)

    def ocorrencias(self, dobrado: str) -> tuple[list[Ocorrencia], list[Ocorrencia]]:
        """(ocorrências válidas, ocorrências anuladas por exclusão)."""
        validas: list[Ocorrencia] = []
        anuladas: list[Ocorrencia] = []
        for termo, padrao, exclusao in self._termos:
            faixas = [m.span() for m in exclusao.finditer(dobrado)] if exclusao else []
            for m in padrao.finditer(dobrado):
                oc = Ocorrencia(termo.chave, m.start(), m.end())
                dentro = any(a <= oc.inicio and oc.fim <= b for a, b in faixas)
                (anuladas if dentro else validas).append(oc)
        validas.sort(key=lambda o: o.inicio)
        return validas, anuladas

    def contexto(self, dobrado: str) -> re.Match[str] | None | bool:
        """O primeiro marcador de contexto, ou True quando o léxico não exige contexto."""
        if self._contexto is None:
            return True
        return self._contexto.search(dobrado)

    def termo(self, chave: str) -> Termo:
        return next(t for t in self.lexico.termos if t.chave == chave)
