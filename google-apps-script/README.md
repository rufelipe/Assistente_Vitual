# YODA flutuante dentro do Google Sheets

O projeto usa um diálogo não modal do Apps Script para apresentar o YODA em uma janela independente. A janela pode ser minimizada até ficar somente com o avatar e reaberta ao clicar nele. O Google controla a posição inicial e a moldura externa do diálogo; não é possível injetar um botão flutuante diretamente sobre a grade da planilha com Apps Script.

## Instalação

1. Abra a planilha e vá em Extensões > Apps Script.
2. No arquivo `Code.gs`, substitua todo o conteúdo pelo arquivo deste diretório.
3. No arquivo HTML chamado `YODA` (nome exibido como `YODA.html`), substitua todo o conteúdo pelo arquivo deste diretório.
4. Salve os dois arquivos.
5. Execute `onOpen` uma vez, autorize e recarregue a planilha.
6. Use o menu 🤖 YODA > Abrir Assistente.
7. Use o botão de minimizar no cabeçalho para recolher a janela ao avatar; clique no avatar para expandir.

## Alertas de edição

Mantenha o gatilho instalável da função `recordEdit`: Apps Script > Gatilhos > Adicionar gatilho > `recordEdit` > Da planilha > Ao editar. A janela consulta a última alteração a cada 3 segundos e exibe um aviso visual sem som.
