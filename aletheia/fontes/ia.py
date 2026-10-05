"""Internet Archive, a coleção (não o Wayback): livros, vídeos, áudios e documentos
depositados por usuários e instituições, com busca em texto integral.

API: https://archive.org/advancedsearch.php (Lucene). Medido em 05/10/2026:
`q=carandiru` responde sem chave. O item é a página `archive.org/details/<id>`; o
adaptador decide por título e descrição (o integral pode ser um vídeo ou um PDF de
centenas de páginas) e deixa o nível 3 para o termo no título.

Configuração:
    {"tipo": "ia", "id": "ia:carandiru", "busca": "carandiru", "por_pagina": 100,
     "limite_por_minuto": 20, "estrato": "memoria"}
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from aletheia.captura import montar_documento
from aletheia.contrato import Documento, Referencia
from aletheia.http import Cliente, Transporte, transporte_urllib

URL = "https://archive.org/advancedsearch.php"
DETALHES = "https://archive.org/details"
CAMPOS = ("identifier", "title", "description", "date", "mediatype", "publicdate")


def _data(texto: str | list | None) -> date | None:
    if isinstance(texto, list):
        texto = texto[0] if texto else None
    try:
        return date.fromisoformat(str(texto)[:10]) if texto else None
    except ValueError:
        return None


def _texto(valor) -> str:
    if isinstance(valor, list):
        return " ".join(str(v) for v in valor if v)
    return str(valor or "")


class InternetArchive:
    respeita_robots = False  # API própria

    def __init__(
        self,
        id: str,
        busca: str,
        cliente: Cliente,
        por_pagina: int = 100,
        limite_por_minuto: int = 20,
    ) -> None:
        self.id = id
        self.busca = busca
        self.cliente = cliente
        self.por_pagina = por_pagina
        self.limite_por_minuto = limite_por_minuto

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> InternetArchive:
        limite = int(cfg.get("limite_por_minuto", 20))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(cfg["id"], cfg["busca"], cliente, int(cfg.get("por_pagina", 100)), limite)

    def listar(self, desde: date) -> Iterator[Referencia]:
        pagina = 1
        while True:
            params = [
                ("q", f"({self.busca}) AND publicdate:[{desde.isoformat()} TO null]"),
                *[("fl[]", campo) for campo in CAMPOS],
                ("sort[]", "publicdate asc"),
                ("rows", str(self.por_pagina)),
                ("page", str(pagina)),
                ("output", "json"),
            ]
            resposta = self.cliente.requisitar(URL, params=params).json()
            docs = (resposta.get("response") or {}).get("docs") or []
            for doc in docs:
                if doc.get("identifier"):
                    yield self._referencia(doc)
            if len(docs) < self.por_pagina:
                return
            pagina += 1

    def _referencia(self, doc: dict) -> Referencia:
        ident = doc["identifier"]
        titulo = _texto(doc.get("title")).strip() or None
        return Referencia(
            fonte=self.id,
            id_na_fonte=ident,
            url=f"{DETALHES}/{ident}",
            titulo=titulo,
            publicado_em=_data(doc.get("publicdate")) or _data(doc.get("date")),
            dados={
                "titulo": titulo or "",
                "descricao": _texto(doc.get("description")),
                "tipo": _texto(doc.get("mediatype")),
                "data_original": _texto(doc.get("date")),
            },
        )

    def baixar(self, ref: Referencia) -> Documento:
        d = dict(ref.dados or {})
        texto = "\n\n".join(
            p
            for p in (
                d.get("titulo"),
                d.get("descricao"),
                f"Tipo: {d.get('tipo')}" if d.get("tipo") else "",
            )
            if p
        )
        return montar_documento(ref, texto, destaques={"titulo": d.get("titulo") or ""})

    def sentinela(self, doc: Documento) -> bool:
        return bool((doc.ref.dados or {}).get("titulo"))
