# Como colocar para rodar, passo a passo

Tudo roda de graça no GitHub Actions; só o primeiro passo precisa da sua máquina.

## 1. Subir o repositório

```bash
unzip aletheia.zip && cd aletheia
git init -b main
git add -A
git commit -m "Alétheia 0.2.0"
git remote add origin https://github.com/luccas-amorim/aletheia.git
git push -u origin main
```

O primeiro `push` dispara a CI (`.github/workflows/ci.yml`): lint, formatação, validação do
léxico e da configuração, 124 testes em Python 3.11, 3.12 e 3.13. Ela precisa estar verde
antes do passo seguinte.

## 2. Configurar o repositório no GitHub

Em **Settings** do repositório:

1. **Secrets and variables → Actions → New repository secret**:
   - `OPENALEX_API_KEY`: chave gratuita, pedida em <https://openalex.org> (sem ela, só o
     canal `openalex` falha; os outros rodam).
   - `CROSSREF_MAILTO` (opcional): um e-mail para o *polite pool* do Crossref. Nunca aparece
     em relatório ou log; o cliente HTTP redige esse parâmetro.
2. **Pages → Build and deployment**: Source = *Deploy from a branch*; Branch = `main`,
   pasta `/ (root)`. A página `index.html` lê `catalogo.csv` e `estimativa.md` do próprio
   repositório e é republicada a cada commit do robô.
3. **Actions → General → Workflow permissions**: se o primeiro `push` do robô falhar com
   erro de permissão, marque *Read and write permissions*. O workflow já pede
   `contents: write`; a configuração do repositório não pode negá-la.

## 3. Primeira rodada: uma fonte pequena, à mão

Em **Actions → Rodada → Run workflow**, preencha `fonte` = `wayback:ponte` e `desde` =
`1992-10-02`. Deixe terminar (cerca de dez minutos: 15 requisições por minuto ao Wayback).
Ao fim:

- `catalogo.csv` deve ter dezenas de linhas, com título, data da captura e `snapshot`;
- `vistas.csv` deve ter uma linha por observação;
- `saidas/<rodada>/relatorio-resumo.md` lista o que entrou, o que pede leitura e o que falhou;
- `estado/wayback_ponte.json` guarda o que foi visto e `ultima_rodada`.

Repita com `fonte` = `crossref:carandiru` e `fonte` = `topico:agenciabrasil` para exercitar
um canal acadêmico e um de página de tópico. Se as três rodadas ficarem verdes, o
encanamento está certo.

## 4. Varredura do passado: todas as fontes, várias rodadas

1. Em **Actions → Rodada → Run workflow**, deixe `fonte` vazio e `desde` vazio: cada fonte
   usa o `desde` do `config.json` (02/10/1992) na primeira vez.
2. Os veículos grandes (`wayback:folha`, `estadao`, `oglobo`, `g1`, `uol`, `bbc`, `elpais`,
   `intercept`, `usp`, `unicamp`) são lidos por **fatias** `prefixo × ano`, no máximo
   `fatias_por_rodada` (60) por rodada. O relatório diz quantas fatias ficaram para a
   próxima ("Listagens que continuam na próxima rodada"). Enquanto houver, rode de novo:
   troque o `cron` de `rodada.yml` para diário (`"17 9 * * *"`) ou dispare à mão.
3. Quando nenhuma fonte reportar fatias pendentes, a varredura acabou. Volte o `cron` para
   semanal (`"17 9 * * 1"`).

Cada fonte é comitada ao terminar. Se o job estourar os 340 minutos, nada se perde: a rodada
seguinte continua da fatia seguinte.

## 5. Calibrar os prefixos do Wayback

Os prefixos de seção em `config.json` são um ponto de partida. Para medir cada um:

```bash
aletheia sondar --config config.json --fonte wayback:folha
```

O comando imprime quantos blocos de índice o CDX precisa varrer por prefixo. Acima de ~600,
divida o prefixo em seções menores; prefixo com zero achados depois de uma varredura
completa provavelmente não existe mais no veículo (confira a URL ao vivo). A Wikipédia
(`wikipedia:verbetes`, `wikipedia:en`) aponta domínios ainda fora da lista: eles aparecem
na coluna `dominio` do catálogo e podem virar novas fontes `wayback` ou `topico`.

## 6. Operação semanal

Toda segunda-feira, 06:17 de Brasília, o robô roda sozinho. Depois de cada rodada:

1. Leia `saidas/<rodada>/relatorio-resumo.md`. Três seções pedem ação:
   - **Fontes que falharam**: o motivo está nomeado (404 de página de tag, 403 de
     `robots.txt`, timeout do CDX). Fonte que falha três semanas seguidas deve ser revista
     ou retirada do `config.json`.
   - **Pede juízo**: itens de nível 2, com o trecho que decidiu. Eles estão em `vistas.csv`
     (contam para a estimativa) mas **não** no catálogo. Hoje o caminho para aceitá-los é
     refinar o léxico (uma forma, uma exclusão, um marcador de contexto) e rodar de novo a
     fonte com `--sem-estado`; como o texto não é guardado, não há `retriar` sem rede.
     Um comando de aceite manual é a próxima melhoria do motor.
   - **Falhas de captura ou de integridade**: ficam pendentes e voltam sozinhas.
2. Olhe `estimativa.md`: documentos observados, piso de Chao por estrato, pares comparáveis,
   curva de acumulação. [Como ler](estimativa.md).
3. Pedidos de remoção chegam por issue; a decisão vai para o registro em
   [`pessoas.md`](pessoas.md).

## 7. Trocar o léxico

O `lexico.json` atual é **provisório**. Quando o da pesquisa existir:

```bash
aletheia validar-lexico lexico.json
```

Comite e pronto: as rodadas seguintes já o aplicam, e `lexico_versao` no catálogo diz o que
cada linha "viu". Se as **formas** mudaram, o que já foi varrido precisa ser lido de novo
(`Run workflow` com `desde` = `1992-10-02`, uma fonte por vez; o estado é preservado e as
fatias concluídas não se repetem, então o custo é só o da releitura das páginas).

## 8. Rodar na sua máquina

```bash
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e ".[dev]"
aletheia validar-config config.json
aletheia rodar --config config.json --fonte wayback:ponte --desde 2021-01-01
aletheia estimar --config config.json
pytest -q
```

Isso grava em `catalogo.csv`, `vistas.csv`, `estado/` e `saidas/` do próprio diretório, como
o robô faria. Para ensaiar sem sujar o repositório, copie `config.json` e `lexico.json` para
outra pasta e rode lá. Em máquina corporativa com inspeção TLS, aponte o Python para a
cadeia de certificados do sistema em vez de desligar a verificação (macOS):

```bash
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain > /tmp/ca.pem
security find-certificate -a -p /Library/Keychains/System.keychain >> /tmp/ca.pem
export SSL_CERT_FILE=/tmp/ca.pem
```

## 9. O que ainda não está feito

- Aceite manual de itens "pede juízo" (hoje, só via léxico).
- Canais Media Cloud, OAI-PMH (BDTD, SciELO), YouTube e Common Crawl pelo texto
  ([`plano.md`](plano.md)).
- SavePageNow para arquivar URLs vivas sem cópia (decisão da pesquisa; exige chave).
- Release trimestral com DOI no Zenodo e exportação Dublin Core.
