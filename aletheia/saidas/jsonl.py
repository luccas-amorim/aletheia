"""JSONL: a fronteira com o consumidor. Cada linha carrega a proveniência inteira."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from aletheia import __version__
from aletheia.rodada import TRIADO, Rodada


def _linha(rodada: Rodada, dados: dict) -> str:
    dados = {**dados, "lexico": {"id": rodada.lexico_id, "versao": rodada.lexico_versao}}
    return json.dumps(dados, ensure_ascii=False)


def _gravar(caminho: Path, linhas: list[str]) -> None:
    caminho.write_text("".join(f"{linha}\n" for linha in linhas), encoding="utf-8")


def contagens(rodada: Rodada) -> dict:
    por_situacao = Counter(linha.situacao for linha in rodada.linhas)
    por_motivo = Counter(
        linha.resultado.motivo for linha in rodada.linhas if linha.resultado is not None
    )
    return {
        "situacao": dict(sorted(por_situacao.items())),
        "motivo": dict(sorted(por_motivo.items())),
    }


def escrever(rodada: Rodada, pasta: Path) -> None:
    todos = [linha.como_dict() for linha in rodada.linhas]
    _gravar(pasta / "itens.jsonl", [_linha(rodada, d) for d in todos])
    for nome, nivel in (("aceitos.jsonl", 3), ("pede-juizo.jsonl", 2)):
        escolhidos = [d for d in todos if d["situacao"] == TRIADO and d["nivel"] == nivel]
        _gravar(pasta / nome, [_linha(rodada, d) for d in escolhidos])
    meta = {
        "id": rodada.id,
        "modo": rodada.modo,
        "motor": __version__,
        "lexico": {"id": rodada.lexico_id, "versao": rodada.lexico_versao},
        "inicio": rodada.inicio,
        "fim": rodada.fim,
        "desde": rodada.desde,
        "falhas_de_fonte": rodada.falhas_de_fonte,
        "incompletas": rodada.incompletas,
        "pede_leitura": rodada.pede_leitura,
        "contagens": contagens(rodada),
        "codigo_saida": rodada.codigo_saida,
    }
    (pasta / "rodada.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
