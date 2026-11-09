# Google Sheets — Assistente Virtual

Esta branch adiciona uma integração inicial com uma planilha Google Sheets privada.

## Como funciona

A Assistente consulta a planilha pela Google Sheets API e, enquanto a interface estiver aberta, verifica alterações a cada 5 segundos. Quando detecta mudança, mostra um alerta visual no próprio painel, sem som.

## Configuração no Google Cloud

1. Crie ou selecione um projeto no Google Cloud.
2. Ative a Google Sheets API.
3. Crie uma Service Account.
4. Gere uma chave JSON para a Service Account.
5. Compartilhe a planilha com o e-mail da Service Account como Viewer.

A Service Account deve ter acesso somente à planilha necessária.

## Configuração no Render

Defina:

- `GOOGLE_SHEET_ID`: `1BgEhjUlOrXUBeusjycfSH8LA2wEUIJxuxLvX0RNe1dE`
- `GOOGLE_SHEET_RANGE`: intervalo da aba que será monitorada, por exemplo `A:Z` ou `Página1!A:Z`
- `GOOGLE_SERVICE_ACCOUNT_JSON`: conteúdo completo do JSON da chave da Service Account.

Nunca coloque a chave JSON no GitHub.

## Observação sobre tempo real

A primeira versão usa polling de 5 segundos para detectar alterações. Isso é "quase em tempo real" e funciona enquanto a Assistente está aberta. A próxima evolução pode usar Apps Script com gatilho instalável `onEdit` e um canal de eventos para reduzir a latência e registrar alterações com mais contexto.

## Alertas

O alerta informa a célula alterada e o valor anterior/novo. Depois de confirmar a estrutura da planilha, podemos evoluir para mensagens de negócio, por exemplo:

"🔔 O contrato 1111333 foi reagendado de 14:20 para 15:30."

## Teste

Depois de configurar as variáveis no Render, abra a Assistente, aguarde a conexão com o Google Sheets e altere uma célula da planilha. O alerta deve aparecer no painel.
