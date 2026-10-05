"""A configuração do observatório: qual léxico, quais fontes, onde gravar.

    {
      "lexico": "lexico.json",
      "diretorio": ".",
      "desde": "1996-01-01",
      "margem_dias": 7,
      "guardar_texto": false,
      "catalogo": {"arquivo": "catalogo.csv", "nivel_minimo": 3},
      "vistas": {"arquivo": "vistas.csv", "nivel_minimo": 2},
      "arquivo": {"resolver": true, "limite_por_minuto": 15},
      "fontes": [{"tipo": "wayback", "id": "wayback:ponte", "prefixos": ["ponte.org/"],
                  "estrato": "imprensa"}]
    }

Caminhos relativos são resolvidos a partir do arquivo de configuração. Em `diretorio`
moram `estado/`, `corpus/`, `saidas/`, o catálogo e as vistas.

`estrato` é obrigatório para a estimativa fazer sentido: captura e recaptura só compara
canais que olham para a mesma população. `validar()` recusa estrato fora da lista.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ESTRATOS = ("imprensa", "imprensa-historica", "academico", "juridico", "memoria", "geral")


@dataclass(frozen=True)
class Config:
    lexico: Path
    diretorio: Path
    fontes: tuple[dict, ...]
    desde: date | None = None
    # Quanto voltar antes da última rodada: fonte que publica com atraso ou com data
    # retroativa não escapa. O estado impede a releitura do que já foi visto.
    margem_dias: int = 2
    # False: o texto integral é lido, triado e descartado; nada vai para `corpus/`.
    guardar_texto: bool = True
    # {"arquivo": "catalogo.csv", "nivel_minimo": 3}: o catálogo CSV cumulativo.
    catalogo: dict | None = None
    # {"arquivo": "vistas.csv", "nivel_minimo": 2}: a matriz documento × canal × rodada.
    vistas: dict | None = None
    # {"resolver": true, "limite_por_minuto": 15}: procurar no Wayback a cópia de
    # referência dos itens que vieram de outros canais.
    arquivo: dict | None = None

    @property
    def catalogo_csv(self) -> Path | None:
        if not self.catalogo:
            return None
        return self.diretorio / self.catalogo.get("arquivo", "catalogo.csv")

    @property
    def catalogo_nivel(self) -> int:
        return int((self.catalogo or {}).get("nivel_minimo", 3))

    @property
    def vistas_csv(self) -> Path | None:
        if self.vistas is None:
            return None
        return self.diretorio / self.vistas.get("arquivo", "vistas.csv")

    @property
    def vistas_nivel(self) -> int:
        return int((self.vistas or {}).get("nivel_minimo", 2))

    @property
    def resolver_arquivo(self) -> bool:
        return bool((self.arquivo or {}).get("resolver", False))

    @property
    def estado(self) -> Path:
        return self.diretorio / "estado"

    @property
    def corpus(self) -> Path:
        return self.diretorio / "corpus"

    @property
    def saidas(self) -> Path:
        return self.diretorio / "saidas"

    def estrato_de(self, fonte: str) -> str:
        for f in self.fontes:
            if f.get("id") == fonte:
                return f.get("estrato", "geral")
        return "geral"


def validar(dados: dict) -> list[str]:
    """Problemas de forma e de método; vazia quando a configuração está sã."""
    problemas: list[str] = []
    if not isinstance(dados, dict):
        return ["a raiz precisa ser um objeto"]
    if not dados.get("lexico"):
        problemas.append("lexico: obrigatório")
    fontes = dados.get("fontes") or []
    if not fontes:
        problemas.append("fontes: nenhuma fonte configurada")
    ids = [f.get("id") for f in fontes]
    if len(set(ids)) != len(ids):
        problemas.append("fontes: ids repetidos")
    for f in fontes:
        onde = f"fontes[{f.get('id') or '?'}]"
        if not f.get("id"):
            problemas.append(f"{onde}: sem id")
        if not f.get("tipo"):
            problemas.append(f"{onde}: sem tipo")
        estrato = f.get("estrato")
        if estrato is None:
            problemas.append(f"{onde}: sem estrato (um de {', '.join(ESTRATOS)})")
        elif estrato not in ESTRATOS:
            problemas.append(f"{onde}: estrato desconhecido {estrato!r}")
        if ":" in (f.get("id") or "") and f["id"].split(":", 1)[0] != f.get("tipo"):
            problemas.append(
                f"{onde}: o prefixo do id ({f['id'].split(':', 1)[0]}) precisa ser o tipo "
                f"({f.get('tipo')}): é por ele que a estimativa agrupa os canais"
            )
    for chave in ("catalogo", "vistas"):
        bloco = dados.get(chave)
        if bloco is not None:
            nivel = bloco.get("nivel_minimo", 3 if chave == "catalogo" else 2)
            if not isinstance(nivel, int) or not 0 <= nivel <= 3:
                problemas.append(f"{chave}.nivel_minimo: inteiro de 0 a 3")
    cat = (dados.get("catalogo") or {}).get("nivel_minimo", 3)
    vis = (dados.get("vistas") or {}).get("nivel_minimo", 2)
    if isinstance(cat, int) and isinstance(vis, int) and vis > cat:
        problemas.append("vistas.nivel_minimo não pode ser maior que catalogo.nivel_minimo")
    if dados.get("desde"):
        try:
            date.fromisoformat(dados["desde"])
        except ValueError:
            problemas.append("desde: use AAAA-MM-DD")
    return problemas


def carregar(caminho: str | Path) -> Config:
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    base = caminho.parent
    fontes = dados.get("fontes") or []
    if not fontes:
        raise ValueError(f"{caminho}: nenhuma fonte configurada")
    ids = [f.get("id") for f in fontes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{caminho}: ids de fonte repetidos")
    return Config(
        lexico=(base / dados["lexico"]).resolve(),
        diretorio=(base / dados.get("diretorio", "dados")).resolve(),
        fontes=tuple(fontes),
        desde=date.fromisoformat(dados["desde"]) if dados.get("desde") else None,
        margem_dias=int(dados.get("margem_dias", 2)),
        guardar_texto=bool(dados.get("guardar_texto", True)),
        catalogo=dados.get("catalogo"),
        vistas=dados.get("vistas"),
        arquivo=dados.get("arquivo"),
    )
