"""Wikipédia: os links externos dos verbetes, em várias línguas. Semente, não acervo.

Os editores já reuniram as referências que sustentam cada verbete sobre o massacre. O
adaptador lista esses links (API do MediaWiki, `prop=extlinks`) e os entrega como
referências a baixar. Em 05/10/2026 o verbete em português tinha 50 links em 23
domínios, vários fora da lista de veículos do observatório: é também a melhor fonte de
**domínios candidatos** para novas fontes `wayback` e `topico`.

A API é interface própria (sem `robots.txt`); as páginas de destino são baixadas com o
`robots.txt` de cada origem respeitado.

Configuração:
    {"tipo": "wikipedia", "id": "wikipedia:pt", "idioma": "pt",
     "titulos": ["Massacre_do_Carandiru"], "limite_por_minuto": 30, "estrato": "geral"}
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from urllib.parse import urlsplit

from aletheia.contrato import Documento, Referencia
from aletheia.fontes.rss import documento_html, pagina_integra
from aletheia.http import Cliente, Transporte, transporte_urllib
from aletheia.url import normalizar

_WAYBACK_HOST = "web.archive.org"


class Wikipedia:
    respeita_robots = True  # vale para as páginas de destino

    def __init__(
        self,
        id: str,
        idioma: str,
        titulos: list[str],
        api: Cliente,
        paginas: Cliente,
        limite_por_minuto: int = 30,
        minimo_caracteres: int = 400,
    ) -> None:
        self.id = id
        self.idioma = idioma
        self.titulos = titulos
        self.api = api
        self.paginas = paginas
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres

    @property
    def url_api(self) -> str:
        return f"https://{self.idioma}.wikipedia.org/w/api.php"

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Wikipedia:
        limite = int(cfg.get("limite_por_minuto", 30))
        api = Cliente(limite, respeita_robots=False, transporte=transporte)
        paginas = Cliente(limite, respeita_robots=True, transporte=transporte)
        return cls(
            cfg["id"], cfg.get("idioma", "pt"), list(cfg["titulos"]), api, paginas, limite,
            int(cfg.get("minimo_caracteres", 400)),
        )  # fmt: skip

    def listar(self, desde: date) -> Iterator[Referencia]:
        vistos: set[str] = set()
        for titulo in self.titulos:
            continuar: dict[str, str] = {}
            while True:
                params = {
                    "action": "query",
                    "prop": "extlinks",
                    "titles": titulo,
                    "ellimit": "500",
                    "format": "json",
                    "formatversion": "2",
                    **continuar,
                }
                dados = self.api.requisitar(self.url_api, params=params).json()
                for pagina in (dados.get("query") or {}).get("pages") or []:
                    for link in pagina.get("extlinks") or []:
                        url = link.get("url") or link.get("*") or ""
                        if not url.startswith(("http://", "https://")):
                            continue
                        chave = normalizar(url)
                        if chave in vistos:
                            continue
                        vistos.add(chave)
                        extras = {"via": f"{self.idioma}.wikipedia.org/wiki/{titulo}"}
                        if urlsplit(url).netloc == _WAYBACK_HOST:
                            extras["snapshot"] = url
                        yield Referencia(self.id, chave, url, None, None, extras)
                continuar = dados.get("continue") or {}
                if not continuar:
                    break

    def baixar(self, ref: Referencia) -> Documento:
        return documento_html(ref, self.paginas.requisitar(ref.url))

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres)
