# Plano: como chegar perto de "tudo"

Pergunta de partida: é possível um robô vasculhar, incrementalmente, **toda** a internet
sobre o massacre do Carandiru e catalogar cada achado com o universo léxico da pesquisa?

Resposta curta: **"toda" não se garante; "quase toda, com a lacuna medida", sim.** Nenhum
sistema, nem o Google, enumera tudo o que existe sobre um tema. O que dá para construir é
um robô que descobre por vários canais independentes, nunca esquece o que achou, guarda a
URL, a cópia de referência e o motivo de cada achado, e **estima quanto ainda falta**. A
última parte é a que transforma "toda a internet" de promessa em número.

## Duas tarefas diferentes

| | Varredura (o passivo) | Vigilância (o fluxo) |
|---|---|---|
| Pergunta | o que já foi publicado desde 1992? | o que saiu desde a última rodada? |
| Volume | grande, uma vez | pequeno, toda semana |
| Canais | Wayback por fatias, páginas de tópico arquivadas, Crossref/OpenAlex/IA, Wikipédia | GDELT, RSS, páginas de tópico vivas, buscas periódicas |
| No motor | fatias `prefixo × ano` com progresso no estado | `rodar` agendado, janela = última rodada − margem |

O contrato do adaptador serve às duas: `listar(desde)` com uma data antiga é a varredura;
com a data da última rodada, é a vigilância. O estado garante que nada seja relido nem
esquecido: item que falhou fica **pendente** e volta em toda rodada; fatia concluída não
volta a ser consultada.

## Descobrir é uma coisa; arquivar é outra

A primeira versão pedia ao Wayback as duas coisas ao mesmo tempo: *descobrir* todas as URLs
de um domínio com o termo e *servir* a cópia. É por isso que a consulta era larga demais e
estourava. Agora:

- **Qualquer canal descobre** URLs (Wayback fatiado, tópico, GDELT, Crossref, Wikipédia…).
- **O Wayback fornece a cópia de referência** por URL exata (`aletheia/arquivo.py`), que
  responde em menos de um segundo, para todo documento que entra no catálogo.
- **Pedir o arquivamento** de uma URL viva ainda sem cópia (SavePageNow) é o próximo passo
  natural, e uma decisão da pesquisa: exige chave e tem cota própria. O ponto de extensão
  existe (`Arquivo.pedir`).

## Por que não "raspar o Google"

- **Não há API.** A Custom Search JSON API fechou para novos clientes e a busca na web inteira
  termina em 1º/01/2027. A Bing Search API foi desligada em 11/08/2025.
- **O `robots.txt` do Google proíbe `/search`**, e o do Google Notícias (`news.google.com`)
  tem `Disallow: /` sem liberar `/rss/search` (medido em 05/10/2026). O motor não ignora
  `robots.txt`, por política. Serviços pagos de SERP seriam contornar a regra por intermediário.
- **"Centenas de milhares de resultados" é estimativa do buscador**, não contagem.

O que o Google indexa, porém, quase sempre existe em outro lugar que se pode ler com
licença: no Wayback, na página de tópico do veículo, no Crossref, no próprio site de origem.

## Os canais, por ordem de rendimento esperado

