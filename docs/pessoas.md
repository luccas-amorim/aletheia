# Pessoas: o que o observatório faz e não faz

O massacre tem vítimas com nome, familiares vivos, réus julgados e absolvidos, testemunhas,
jornalistas. Todos aparecem nos documentos que o catálogo aponta. A regra do projeto, escrita
antes do primeiro item, é esta:

**O catálogo descreve documentos, não pessoas.**

Na prática:

1. **Nenhuma coluna de nome.** O catálogo tem endereço, domínio, título como a fonte deu, data,
   cópia de referência, hash do texto e as chaves do léxico. Não há coluna de pessoa, papel ou
   vínculo, e o motor não cruza fontes para montar perfil de ninguém (`docs/plano.md`).
2. **Texto integral não é guardado nem publicado** (`"guardar_texto": false`). O que o robô lê,
   descarta depois de triar. A cópia de referência é a do Internet Archive, sob a política dele.
3. **Trechos nos relatórios** (`saidas/*/relatorio-*.md`, campo `trecho` em `itens.jsonl`) existem
   para auditar a triagem e têm até ~320 caracteres em torno do termo que decidiu. São parte do
   repositório público. Se um trecho expuser alguém de forma desproporcional ao documento de
   origem, é removido a pedido, e a decisão fica registrada abaixo.
4. **Pedidos de remoção ou correção** entram por
   [issue](../.github/ISSUE_TEMPLATE/remocao.md) ou pelo contato do perfil do mantenedor.
   Vítima, familiar ou pessoa citada não precisa provar vínculo para pedir a remoção do título de
   uma linha. Prazo de resposta: 7 dias.
5. **Base legal (LGPD).** O tratamento é de dados já públicos, para pesquisa histórica e
   acadêmica (art. 7º, IV, e art. 4º, II, "b", da Lei 13.709/2018), restrito a metadados de
   documentos, sem decisão automatizada sobre pessoas e sem compartilhamento além do próprio
   repositório público. O controlador é o mantenedor, identificado no perfil do GitHub.

## Registro de decisões

| Data | Linha (`id`) | Pedido | Decisão |
|---|---|---|---|
| | | | |
