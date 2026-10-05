"""RSS 2.0 e Atom, genérico. Serve a qualquer veículo, blog ou repositório que publique feed.

O feed só serve para listar. O texto vem sempre da página do item: resumo de feed é
resumo, e a triagem nunca decide pelo resumo.

Configuração:
    {"tipo": "rss", "id": "rss:conjur", "url": "https://.../feed",
     "limite_por_minuto": 20, "minimo_caracteres": 400}
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from aletheia.captura import montar_documento
from aletheia.contrato import Documento, Referencia
from aletheia.http import Cliente, Resposta, Transporte, transporte_urllib
from aletheia.texto import Pagina, decodificar

_ATOM = "{http://www.w3.org/2005/Atom}"

# Página de erro servida com HTTP 200. Procurados só no começo de texto curto: página de
# erro é curta e diz o que é logo de saída. Uma matéria longa cuja manchete diga "acesso
# negado" não pode ser reprovada por isso: falso negativo custa mais que falso positivo.
LIMITE_PAGINA_DE_ERRO = 2500
MARCAS_DE_ERRO = (
    "página não encontrada",
    "pagina nao encontrada",
    "page not found",
    "404 not found",
    "acesso negado",
    "access denied",
    "verifique se você é humano",
    "are you a robot",
    "captcha",
    "just a moment",
)


def _data(texto: str | None) -> date | None:
    if not texto:
        return None
    texto = texto.strip()
    try:
        return parsedate_to_datetime(texto).date()  # RSS: RFC 822
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()  # Atom: RFC 3339
    except ValueError:
        return None


def _texto(no: ET.Element | None) -> str | None:
    return no.text.strip() if no is not None and no.text and no.text.strip() else None


def ler_feed(conteudo: bytes, fonte: str) -> Iterator[Referencia]:
    raiz = ET.fromstring(conteudo)
    for item in raiz.iter("item"):  # RSS 2.0
        link = _texto(item.find("link"))
        if not link:
            continue
        yield Referencia(
            fonte=fonte,
            id_na_fonte=_texto(item.find("guid")) or link,
            url=link,
            titulo=_texto(item.find("title")),
            publicado_em=_data(_texto(item.find("pubDate"))),
        )
    for entrada in raiz.iter(f"{_ATOM}entry"):
        links = entrada.findall(f"{_ATOM}link")
        alternativo = [n for n in links if n.get("rel", "alternate") == "alternate"]
        link = (alternativo or links or [None])[0]
        url = link.get("href") if link is not None else None
        if not url:
            continue
        publicado = _texto(entrada.find(f"{_ATOM}published")) or _texto(
            entrada.find(f"{_ATOM}updated")
        )
        yield Referencia(
            fonte=fonte,
            id_na_fonte=_texto(entrada.find(f"{_ATOM}id")) or url,
            url=url,
            titulo=_texto(entrada.find(f"{_ATOM}title")),
            publicado_em=_data(publicado),
        )


class Rss:
    respeita_robots = True

    def __init__(
        self,
        id: str,
        url: str,
        cliente: Cliente,
        limite_por_minuto: int = 20,
        minimo_caracteres: int = 400,
    ) -> None:
        self.id = id
        self.url = url
        self.cliente = cliente
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Rss:
        limite = int(cfg.get("limite_por_minuto", 20))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(cfg["id"], cfg["url"], cliente, limite, int(cfg.get("minimo_caracteres", 400)))

    def listar(self, desde: date) -> Iterator[Referencia]:
        resposta = self.cliente.requisitar(self.url)
        for ref in ler_feed(resposta.corpo, self.id):
            # Item sem data entra: perder um item é pior que reler um.
            if ref.publicado_em is None or ref.publicado_em >= desde:
                yield ref

    def baixar(self, ref: Referencia) -> Documento:
        return documento_html(ref, self.cliente.requisitar(ref.url), ref.titulo)

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres)


def documento_html(ref: Referencia, resposta: Resposta, manchete: str | None = None) -> Documento:
    """Uma página HTML como Documento: texto visível, manchete e linha fina em destaque.

    Compartilhado por todo adaptador que baixa página de veículo (rss, wayback, gdelt).
    """
    html, _ = decodificar(resposta.corpo, resposta.cabecalhos.get("content-type"))
    pagina = Pagina(html)
    manchete = manchete or pagina.manchete or ""
    texto = pagina.texto
    if manchete and manchete not in texto:
        texto = f"{texto}\n\n{manchete}"
    destaques = {"manchete": manchete}
    if descricao := pagina.meta.get("og:description") or pagina.meta.get("description"):
        destaques["linha_fina"] = descricao
        if descricao not in texto:
            texto = f"{texto}\n\n{descricao}"
    return montar_documento(
        ref,
        texto,
        bruto=resposta.corpo,
        cabecalhos={
            k: v for k, v in resposta.cabecalhos.items() if k in ("content-type", "last-modified")
        },
        destaques=destaques,
    )


def pagina_integra(doc: Documento, minimo_caracteres: int, marcas=MARCAS_DE_ERRO) -> bool:
    """Texto longo o bastante e, se curto, sem cara de página de erro."""
    if len(doc.texto) < minimo_caracteres:
        return False
    if len(doc.texto) >= LIMITE_PAGINA_DE_ERRO:
        return True
    cabeca = doc.texto[:300].lower()
    return not any(marca in cabeca for marca in marcas)
