# Quanto da internet o observatório absorve

Duas perguntas diferentes, e é bom não misturá-las:

1. **Quanto existe?** Ninguém sabe, nem o Google. O número de resultados que um buscador
   mostra é estimativa dele, inclui o filme de 2003, a estação de metrô, o bairro,
   republicações e páginas de listagem, e não pagina além de algumas centenas.
2. **Quanto, do que existe, os nossos canais alcançam?** Isso se mede, por captura e
   recaptura entre canais (`aletheia estimar`), e é o número que o `estimativa.md` da raiz
   publica depois de cada rodada.

## A matriz: `vistas.csv`

Uma linha por **observação**: documento (`id` da URL normalizada), canal (`wayback`,
`topico`, `gdelt`…), fonte, rodada, nível, data e hash do texto. O mesmo documento visto
por dois canais tem duas linhas; duas URLs com o mesmo texto (`hash_texto` igual) contam
como um documento. É dessa matriz que saem `n1`, `n2`, `m`, `f1`, `f2` e a curva.

## O que cada canal alcança, e o que não alcança

| Canal | Alcança | Não alcança |
|---|---|---|
| **Wayback por prefixo** | toda página arquivada daqueles prefixos com `carandiru` **no endereço**, inclusive as mortas | página sem a palavra no endereço (comum até meados dos anos 2000); seção fora da lista; página nunca arquivada |
| **Tópico** | o que a redação marcou com a tag, com ou sem a palavra no endereço | veículo sem página de tag; matéria não etiquetada |
| **GDELT** | notícia de qualquer veículo do mundo, pelo texto, nos **últimos ~90 dias** | todo o passado |
| **OpenAlex / Crossref** | trabalho com o termo no título, resumo ou texto indexado | trabalho sem DOI nem repositório indexado |
| **IA** | item depositado com o termo em título, descrição ou texto | o que não foi depositado |
| **Wikipédia** | o que algum editor citou | o resto; é semente |

Pontos cegos de todos eles hoje: **redes sociais**, **vídeo** (YouTube: canal possível com
chave), **acervos pagos**, **PDF em endereço opaco**, **imprensa de 1992 a ~1998** (vive na
Hemeroteca Digital: entra por `lista`), **livros** fora do IA.

## Estratos

Captura e recaptura supõe que os canais olham para a mesma população. Por isso cada fonte
declara um `estrato` em `config.json`, e `validar-config` recusa estrato desconhecido:

| Estrato | Fontes |
|---|---|
| `imprensa` | wayback dos veículos, topico, gdelt, rss |
| `juridico` | wayback de conjur, migalhas, tjsp, stj, mpsp |
| `academico` | openalex, crossref, wayback de usp, unicamp, scielo |
| `memoria` | ia |
| `imprensa-historica` | lista (Hemeroteca) |
| `geral` | wikipedia (semente; não entra em estimativa de estrato) |

Na primeira versão, tribunais e universidades estavam marcados como `imprensa`, e a
estimativa comparava populações diferentes. Corrigido.

## Janelas

O GDELT só vê ~90 dias. Comparado com o Wayback sem alinhar a janela, quase tudo do Wayback
seria "visto por um canal só" e o piso explodiria. Regra do código: par que envolva canal
de janela curta só entra no piso quando `estimar --desde <data>` restringe todos os canais
à mesma janela; fora disso, o relatório mostra o par como **não comparável**.

## Hipóteses para a primeira medição

Palpites declarados como palpites, para serem derrubados pelos números.

- **Imprensa, pelo Wayback fatiado:** centenas de URLs por grande veículo, concentradas nos
  picos (aniversários de 2 de outubro, júris de 2013 e 2014, anulação em 2016, STJ em 2021,
  indulto). Dezenas nos pequenos. Total do estrato na casa dos **milhares**.
- **Tópico × Wayback:** sobreposição alta nos veículos que têm tag; é o primeiro par que
  deve dar um piso crível para imprensa.
- **Acadêmico:** algumas centenas de trabalhos; OpenAlex × Crossref com sobreposição alta
  (ambos indexam DOIs), portanto piso perto do observado: leia como "o que tem DOI está bem
  servido", não como "achamos tudo".
- **Ponto cego dominante:** páginas sem a palavra no endereço e sem tag. Se a hipótese
  estiver certa, `f1` alto e cobertura baixa em imprensa; o remédio é Media Cloud e, depois,
  Common Crawl pelo texto.

## Como ler o `estimativa.md` da raiz

- **Observados** é contagem: documentos distintos do estrato.
- **Piso (Chao)** é o mínimo que deve existir, dado o que os canais acharam e o quanto se
  sobrepuseram. É piso porque os canais não são independentes.
- **Cobertura, no máximo X%** é observados ÷ piso.
- **Curva de acumulação:** quantos documentos novos cada rodada trouxe. Saturação é a curva
  achatar **quando um canal novo entra**.

## Regras de decisão

| Se a medição mostrar | Então |
|---|---|
| cobertura acima de ~80% num estrato, e canal novo trazendo poucos documentos | o estrato está bem servido; manter a vigilância semanal |
| `f1` alto e cobertura abaixo de ~50% | falta um canal que veja o que os outros não veem (Media Cloud, Common Crawl pelo texto) |
| um prefixo do Wayback com zero achados | conferir com `sondar` se o prefixo existe; o veículo pode não usar a palavra no endereço |
| estrato com um canal comparável só | sem estimativa: acrescentar um segundo canal antes de afirmar qualquer cobertura |
