# Estimativa de cobertura

## Estrato `academico`

Documentos distintos observados: **98**.

| Canal | Documentos | Só neste canal |
|---|---|---|
| `crossref` | 34 | 1 |
| `openalex` | 97 | 64 |

**Total estimado**

- **Chao (piso, 2 canais comparáveis):** 162 (vistos por um canal só: 65; por exatamente dois: 33).
- **Cobertura:** no máximo 60% (observados ÷ piso).

| Par | n1 | n2 | em comum | Chapman | IC 95% |
|---|---|---|---|---|---|
| `crossref` × `openalex` | 34 | 97 | 33 | 100 | 98 a 104 |

Par sem nada em comum dá estimativa enorme e instável: não diz que o total é enorme, diz que os dois canais olham para lugares diferentes.

**Curva de acumulação**

| Rodada | Novos | Total |
|---|---|---|
| 20261019T184015Z | 97 | 97 |
| 20261019T191812Z | 1 | 98 |
| 20261019T194835Z | 0 | 98 |

## Estrato `geral`

Documentos distintos observados: **38**.

| Canal | Documentos | Só neste canal |
|---|---|---|
| `wikipedia` | 38 | 38 |

Com um canal comparável só não há estimativa: é preciso ao menos dois (canal de janela curta só conta com `--desde`).

**Curva de acumulação**

| Rodada | Novos | Total |
|---|---|---|
| 20261019T175309Z | 27 | 27 |
| 20261019T182627Z | 11 | 38 |
| 20261019T184015Z | 0 | 38 |
| 20261019T191812Z | 0 | 38 |
| 20261019T194835Z | 0 | 38 |

## Estrato `imprensa`

Documentos distintos observados: **89**.

| Canal | Documentos | Só neste canal |
|---|---|---|
| `topico` | 26 | 26 |
| `wayback` | 63 | 63 |

**Total estimado**

- **Chao (piso, 2 canais comparáveis):** 4,005 (vistos por um canal só: 89; por exatamente dois: 0).
- **Cobertura:** no máximo 2% (observados ÷ piso).

| Par | n1 | n2 | em comum | Chapman | IC 95% |
|---|---|---|---|---|---|
| `topico` × `wayback` | 26 | 63 | 0 | 1,727 | 89 a 4,059 |

Par sem nada em comum dá estimativa enorme e instável: não diz que o total é enorme, diz que os dois canais olham para lugares diferentes.

**Curva de acumulação**

| Rodada | Novos | Total |
|---|---|---|
| 20261012T200234Z | 6 | 6 |
| 20261012T201128Z | 57 | 63 |
| 20261012T215901Z | 0 | 63 |
| 20261012T231455Z | 0 | 63 |
| 20261012T232018Z | 0 | 63 |
| 20261013T000920Z | 26 | 89 |
| 20261019T171852Z | 0 | 89 |
| 20261019T175309Z | 0 | 89 |
| 20261019T182627Z | 0 | 89 |
| 20261019T184015Z | 0 | 89 |
| 20261019T191812Z | 0 | 89 |
| 20261019T194835Z | 0 | 89 |

## Estrato `juridico`

Documentos distintos observados: **101**.

| Canal | Documentos | Só neste canal |
|---|---|---|
| `wayback` | 101 | 101 |

Com um canal comparável só não há estimativa: é preciso ao menos dois (canal de janela curta só conta com `--desde`).

**Curva de acumulação**

| Rodada | Novos | Total |
|---|---|---|
| 20261012T215901Z | 91 | 91 |
| 20261012T231455Z | 5 | 96 |
| 20261012T232018Z | 5 | 101 |
| 20261013T000920Z | 0 | 101 |
| 20261019T171852Z | 0 | 101 |
| 20261019T175309Z | 0 | 101 |
| 20261019T182627Z | 0 | 101 |
| 20261019T184015Z | 0 | 101 |
| 20261019T191812Z | 0 | 101 |
| 20261019T194835Z | 0 | 101 |

## Estrato `memoria`

Documentos distintos observados: **9**.

| Canal | Documentos | Só neste canal |
|---|---|---|
| `ia` | 9 | 9 |

Com um canal comparável só não há estimativa: é preciso ao menos dois (canal de janela curta só conta com `--desde`).

**Curva de acumulação**

| Rodada | Novos | Total |
|---|---|---|
| 20261019T194835Z | 9 | 9 |


## Como ler

Os canais não são independentes, e a dependência puxa a estimativa para baixo: os números acima são piso. Saturação de verdade é a curva achatar com canais novos entrando, não só com os mesmos canais repetindo. Par marcado como não comparável junta um canal de janela curta (GDELT, ~90 dias) com um de janela longa sem `--desde`: o número sairia enorme e não diria nada.
