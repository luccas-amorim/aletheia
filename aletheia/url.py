"""A URL como identidade: a mesma normalização para o catálogo, as vistas e a estimativa.

Duas URLs que diferem só em esquema, `www.`, barra final, porta padrão, parâmetros de
rastreio ou prefixo do Wayback apontam para o mesmo documento e precisam do mesmo `id`.
Antes, o catálogo usava a URL crua e a estimativa a normalizada: a mesma matéria vista
pelo GDELT (ao vivo) e pelo Wayback (arquivada) virava duas linhas.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

_WAYBACK = re.compile(r"^https?://web\.archive\.org/web/\d+[a-z_]*/(.+)$")
_RASTREIO = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|amp$|igshid$|_ga$)")


def normalizar(url: str) -> str:
    """`host/caminho?consulta`, sem esquema, `www.`, porta padrão, barra final nem rastreio."""
    url = url.strip()
    if m := _WAYBACK.match(url):
        url = m.group(1)
    if "://" not in url:
        url = f"http://{url}"
    partes = urlsplit(url)
    host = partes.netloc.lower().removeprefix("www.")
    host = re.sub(r":(80|443)$", "", host)
    caminho = partes.path.rstrip("/") or "/"
    consulta = urlencode(
        sorted((k, v) for k, v in parse_qsl(partes.query) if not _RASTREIO.match(k.lower()))
    )
    return f"{host}{caminho}" + (f"?{consulta}" if consulta else "")


def identidade(url: str) -> str:
    """16 hex do sha256 da URL normalizada: estável entre rodadas e entre canais."""
    return hashlib.sha256(normalizar(url).encode("utf-8")).hexdigest()[:16]


def dominio(url: str) -> str:
    return normalizar(url).split("/", 1)[0]


def original_do_wayback(url: str) -> str:
    """A URL de origem por trás de um endereço do Wayback; a própria URL se não for."""
    m = _WAYBACK.match(url.strip())
    return m.group(1) if m else url
