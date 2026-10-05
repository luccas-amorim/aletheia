# Mudanças

## 0.2.0 — 2026-10-05

Primeira versão com o nome Alétheia. Reconstrução do motor do Observatório do Massacre do
Carandiru (antes `observatory`), com as correções e o desenho do plano de 05/10/2026.

- **Segurança**: toda URL em erro e log passa por `redigir()`; `api_key`, `token` e afins nunca
  chegam ao relatório comitado.
- **Rede**: `IncompleteRead`, `RemoteDisconnected` e `BadStatusLine` são retentados; não há mais
  pausa depois da última tentativa.
- **Wayback fatiado**: consultas por `prefixo × ano`, paginadas, com progresso por fatia gravado
  no estado; `fatias_por_rodada` limita cada rodada; `sondar` mede cada prefixo; `excluir` tira
  feed, embed, amp, busca, listagens e mídia do que o filtro de endereço casa.
- **Estado**: gravado mesmo quando a listagem falha; só a data da última rodada deixa de avançar.
  Pendentes não guardam `dados` grandes (texto com nomes).
- **Canais novos**: `topico` (páginas de tag, vivas e arquivadas), `wikipedia` (links externos
  dos verbetes), `crossref`, `ia` (Internet Archive), `lista` (CSV curado).
- **Catálogo v2**: 14 colunas, id pela URL normalizada, snapshot do Wayback, estrato, categorias,
  versão do léxico, título pela manchete da página; dois endereços com o mesmo texto são um
  documento; migra o formato antigo de 3 colunas.
- **Vistas**: `vistas.csv` como matriz de captura e recaptura; `estimar` lê dela, deduplica por
  hash do texto e marca pares não comparáveis (GDELT sem `--desde`).
- **Config**: `validar-config` exige estrato conhecido e prefixo do id igual ao tipo.
- **Página**: `index.html` navega o catálogo no GitHub Pages, sem servidor nem CDN.
- **Janela**: a varredura parte de 02/10/1992; o Wayback corta para 1996 (início do arquivo)
  e informa a janela efetiva.
