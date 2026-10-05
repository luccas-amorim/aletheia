"""Saídas de uma rodada. Todas escritas em `<saidas>/<id da rodada>/`.

| Arquivo                  | Conteúdo                                                        |
|--------------------------|-----------------------------------------------------------------|
| `itens.jsonl`            | uma linha por item, todos os níveis e situações (canônico)      |
| `aceitos.jsonl`          | só nível 3, com proveniência: o que o consumidor importa        |
| `pede-juizo.jsonl`       | só nível 2: o que precisa de leitura humana                     |
| `relatorio-completo.md`  | uma linha por item, aceitos e descartados, com o motivo         |
| `relatorio-resumo.md`    | o que pede ação: aceitos, pede juízo, falhas                    |
| `rodada.json`            | metadados: léxico, versão do motor, datas, contagens            |
"""

from __future__ import annotations

from pathlib import Path

from aletheia.rodada import Rodada
from aletheia.saidas import jsonl, relatorio


def escrever(rodada: Rodada, raiz: Path) -> Path:
    pasta = Path(raiz) / f"{rodada.id}-{rodada.modo}"
    pasta.mkdir(parents=True, exist_ok=True)
    jsonl.escrever(rodada, pasta)
    relatorio.escrever(rodada, pasta)
    return pasta
