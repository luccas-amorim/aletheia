"""As vistas: uma linha por observação (documento × canal × fonte × rodada).

É a matriz de captura e recaptura. O catálogo diz **o que** existe; as vistas dizem **quem
viu o quê, quando**, e é delas que `estimar` tira a sobreposição entre canais e a curva de
acumulação. Só acrescenta; nunca reescreve. Documentos abaixo de `nivel_minimo` (padrão 2)
ficam de fora: o que o léxico não aceitou nem deixou em dúvida não é "visto".

| Coluna         | Conteúdo                                              |
|----------------|-------------------------------------------------------|
| `id`           | o mesmo id do catálogo (URL normalizada)              |
| `canal`        | prefixo do id da fonte (`wayback`, `gdelt`, ...)      |
| `fonte`        | id da fonte                                           |
| `rodada`       | id da rodada                                          |
| `nivel`        | nível da triagem nesta observação                     |
| `publicado_em` | data declarada ou de captura, para alinhar janelas    |
| `hash_texto`   | para contar como um só documento servido em duas URLs |
| `url`          | o endereço de origem                                  |
"""

from __future__ import annotations

import csv
from pathlib import Path

from aletheia.estimativa import canal
from aletheia.rodada import TRIADO, Rodada
from aletheia.url import identidade, original_do_wayback

COLUNAS = ("id", "canal", "fonte", "rodada", "nivel", "publicado_em", "hash_texto", "url")


def acrescentar(rodada: Rodada, caminho: Path, nivel_minimo: int = 2) -> int:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists()
    escritas = 0
    with caminho.open("a", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        if novo:
            escritor.writeheader()
        for item in rodada.linhas:
            if item.situacao != TRIADO or (item.nivel or 0) < nivel_minimo:
                continue
            url = original_do_wayback(item.ref.url)
            escritor.writerow(
                {
                    "id": identidade(url),
                    "canal": canal(item.ref.fonte),
                    "fonte": item.ref.fonte,
                    "rodada": rodada.id,
                    "nivel": item.nivel,
                    "publicado_em": item.ref.publicado_em.isoformat()
                    if item.ref.publicado_em
                    else "",
                    "hash_texto": item.hash_texto or "",
                    "url": url,
                }
            )
            escritas += 1
    return escritas
