"""O Wayback Machine como arquivo de referência, por URL exata.

Descobrir é uma coisa (qualquer canal faz); ter uma cópia estável, datada, de cada
documento é outra. Para um documento que veio do GDELT, do Crossref ou de uma página de
tópico, este módulo pergunta ao CDX se o Wayback tem uma captura íntegra da URL e devolve
o endereço no modo `id_` (conteúdo arquivado sem a barra do Wayback). A consulta por URL
exata responde em menos de um segundo; a consulta por domínio inteiro é a que estoura.

`SavePageNow` (pedir ao Wayback que arquive uma URL viva ainda sem cópia) fica para uma
decisão da pesquisa: exige chave e tem cota própria. O ponto de extensão é `pedir()`.
"""

from __future__ import annotations

from urllib.parse import urlencode

from aletheia.http import Cliente, ErroColeta, Transporte, transporte_urllib
from aletheia.url import original_do_wayback

CDX = "https://web.archive.org/cdx/search/cdx"
ARQUIVO = "https://web.archive.org/web"


def snapshot(timestamp: str, original: str) -> str:
    return f"{ARQUIVO}/{timestamp}id_/{original}"


class Arquivo:
    """Resolve URLs para a captura mais recente íntegra no Wayback."""

    def __init__(
        self,
        cliente: Cliente | None = None,
        *,
        limite_por_minuto: int = 15,
        transporte: Transporte = transporte_urllib,
    ) -> None:
        self.cliente = cliente or Cliente(
            limite_por_minuto, respeita_robots=False, transporte=transporte, tempo_limite=60
        )

    def resolver(self, url: str) -> tuple[str, str] | None:
        """(timestamp, url do snapshot) da captura 200 mais recente, ou None."""
        original = original_do_wayback(url)
        params = [
            ("url", original),
            ("matchType", "exact"),
            ("filter", "statuscode:200"),
            ("output", "json"),
            ("fl", "timestamp,original"),
            ("limit", "-1"),  # a última captura
        ]
        try:
            linhas = self.cliente.requisitar(f"{CDX}?{urlencode(params)}").json() or []
        except ErroColeta:
            return None
        corpo = [linha for linha in linhas[1:] if linha]
        if not corpo:
            return None
        timestamp, achado = corpo[-1][0], corpo[-1][1]
        return timestamp, snapshot(timestamp, achado)

    def pedir(self, url: str) -> None:  # pragma: no cover - ponto de extensão
        """Pedir arquivamento (SavePageNow). Não implementado: decisão da pesquisa."""
        raise NotImplementedError("SavePageNow exige chave e política própria; ver docs/plano.md")
