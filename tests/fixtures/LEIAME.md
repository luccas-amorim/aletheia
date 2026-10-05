# Fixtures

Os testes rodam sem rede, contra estes arquivos. São **sintéticos**: imitam o formato
documentado de cada origem, sem terem sido gravados dela, porque o ambiente em que o
motor foi escrito bloqueava as fontes. Cada um deve ser trocado por uma resposta real,
gravada, na primeira rodada com rede.

| Arquivo | Imita |
|---|---|
| `rss/feed.xml`, `rss/atom.xml` | RSS 2.0 de um veículo e Atom 1.0 de um repositório |
| `rss/materia-carandiru.html` | matéria em windows-1252 declarado como iso-8859-1 |
| `rss/materia-outra.html`, `rss/erro-200.html` | matéria sem relação com o léxico; página de erro servida com 200 |
| `wayback/cdx-p1.json`, `cdx-p2.json` | respostas do servidor CDX em JSON, a primeira com chave de retomada |
| `wayback/captura.html`, `nao-arquivada.html` | cópia arquivada (modo `id_`) e a página de "não arquivada" servida com 200 |
| `openalex/p1.json`, `p2.json` | `/works` com resumo em índice invertido e paginação por cursor |
| `gdelt/dia.json` | `artlist` em JSON do DOC 2.0 |
| `lexico-carandiru.json` | léxico de amostra para os testes; o real é `lexico.json`, na raiz |
| `lexico-exemplo.json` | léxico mínimo de outro domínio, para os testes de formato |

Acrescentados com a Alétheia (também sintéticos):

| Arquivo | Imita |
|---|---|
| `topico/pagina1.html`, `pagina2.html` | duas páginas de uma tag de veículo, com navegação, link externo e paginação |
| `wikipedia/extlinks-p1.json`, `p2.json` | `prop=extlinks` da API do MediaWiki, com `continue` |
| `crossref/p1.json`, `p2.json` | `/works` com resumo em JATS e cursor |
| `ia/p1.json` | `advancedsearch.php` do Internet Archive em JSON |
