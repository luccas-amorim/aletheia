"""Páginas de tópico ou de tag dos veículos: a lista que a própria redação mantém.

`cartacapital.com.br/tag/carandiru/`, `ponte.org/tag/carandiru/`,
`agenciabrasil.ebc.com.br/tags/carandiru` (todas respondendo em 05/10/2026) são índices
curados do que o veículo publicou sobre o tema, paginados. É o canal de maior rendimento
por requisição, e **independente** do Wayback por endereço: acha matéria que não tem a
palavra na URL. Com `"arquivadas": true`, o adaptador também lê as versões antigas da
própria página de tag no Wayback (uma por ano), o que recupera matérias despublicadas.

O adaptador respeita o `robots.txt` do veículo. Medido em 05/10/2026: Ponte e CartaCapital
(atrás da Cloudflare) respondem **403 ao `robots.txt`** para robôs identificados; o cliente
lê isso como "proíbe tudo", por política. Agência Brasil responde 200 e autoriza. Quando a
página viva é vedada e `arquivadas` está ligado, o adaptador lê só as versões do Wayback,
que são interface do arquivo, não do veículo; sem `arquivadas`, a fonte falha com o motivo
nomeado, em vez de devolver zero em silêncio. Links são filtrados ao
mesmo domínio e a caminhos que parecem matéria (fora `/tag/`, `/autor/`, `/page/`, busca, feed).

Configuração:
    {"tipo": "topico", "id": "topico:ponte", "url": "https://ponte.org/tag/carandiru/",
     "paginacao": "page/{n}/", "max_paginas": 40, "arquivadas": true,
     "limite_por_minuto": 12, "estrato": "imprensa"}

`paginacao` é o sufixo da página `n` (n ≥ 2), relativo à URL do tópico: `page/{n}/` dá
`.../tag/carandiru/page/2/`; `?page={n}` dá `.../tags/carandiru?page=2`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit

from aletheia.arquivo import CDX, snapshot
from aletheia.contrato import Documento, Referencia
from aletheia.fontes.rss import documento_html, pagina_integra
from aletheia.http import BloqueadoPorRobots, Cliente, ErroColeta, Transporte, transporte_urllib
from aletheia.url import normalizar, original_do_wayback

log = logging.getLogger(__name__)

_NAO_MATERIA = re.compile(
    r"/(tag|tags|tema|temas|topico|topicos|tudo-sobre|autor|autores|author|category|"
    r"categoria|categorias|assunto|assuntos|page|pagina|search|busca|feed|wp-|amp)(/|$)|"
    r"[?&](s|q|busca|page|pagina)=|/feed$|\.(xml|rss|jpg|jpeg|png|gif|pdf|mp3|mp4)$",
    re.I,
)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def extrair_links(html: str, base: str, so_dominio: str | None) -> list[str]:
    """Links absolutos, do mesmo domínio, com cara de matéria, sem repetição, na ordem."""
    parser = _Links()
    parser.feed(html)
    parser.close()
    base_original = original_do_wayback(base)
    vistos: set[str] = set()
    saida: list[str] = []
    for href in parser.hrefs:
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        absoluto = urljoin(base_original, href.strip())
        absoluto = original_do_wayback(absoluto)
        partes = urlsplit(absoluto)
        if partes.scheme not in ("http", "https"):
            continue
        host = partes.netloc.lower().removeprefix("www.")
        if so_dominio and not (host == so_dominio or host.endswith(f".{so_dominio}")):
            continue
        if len(partes.path.strip("/")) < 8 or _NAO_MATERIA.search(absoluto):
            continue
        chave = normalizar(absoluto)
        if chave in vistos or chave == normalizar(base_original):
            continue
        vistos.add(chave)
        saida.append(absoluto.split("#", 1)[0])
    return saida


class Topico:
    respeita_robots = True

    def __init__(
        self,
        id: str,
        url: str,
        cliente: Cliente,
        arquivo: Cliente | None = None,
        *,
        paginacao: str = "page/{n}/",
        max_paginas: int = 40,
        arquivadas: bool = False,
        limite_por_minuto: int = 12,
        minimo_caracteres: int = 400,
    ) -> None:
        self.id = id
        self.url = url
        self.cliente = cliente
        self.arquivo = arquivo
        self.paginacao = paginacao
        self.max_paginas = max_paginas
        self.arquivadas = arquivadas
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres
        host = urlsplit(url).netloc.lower().removeprefix("www.")
        # Domínio registrável aproximado: os dois últimos rótulos (três se o penúltimo é
        # curto, como em `.com.br`).
        rotulos = host.split(".")
        self.dominio = ".".join(
            rotulos[-3:] if len(rotulos) > 2 and len(rotulos[-2]) <= 3 else rotulos[-2:]
        )

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Topico:
        limite = int(cfg.get("limite_por_minuto", 12))
        cliente = Cliente(limite, respeita_robots=True, transporte=transporte)
        arquivo = Cliente(15, respeita_robots=False, transporte=transporte, tempo_limite=120)
        return cls(
            cfg["id"],
            cfg["url"],
            cliente,
            arquivo,
            paginacao=cfg.get("paginacao", "page/{n}/"),
            max_paginas=int(cfg.get("max_paginas", 40)),
            arquivadas=bool(cfg.get("arquivadas", False)),
            limite_por_minuto=limite,
            minimo_caracteres=int(cfg.get("minimo_caracteres", 400)),
        )

    def _pagina(self, n: int) -> str:
        if n == 1:
            return self.url
        sufixo = self.paginacao.format(n=n)
        if sufixo.startswith("?"):
            return (
                f"{self.url.rstrip('/')}{sufixo}"
                if "?" not in self.url
                else f"{self.url}&{sufixo[1:]}"
            )
        return urljoin(self.url if self.url.endswith("/") else self.url + "/", sufixo)

    def _referencias(self, links: list[str], via: str, vistos: set[str]) -> Iterator[Referencia]:
        for link in links:
            chave = normalizar(link)
            if chave in vistos:
                continue
            vistos.add(chave)
            yield Referencia(
                fonte=self.id, id_na_fonte=chave, url=link, titulo=None, dados={"via": via}
            )

    def listar(self, desde: date) -> Iterator[Referencia]:
        vistos: set[str] = set()
        for n in range(1, self.max_paginas + 1):
            pagina = self._pagina(n)
            try:
                resposta = self.cliente.requisitar(pagina)
            except BloqueadoPorRobots:
                # Política, não falha de rede. Sem versões arquivadas para ler, a fonte não
                # tem o que fazer e diz isso; com elas, segue só pelo arquivo.
                if not (self.arquivadas and self.arquivo is not None):
                    raise
                log.warning(
                    "%s: robots.txt não autoriza %s; lendo só as versões arquivadas",
                    self.id,
                    pagina,
                )
                break
            except ErroColeta:
                break  # acabou a paginação (404) ou a página não responde: para aqui
            html = resposta.corpo.decode("utf-8", errors="replace")
            novos = [link for link in extrair_links(html, pagina, self.dominio)
                     if normalizar(link) not in vistos]  # fmt: skip
            if not novos:
                break
            yield from self._referencias(novos, pagina, vistos)
        if self.arquivadas and self.arquivo is not None:
            yield from self._arquivadas(desde, vistos)

    def _arquivadas(self, desde: date, vistos: set[str]) -> Iterator[Referencia]:
        """Uma captura por ano da própria página de tópico, desde `desde`."""
        params = [
            ("url", self.url),
            ("matchType", "exact"),
            ("filter", "statuscode:200"),
            ("collapse", "timestamp:4"),
            ("output", "json"),
            ("fl", "timestamp,original"),
            ("from", desde.strftime("%Y%m%d")),
        ]
        linhas = self.arquivo.requisitar(f"{CDX}?{urlencode(params)}").json() or []
        for linha in linhas[1:]:
            if not linha:
                continue
            momento, original = linha[0], linha[1]
            captura = snapshot(momento, original)
            try:
                html = self.arquivo.requisitar(captura).corpo.decode("utf-8", errors="replace")
            except ErroColeta:
                continue
            yield from self._referencias(
                extrair_links(html, captura, self.dominio), captura, vistos
            )

    def baixar(self, ref: Referencia) -> Documento:
        return documento_html(ref, self.cliente.requisitar(ref.url))

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres)
