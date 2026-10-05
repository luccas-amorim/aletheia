"""O catálogo: uma linha por documento, cumulativo, em CSV versionado.

| Coluna            | Conteúdo                                                              |
|-------------------|-----------------------------------------------------------------------|
| `id`              | 16 hex do sha256 da URL normalizada: estável entre rodadas e canais   |
| `url`             | o endereço de origem (sem o prefixo do Wayback)                       |
| `dominio`         | host, sem `www.`                                                      |
| `estrato`         | o da fonte que o trouxe primeiro                                      |
| `titulo`          | manchete ou título, como a fonte deu                                  |
| `publicado_em`    | data declarada pela fonte; vazia se desconhecida                      |
| `capturado_em`    | timestamp da captura do Wayback usada como referência                 |
| `snapshot`        | `https://web.archive.org/web/<ts>id_/<url>`, quando há                |
| `hash_texto`      | sha256 do texto normalizado                                           |
| `nivel`           | 2 ou 3 na primeira vez                                                |
| `identificadores` | chaves do léxico que casaram, separadas por `;`                       |
| `categorias`      | facetas do léxico, separadas por `;`                                  |
| `primeira_rodada` | id da rodada em que entrou                                            |
| `lexico_versao`   | versão do léxico que decidiu                                          |

O arquivo cresce entre rodadas e **nunca reescreve uma linha**: documento que volta numa
rodada seguinte, ou por outro canal, mantém o registro da primeira vez. Dois endereços
que servem o mesmo texto (`hash_texto` igual: `/amp/`, `/embed/`, republicação) são um
documento. A única exceção é
o `snapshot`: quando vazio e depois resolvido, é preenchido (ver `completar_snapshots`).
O catálogo descreve documentos, não pessoas: o título é o único campo textual e vem da
fonte; não há coluna de nomes.

O formato antigo (três colunas: `id,url,identificadores`) é lido e migrado na primeira
gravação; o `id` muda para o da URL normalizada.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from aletheia.rodada import TRIADO, Rodada
from aletheia.url import dominio, identidade, original_do_wayback

COLUNAS = (
    "id",
    "url",
    "dominio",
    "estrato",
    "titulo",
    "publicado_em",
    "capturado_em",
    "snapshot",
    "hash_texto",
    "nivel",
    "identificadores",
    "categorias",
    "primeira_rodada",
    "lexico_versao",
)


def id_da_url(url: str) -> str:
    return identidade(url)


def ler(caminho: Path) -> list[dict[str, str]]:
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    # Migração do formato de três colunas.
    saida = []
    for linha in linhas:
        completa = {c: (linha.get(c) or "") for c in COLUNAS}
        completa["url"] = original_do_wayback(completa["url"])
        completa["id"] = identidade(completa["url"]) if completa["url"] else completa["id"]
        completa["dominio"] = completa["dominio"] or (
            dominio(completa["url"]) if completa["url"] else ""
        )
        saida.append(completa)
    return saida


def _gravar(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".csv.part")
    with temporario.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    os.replace(temporario, caminho)


def _timestamp(snapshot: str | None) -> str:
    if not snapshot:
        return ""
    partes = snapshot.split("/web/", 1)
    return (
        partes[1].split("/", 1)[0].rstrip("abcdefghijklmnopqrstuvwxyz_") if len(partes) == 2 else ""
    )


def atualizar(
    rodada: Rodada,
    caminho: Path,
    nivel_minimo: int = 3,
    estrato_de=lambda fonte: "geral",
) -> int:
    """Acrescenta os documentos novos da rodada com nível >= `nivel_minimo`. Devolve quantos."""
    caminho = Path(caminho)
    linhas = ler(caminho)
    conhecidos = {linha["id"] for linha in linhas}
    # O mesmo texto servido em duas URLs (`/amp/`, `/embed/`, republicação) é um documento.
    textos = {linha["hash_texto"] for linha in linhas if linha.get("hash_texto")}
    novas = 0
    for item in rodada.linhas:
        if item.situacao != TRIADO or (item.nivel or 0) < nivel_minimo:
            continue
        url = original_do_wayback(item.ref.url)
        ident = identidade(url)
        if ident in conhecidos or (item.hash_texto and item.hash_texto in textos):
            continue
        conhecidos.add(ident)
        if item.hash_texto:
            textos.add(item.hash_texto)
        r = item.resultado
        linhas.append(
            {
                "id": ident,
                "url": url,
                "dominio": dominio(url),
                "estrato": estrato_de(item.ref.fonte),
                "titulo": (item.titulo or "").replace("\n", " ").strip(),
                "publicado_em": item.ref.publicado_em.isoformat() if item.ref.publicado_em else "",
                "capturado_em": _timestamp(item.snapshot),
                "snapshot": item.snapshot or "",
                "hash_texto": item.hash_texto or "",
                "nivel": str(item.nivel or ""),
                "identificadores": ";".join(r.chaves) if r else "",
                "categorias": ";".join(r.categorias) if r else "",
                "primeira_rodada": rodada.id,
                "lexico_versao": rodada.lexico_versao,
            }
        )
        novas += 1
    if novas or not caminho.exists() or _precisa_migrar(caminho):
        _gravar(caminho, linhas)
    return novas


def _precisa_migrar(caminho: Path) -> bool:
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        cabecalho = next(csv.reader(arquivo), [])
    return tuple(cabecalho) != COLUNAS


def completar_snapshots(caminho: Path, resolver) -> int:
    """Preenche `snapshot`/`capturado_em` vazios usando `resolver(url) -> (ts, url) | None`."""
    linhas = ler(caminho)
    preenchidas = 0
    for linha in linhas:
        if linha["snapshot"] or not linha["url"]:
            continue
        achado = resolver(linha["url"])
        if achado is None:
            continue
        linha["capturado_em"], linha["snapshot"] = achado
        preenchidas += 1
    if preenchidas:
        _gravar(caminho, linhas)
    return preenchidas
