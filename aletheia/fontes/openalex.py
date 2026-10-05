"""OpenAlex: a produção acadêmica indexada (artigos, teses, livros, capítulos).

API: https://docs.openalex.org. Busca por texto em título, resumo e texto integral
indexado; paginação por cursor; até 200 por página.

**Chave.** Medido em 04/10/2026: sem chave, a cota diária é compartilhada por todo o IP
de saída e já vinha esgotada ("Insufficient budget"). Defina `OPENALEX_API_KEY` (a chave
é gratuita). O adaptador não envia e-mail nem outro dado de quem roda. A chave vai na
query string, que é o que a API aceita; o cliente HTTP a redige em toda mensagem de erro
e linha de log, para que nunca chegue ao relatório comitado.

**O que é texto aqui.** O integral de um trabalho acadêmico costuma estar num PDF atrás
de outro servidor. Este adaptador decide por **título e resumo**, e diz isso: o título é
o destaque (nível 3), e um termo só no resumo fica em "pede juízo". É uma exceção
consciente à regra de nunca decidir pelo resumo, aceitável para catalogar e
insuficiente para afirmar que o trabalho trata do tema.

Configuração:
    {"tipo": "openalex", "id": "openalex:carandiru", "busca": "carandiru",
     "por_pagina": 200, "limite_por_minuto": 30}
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

from aletheia.captura import montar_documento
from aletheia.contrato import Documento, Referencia
from aletheia.http import Cliente, Transporte, transporte_urllib

URL = "https://api.openalex.org/works"
CAMPOS = (
    "id,doi,display_name,publication_date,type,abstract_inverted_index,primary_location,open_access"
)


def resumo(invertido: dict | None) -> str:
    """O OpenAlex guarda o resumo como índice invertido (palavra -> posições)."""
    if not invertido:
        return ""
    posicoes = {p: palavra for palavra, lista in invertido.items() for p in lista}
    return " ".join(posicoes[p] for p in sorted(posicoes))


class OpenAlex:
    respeita_robots = False  # API própria

    def __init__(
        self,
        id: str,
        busca: str,
        cliente: Cliente,
        por_pagina: int = 200,
        limite_por_minuto: int = 30,
        chave: str | None = None,
    ) -> None:
        self.id = id
        self.busca = busca
        self.cliente = cliente
        self.por_pagina = por_pagina
        self.limite_por_minuto = limite_por_minuto
        self.chave = chave

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> OpenAlex:
        limite = int(cfg.get("limite_por_minuto", 30))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(
            cfg["id"],
            cfg["busca"],
            cliente,
            int(cfg.get("por_pagina", 200)),
            limite,
            os.environ.get("OPENALEX_API_KEY"),
        )

    def listar(self, desde: date) -> Iterator[Referencia]:
        cursor = "*"
        while cursor:
            params = {
                "search": self.busca,
                "filter": f"from_publication_date:{desde.isoformat()}",
                "per-page": self.por_pagina,
                "cursor": cursor,
                "select": CAMPOS,
            }
            if self.chave:
                params["api_key"] = self.chave
            dados = self.cliente.requisitar(URL, params=params).json()
            resultados = dados.get("results") or []
            for obra in resultados:
                yield self._referencia(obra)
            cursor = (dados.get("meta") or {}).get("next_cursor") if resultados else None

    def _referencia(self, obra: dict) -> Referencia:
        local = obra.get("primary_location") or {}
        acesso = obra.get("open_access") or {}
        url = obra.get("doi") or local.get("landing_page_url") or obra.get("id")
        publicado = obra.get("publication_date")
        return Referencia(
            fonte=self.id,
            id_na_fonte=str(obra.get("id")),
            url=url,
            titulo=obra.get("display_name"),
            publicado_em=date.fromisoformat(publicado) if publicado else None,
            dados={
                "titulo": obra.get("display_name") or "",
                "resumo": resumo(obra.get("abstract_inverted_index")),
                "tipo": obra.get("type") or "",
                "veiculo": ((local.get("source") or {}).get("display_name")) or "",
                "acesso_aberto": acesso.get("oa_url") or "",
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
