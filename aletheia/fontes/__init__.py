"""Canais de descoberta. Um por origem, todos cumprindo `aletheia.contrato.Fonte`.

| tipo        | o que alcança                                              | estrato usual      |
|-------------|------------------------------------------------------------|--------------------|
| `wayback`   | URLs arquivadas com o termo no endereço, por prefixo × ano | qualquer           |
| `topico`    | a página de tag do veículo, viva e arquivada               | imprensa           |
| `gdelt`     | notícias pelo texto, últimos ~90 dias                      | imprensa           |
| `rss`       | o fluxo de um veículo ou repositório                       | imprensa, academico|
| `openalex`  | produção acadêmica indexada (título e resumo)              | academico          |
| `crossref`  | registro de DOIs (título e resumo)                         | academico          |
| `ia`        | coleção do Internet Archive (livros, vídeo, áudio, docs)   | memoria            |
| `wikipedia` | links externos dos verbetes: semente de URLs e de domínios | geral              |
| `lista`     | CSV curado à mão (Hemeroteca, acervos sem API)             | imprensa-historica |
"""

from __future__ import annotations

from aletheia.contrato import Fonte
from aletheia.fontes.crossref import Crossref
from aletheia.fontes.gdelt import Gdelt
from aletheia.fontes.ia import InternetArchive
from aletheia.fontes.lista import Lista
from aletheia.fontes.openalex import OpenAlex
from aletheia.fontes.rss import Rss
from aletheia.fontes.topico import Topico
from aletheia.fontes.wayback import Wayback
from aletheia.fontes.wikipedia import Wikipedia
from aletheia.http import Transporte, transporte_urllib

TIPOS = {
    "rss": Rss,
    "wayback": Wayback,
    "openalex": OpenAlex,
    "gdelt": Gdelt,
    "crossref": Crossref,
    "ia": InternetArchive,
    "topico": Topico,
    "wikipedia": Wikipedia,
    "lista": Lista,
}


def construir(cfg: dict, transporte: Transporte = transporte_urllib) -> Fonte:
    tipo = cfg.get("tipo")
    if tipo not in TIPOS:
        raise ValueError(f"tipo de fonte desconhecido: {tipo!r} (conhecidos: {sorted(TIPOS)})")
    if not cfg.get("id"):
        raise ValueError(f"fonte {tipo} sem id")
    return TIPOS[tipo].de_config(cfg, transporte)
