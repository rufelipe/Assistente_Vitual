# Assistente YODA — Google Workspace Add-on

Esta pasta agora contém a versão do YODA preparada para funcionar como **Google Workspace Add-on para Google Sheets**.

## O que mudou

A versão antiga era um script vinculado a cada planilha e exigia:

- Extensões > Apps Script;
- copiar o Code.gs;
- copiar o YODA.html;
- configurar gatilho.

A nova versão usa o modelo de **Google Workspace Add-on**. O projeto pode ser instalado uma vez na conta e depois usado em diferentes planilhas, sem copiar código para cada arquivo.

A interface usa o modelo de Cards do Google Workspace Add-ons. Isso significa que ela aparece no painel de complementos do Google Sheets; não é um HTML livre sobre a grade da planilha.

## Arquivos

- `Code.gs`: lógica do add-on, interface e integração com a API.
- `appsscript.json`: manifesto do Google Workspace Add-on.
- `YODA.html`: versão HTML antiga, mantida como referência/compatibilidade e não usada pelo novo add-on.

## API

O add-on envia perguntas para:

`https://assistente-virtual-api.onrender.com/api/chat`

O payload inclui:

- `message`: pergunta do usuário;
- `sheet_context`: nome da planilha, URL, aba, intervalo e até 200 linhas exibidas da aba ativa.

## Próximos passos

1. Abrir o projeto no Google Apps Script como projeto independente/standalone.
2. Ativar a exibição do arquivo `appsscript.json` no editor.
3. Copiar `Code.gs` e `appsscript.json` deste diretório.
4. Salvar o projeto e autorizar os escopos solicitados.
5. Criar uma implantação de teste do Google Workspace Add-on.
6. Instalar o add-on na conta de teste.
7. Abrir uma planilha e testar o YODA.
8. Depois dos testes, podemos preparar a distribuição privada para a organização ou publicação no Google Workspace Marketplace.

## Observação importante

A versão de Add-on não usa `SpreadsheetApp.getActiveSpreadsheet()` como um script preso a uma única planilha. A função é executada no contexto do Google Sheets em que o add-on está aberto e usa a planilha/aba ativa para montar o contexto enviado à API.

## Alertas

O antigo alerta de edição via polling HTML não faz parte da primeira versão do Add-on, porque a interface de Cards não executa JavaScript de navegador como o antigo `YODA.html`.

Podemos implementar alertas de outra forma na próxima etapa, inclusive usando automações/trigger e notificações compatíveis com o Google Workspace.
