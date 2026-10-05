# Alétheia — Observatório do Massacre do Carandiru

Catálogo do que a internet guarda sobre o massacre de 2 de outubro de 1992 na Casa de
Detenção de São Paulo: reportagens, artigos acadêmicos, acervos, documentos judiciais. Um
robô descobre por canais independentes, lê o texto inteiro, confronta com o léxico da
pesquisa, anota a cópia de referência no Internet Archive e **estima quanto ainda falta**.
Nada aqui é opinião sobre o caso: é um índice conferido do que existe, com o método à vista.

O nome está em [`MITO.md`](MITO.md). O motor descende do [Argos](https://github.com/luccas-amorim/argos).

> **Estado em 05/10/2026:** motor reconstruído e testado (124 testes, sem rede); catálogo
> ainda **vazio**, à espera da primeira varredura. O léxico é **provisório**. Ver
> [`CHANGELOG.md`](CHANGELOG.md), [`docs/operacao.md`](docs/operacao.md) e
> [`docs/plano.md`](docs/plano.md).

## O que está aqui

| Arquivo | O que é | Quem mantém |
|---|---|---|
| [`catalogo.csv`](catalogo.csv) | **o catálogo**: um documento por linha, 14 colunas ([formato](aletheia/saidas/catalogo.py)) | o robô, toda rodada |
| [`vistas.csv`](vistas.csv) | quem viu o quê, quando: a matriz de captura e recaptura | o robô |
| `estimativa.md` | quanto já foi achado e quanto falta, por estrato | o robô, depois de cada rodada |
| [`lexico.json`](lexico.json) | o vocabulário que decide o que entra e como se cataloga | a pesquisa (o atual é **provisório**) |
| [`config.json`](config.json) | os canais de busca e os estratos | a pesquisa, com apoio técnico |
| [`listas/`](listas/) | URLs curadas à mão (Hemeroteca, acervos sem API) | a pesquisa |
| `saidas/` | o relatório de cada rodada: o que entrou, o que pede leitura, o que foi descartado e por quê | o robô |
| `estado/` | a memória do robô: o que já viu, o que falhou, até onde foi em cada varredura | o robô |
| [`index.html`](index.html) | o catálogo navegável no GitHub Pages, sem servidor | apoio técnico |
| [`docs/`](docs/) | [como rodar](docs/operacao.md), plano, método da estimativa, política sobre pessoas | a pesquisa |
| [`aletheia/`](aletheia/) | o motor | apoio técnico |

O texto integral das páginas **não** é guardado (`"guardar_texto": false`): o catálogo é o
índice; a cópia de referência é a do Wayback Machine, na coluna `snapshot`.

## Os canais

| Canal | O que alcança | Como |
|---|---|---|
| `wayback` | tudo o que foi arquivado de um veículo com o termo no endereço, inclusive o que saiu do ar | CDX, por **prefixo de seção × ano**, com progresso gravado |
| `topico` | a página de tag do veículo, viva e nas versões arquivadas | paginação + CDX da própria página |
| `wikipedia` | os links externos dos verbetes, em pt e en | API do MediaWiki; semente de URLs e de domínios |
| `gdelt` | notícias pelo texto, no mundo, últimos ~90 dias | DOC 2.0 |
| `openalex`, `crossref` | artigos, teses, livros (título e resumo) | APIs abertas; dois canais dão estimativa ao estrato |
| `ia` | livros, vídeos, áudios e documentos depositados no Internet Archive | `advancedsearch` |
| `lista` | o que nenhum robô alcança por política ou falta de API | CSV em `listas/` |

O Google (busca e Notícias) está **fora, por política**: não há API, e o `robots.txt` não
autoriza. Redes sociais e acervos pagos também. O que eles indexam quase sempre existe em
outro lugar que se pode ler com licença ([`docs/plano.md`](docs/plano.md)).

## Como o catálogo cresce

Toda segunda-feira o robô roda ([`.github/workflows/rodada.yml`](.github/workflows/rodada.yml)):

1. cada canal lista o que há de novo; o Wayback avança as fatias que faltam da varredura;
2. o texto de cada item é lido inteiro e confrontado com o léxico;
3. nível 3 entra em `catalogo.csv`; nível 2 e 3 entram em `vistas.csv`; nível 2 vai para
   `saidas/<rodada>/pede-juizo.jsonl`, para leitura humana;
4. documentos sem cópia de referência são procurados no Wayback por URL exata;
5. `estimativa.md` é recalculada.

Cada fonte é comitada ao terminar. Se o job estourar o tempo, nada se perde: o estado guarda
o que foi visto e até onde cada varredura chegou.

**A primeira varredura** parte do dia do massacre (`"desde": "1992-10-02"`) e vem até hoje.
Cada canal alcança o que pode: Crossref e OpenAlex, pela data de publicação, chegam a 1992;
o Wayback só tem capturas desde 1996 e corta a janela sozinho (o relatório diz a janela
efetiva); o GDELT só vê os últimos ~90 dias; a imprensa de 1992 a ~1998 entra pela
Hemeroteca Digital, à mão, em `listas/`. Ela cabe em algumas rodadas: os veículos grandes
são consultados por seções e anos (`fatias_por_rodada` limita cada passagem); os pequenos,
de uma vez. Durante essa fase, troque o `cron` para diário. Depois, cada rodada semanal
cobre só o que saiu desde a anterior (menos a margem de 7 dias). Para calibrar os prefixos:

```bash
aletheia sondar --config config.json --fonte wayback:folha
```

## Rodar à mão

O passo a passo completo, do `git push` à operação semanal, está em
[`docs/operacao.md`](docs/operacao.md).

```bash
pip install -e ".[dev]"
aletheia validar-lexico lexico.json
aletheia validar-config config.json
aletheia rodar --config config.json --fonte wayback:ponte --desde 1996-01-01
aletheia estimar --config config.json
pytest -q          # sem rede, contra fixtures
```

Exige Python 3.11+. Sem dependências além da biblioteca padrão.

## Antes da primeira rodada

- Em **Settings → Secrets and variables → Actions**, defina `OPENALEX_API_KEY` (chave
  gratuita). Opcional: `CROSSREF_MAILTO`, para o *polite pool* do Crossref. Nenhuma chave
  aparece em relatório ou log: o cliente HTTP as redige.
- Em **Settings → Pages**, publique a partir de `main`, pasta `/` (raiz): `index.html` lê
  `catalogo.csv` e `estimativa.md` do próprio repositório.
- Troque o léxico provisório pelo da pesquisa quando ele existir; `lexico_versao` no catálogo
  diz o que cada linha "viu".

## O léxico

`lexico.json` segue [`lexico.schema.json`](lexico.schema.json). Cada termo tem `formas` (as
grafias que contam), `exclusoes` (o que parece mas não é: o filme, a estação de metrô),
`categorias` (as facetas de catalogação) e `peso`. O `contexto` separa o evento de outros usos
da palavra. Reticências (`…`) numa forma valem até 60 caracteres: "massacre … Carandiru".

## Pessoas

O catálogo **descreve documentos, não pessoas**: não há coluna de nome, não há texto, não há
cruzamento de fontes para montar perfil. Vítima, familiar ou pessoa citada pode pedir a
remoção do título de uma linha sem provar vínculo. Regras, base legal e registro de decisões
em [`docs/pessoas.md`](docs/pessoas.md); pedido por
[issue](.github/ISSUE_TEMPLATE/remocao.md).

## Licenças

Código sob [MIT](LICENSE). Catálogo, vistas, estimativa e relatórios sob
[CC BY 4.0](LICENSE-CATALOGO.md). Os documentos catalogados continuam sob os direitos de
quem os publicou: o catálogo aponta, não redistribui. Para citar: [`CITATION.cff`](CITATION.cff).

## Apoie

Este observatório é mantido por uma pessoa, nas horas livres, sem financiamento. O que o apoio
compra é tempo: para ler a fila "pede juízo", para substituir o léxico provisório, para conferir
os domínios candidatos que a Wikipédia aponta. A varredura em si roda de graça no GitHub Actions.

[GitHub Sponsors](https://github.com/sponsors/luccas-amorim) · [PIX](https://luccas-amorim.github.io/apoie/)

Tudo o que o apoio financia continua aberto e gratuito. Nada aqui é consultoria jurídica.
