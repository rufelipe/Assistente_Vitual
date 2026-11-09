# YODA dentro do Google Sheets

O Google Sheets permite que um script vinculado à planilha crie menus e barras laterais. Esta implementação adiciona o YODA como uma barra lateral dentro da própria planilha.

## Instalação

1. Abra a planilha.
2. Vá em Extensões > Apps Script.
3. Crie um arquivo chamado Code.gs e cole o conteúdo de Code.gs deste repositório.
4. Crie um arquivo HTML chamado YODA e cole o conteúdo de YODA.html.
5. Salve.
6. Execute onOpen uma vez e autorize o projeto.
7. Volte à planilha e recarregue.
8. Use o menu 🤖 YODA > Abrir Assistente.

## Alertas de edição

Crie um gatilho instalável para a função recordEdit:
Apps Script > Triggers/Gatilhos > Add Trigger > recordEdit > From spreadsheet > On edit.

A sidebar verifica a cada 3 segundos se houve uma nova edição e exibe um alerta visual sem som.

A próxima etapa pode transformar a alteração de célula em uma mensagem de negócio, por exemplo: O contrato 1111333 foi reagendado de 14:20 para 15:30.
