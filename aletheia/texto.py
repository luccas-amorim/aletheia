"""Decodificação, extração de texto de HTML e a dobra usada para casar termos.

Decodificar errado não quebra: corrompe em silêncio e imita texto velho (a lição da F0 do
AtlasPen, com o Planalto servindo cp1252 sem declarar e UTF-16 com BOM). Por isso a
detecção mora aqui, uma vez só, e o resto do motor só vê texto UTF-8 normalizado.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from html.parser import HTMLParser

_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)
_CT_CHARSET = re.compile(r"charset\s*=\s*\"?([A-Za-z0-9_\-]+)", re.I)


def decodificar(bruto: bytes, content_type: str | None = None) -> tuple[str, str]:
    """(texto, codificação). Ordem: BOM, cabeçalho HTTP, meta charset, UTF-8, cp1252."""
    if bruto.startswith(b"\xef\xbb\xbf"):
        return bruto[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    if bruto.startswith((b"\xff\xfe", b"\xfe\xff")):
        # Byte ímpar no fim do UTF-16 é lixo de borda (visto no Planalto), não conteúdo.
        corpo = bruto[:-1] if len(bruto) % 2 else bruto
        return corpo.decode("utf-16", errors="replace"), "utf-16"

    candidatas: list[str] = []
    if content_type and (m := _CT_CHARSET.search(content_type)):
        candidatas.append(m.group(1))
    if m := _META_CHARSET.search(bruto[:4096]):
        candidatas.append(m.group(1).decode("ascii", errors="ignore"))
    candidatas += ["utf-8", "cp1252"]

    for nome in candidatas:
        try:
            return bruto.decode(_canonico(nome)), _canonico(nome)
        except (LookupError, UnicodeDecodeError):
            continue
    return bruto.decode("cp1252", errors="replace"), "cp1252"


def _canonico(nome: str) -> str:
    nome = nome.strip().lower()
    # iso-8859-1 declarado quase sempre é cp1252 na prática (aspas e travessões do Word).
    return "cp1252" if nome in {"iso-8859-1", "latin-1", "latin1", "us-ascii"} else nome


_IGNORAR = {"script", "style", "noscript", "template", "svg", "nav", "footer", "aside", "form"}
_BLOCO = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dd", "dt", "figcaption",
}  # fmt: skip


class _Extrator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.titulo: list[str] = []
        self.h1: list[str] = []
        self.meta: dict[str, str] = {}
        self._ignorando = 0
        self._em: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorando += 1
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            chave = (a.get("property") or a.get("name") or "").lower()
            if chave and "content" in a:
                self.meta.setdefault(chave, a["content"])
        if tag in _BLOCO:
            self.partes.append("\n")
        self._em.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self.handle_starttag(tag, attrs)
            self._em.pop()
        elif tag in _BLOCO:
            self.partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorando:
            self._ignorando -= 1
        if tag in _BLOCO:
            self.partes.append("\n")
        if tag in self._em:
            while self._em and self._em.pop() != tag:
                pass

    def handle_data(self, dado: str) -> None:
        if "title" in self._em:
            self.titulo.append(dado)
            return
        if self._ignorando:
            return
        if "h1" in self._em:
            self.h1.append(dado)
        self.partes.append(dado)


class Pagina:
    """Texto visível de uma página HTML, mais o que ela declara sobre si."""

    def __init__(self, html: str) -> None:
        extrator = _Extrator()
        extrator.feed(html)
        extrator.close()
        self.texto = normalizar("".join(extrator.partes))
        self.titulo = normalizar(" ".join(extrator.titulo)) or None
        self.h1 = normalizar(" ".join(extrator.h1)) or None
        self.meta = extrator.meta

    @property
    def manchete(self) -> str | None:
        return self.meta.get("og:title") or self.h1 or self.titulo


def html_para_texto(html: str) -> str:
    return Pagina(html).texto


def normalizar(texto: str) -> str:
    """NFC, espaços colapsados por linha, no máximo uma linha em branco seguida."""
    texto = unicodedata.normalize("NFC", texto).replace("\xa0", " ").replace("\r", "")
    linhas = [re.sub(r"[ \t\f\v]+", " ", linha).strip() for linha in texto.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def dobrar(texto: str) -> str:
    """Minúsculas sem acento, com UM caractere de saída por caractere de entrada.

    A correspondência 1:1 é o que permite achar o termo no texto dobrado e recortar o
    trecho do texto original pelos mesmos índices.
    """
    saida = []
    for c in texto:
        base = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
        base = base.lower()
        saida.append(base[0] if base else c)
    return "".join(saida)


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