| Canal | O que entrega | Estado | Observação |
|---|---|---|---|
| **Wayback (CDX)** · `wayback` | toda URL arquivada cujo endereço contenha o termo, com data de captura, inclusive de páginas mortas | pronto, **fatiado** | domínio inteiro só para sites pequenos; veículos grandes por prefixo de seção × ano (`sondar` mede) |
| **Páginas de tópico** · `topico` | o índice curado da própria redação, vivo e nas versões arquivadas | pronto | maior rendimento por requisição; acha matéria sem o termo na URL |
| **Wikipédia** · `wikipedia` | os links externos dos verbetes | pronto | semente de URLs e de **domínios candidatos** (23 em pt, em 05/10/2026) |
| **GDELT DOC 2.0** · `gdelt` | notícias do mundo, pelo texto, em 65 línguas | pronto | janela de ~90 dias: vigilância, não passivo |
| **Crossref** · `crossref` | registro de DOIs, aberto | pronto | 72 trabalhos em 05/10/2026; dá o segundo canal acadêmico |
| **OpenAlex** · `openalex` | produção acadêmica indexada | pronto | exige chave gratuita |
| **Internet Archive** · `ia` | livros, vídeos, áudios, documentos depositados | pronto | busca em texto integral da coleção |
| **RSS** · `rss` | fluxo de um veículo ou repositório | pronto | vigilância |
| **Lista curada** · `lista` | Hemeroteca Digital, acervos pagos, documentos do processo | pronto | trabalho humano, CSV versionado |
| **Media Cloud** | notícias pelo texto desde 2008, com coleção nacional | a escrever | API com chave gratuita; substitui o Google para o passado da imprensa |
| **OAI-PMH** (BDTD, SciELO, repositórios) | teses e dissertações | a escrever | um adaptador serve a dezenas de repositórios; endpoints a confirmar |
| **YouTube Data API** | vídeo | a escrever | chave gratuita, cota diária suficiente para vigilância |
| **Common Crawl pelo texto** | páginas sem o termo no endereço | a escrever | o maior ponto cego; custa processamento (ver estimativa.md) |
| **Processos** (DataJud, DJEN) | ações penais, recursos no STJ e no STF | no Argos | DJEN exige IP brasileiro |

## Medir o que falta: captura e recaptura

Com dois canais razoavelmente independentes, a sobreposição entre eles estima o total
(Chapman; Chao para três ou mais). `vistas.csv` é a matriz: uma linha por observação de um
documento por um canal numa rodada. Regras em [`estimativa.md`](estimativa.md).

## O léxico da pesquisa

Entra como dado, em `lexico.json`, no formato de `lexico.schema.json`. `formas` (grafias),
`exclusoes` (o filme, a estação, o bairro), `categorias` (facetas: evento, lugar, vítimas,
desdobramento jurídico, memória), `contexto` (o que separa o evento de outros usos). O
catálogo guarda `lexico_versao` em cada linha; quando as **categorias** mudam, reclassifica-se
pelas chaves já gravadas; quando as **formas** mudam, baixa-se de novo (a cópia de referência
já é conhecida, então custa só rede).

## Ordem de trabalho

1. **Primeira varredura** com o `config.json` atual, desde 02/10/1992: fontes pequenas de
   uma vez; grandes por fatias, várias rodadas (trocar o `cron` para diário enquanto durar).
   O Wayback só alcança 1996 em diante; o que há de 1992 a 1995 vem pela data de publicação
   (Crossref, OpenAlex) e pela Hemeroteca (`lista`).
2. **`sondar`** os prefixos dos veículos grandes e ajustar: prefixo com mais de ~600 blocos
   deve ser dividido.
3. **Domínios candidatos** apontados pela Wikipédia viram fontes `wayback`/`topico`
   (decisão da pesquisa; a lista sai no catálogo pela coluna `dominio`).
4. **Léxico real** no lugar do provisório.
5. **Media Cloud e OAI-PMH**: imprensa pelo texto no passado; estrato acadêmico com três canais.
6. **Common Crawl pelo texto**, se a estimativa mostrar `f1` alto e cobertura baixa.
7. **Release trimestral** do catálogo com DOI (Zenodo) e exportação Dublin Core.

## Decisões que são da pesquisa, não do código

- **Onde mora o corpus.** *Decidido em 04/10/2026, mantido:* catálogo CSV, sem texto. O preço
  é conhecido e agora menor: a cópia de referência fica anotada, então "baixar de novo" é barato.
- **O que se publica.** URL, título, data, cópia de referência, chaves do léxico. Nunca o texto.
- **Pessoas.** Ver [`pessoas.md`](pessoas.md). O catálogo descreve documentos, não pessoas.
- **SavePageNow.** Arquivar o que ainda não tem cópia? Provavelmente sim, só para nível 3;
  exige chave do Internet Archive e cota. Não implementado até a decisão.
