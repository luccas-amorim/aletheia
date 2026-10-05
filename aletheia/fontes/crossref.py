"""Crossref: o registro de DOIs, aberto e sem chave. Segundo canal acadêmico.

API: https://api.crossref.org/swagger-ui/index.html. Busca por texto nos metadados
(título, resumo quando depositado, autores), paginação por cursor, até 1.000 por página.
Medido em 05/10/2026: `works?query=carandiru` devolveu 72 trabalhos sem chave.

Como no OpenAlex, o adaptador decide por **título e resumo** (o integral está num PDF
atrás de outro servidor): o título é destaque (nível 3); termo só no resumo fica em
"pede juízo". Com dois canais acadêmicos, o estrato ganha estimativa.

O "polite pool" do Crossref pede um `mailto`; é opcional e, se usado, vem da variável de
ambiente `CROSSREF_MAILTO`. O cliente HTTP redige esse parâmetro em erros e logs.

Configuração:
    {"tipo": "crossref", "id": "crossref:carandiru", "busca": "carandiru",
     "por_pagina": 200, "limite_por_minuto": 30, "estrato": "academico"}
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import date

from aletheia.captura import montar_documento
from aletheia.contrato import Documento, Referencia
from aletheia.http import Cliente, Transporte, transporte_urllib

URL = "https://api.crossref.org/works"
CAMPOS = "DOI,title,abstract,issued,URL,container-title,type"
_TAGS = re.compile(r"<[^>]+>")


def _data(issued: dict | None) -> date | None:
    partes = ((issued or {}).get("date-parts") or [[None]])[0] or [None]
    ano = partes[0]
    if not ano:
        return None
    mes = partes[1] if len(partes) > 1 and partes[1] else 1
    dia = partes[2] if len(partes) > 2 and partes[2] else 1
    try:
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        return None


def limpar_resumo(texto: str | None) -> str:
    """O resumo vem em JATS XML (`<jats:p>`); fica só o texto."""
    return " ".join(_TAGS.sub(" ", texto or "").split())


class Crossref:
    respeita_robots = False  # API própria

    def __init__(
        self,
        id: str,
        busca: str,
        cliente: Cliente,
        por_pagina: int = 200,
        limite_por_minuto: int = 30,
        mailto: str | None = None,
    ) -> None:
        self.id = id
        self.busca = busca
        self.cliente = cliente
        self.por_pagina = por_pagina
        self.limite_por_minuto = limite_por_minuto
        self.mailto = mailto

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Crossref:
        limite = int(cfg.get("limite_por_minuto", 30))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(
            cfg["id"], cfg["busca"], cliente, int(cfg.get("por_pagina", 200)), limite,
            os.environ.get("CROSSREF_MAILTO") or None,
        )  # fmt: skip

    def listar(self, desde: date) -> Iterator[Referencia]:
        cursor = "*"
        while cursor:
            params = {
                "query": self.busca,
                "filter": f"from-pub-date:{desde.isoformat()}",
                "rows": self.por_pagina,
                "cursor": cursor,
                "select": CAMPOS,
            }
            if self.mailto:
                params["mailto"] = self.mailto
            mensagem = self.cliente.requisitar(URL, params=params).json().get("message") or {}
            itens = mensagem.get("items") or []
            for obra in itens:
                ref = self._referencia(obra)
                if ref is not None:
                    yield ref
            cursor = mensagem.get("next-cursor") if itens else None

    def _referencia(self, obra: dict) -> Referencia | None:
        doi = obra.get("DOI")
        if not doi:
            return None
        titulo = " ".join(obra.get("title") or []).strip() or None
        return Referencia(
            fonte=self.id,
            id_na_fonte=doi.lower(),
            url=f"https://doi.org/{doi}",
            titulo=titulo,
            publicado_em=_data(obra.get("issued")),
            dados={
                "titulo": titulo or "",
                "resumo": limpar_resumo(obra.get("abstract")),
                "tipo": obra.get("type") or "",
                "veiculo": " ".join(obra.get("container-title") or []),
                "pagina": obra.get("URL") or "",
            },
        )

    def baixar(self, ref: Referencia) -> Documento:
        """Sem rede: título, resumo, tipo e veículo vieram na listagem."""
        d = dict(ref.dados or {})
        texto = "\n\n".join(
            p
            for p in (
                d.get("titulo"),
                d.get("resumo"),
                f"Tipo: {d.get('tipo')}" if d.get("tipo") else "",
                f"Veículo: {d.get('veiculo')}" if d.get("veiculo") else "",
            )
            if p
        )
        return montar_documento(ref, texto, destaques={"titulo": d.get("titulo") or ""})

    def sentinela(self, doc: Documento) -> bool:
        return bool((doc.ref.dados or {}).get("titulo"))
