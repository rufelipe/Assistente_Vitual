// Cole este código no Apps Script da planilha se quiser um caminho
// de notificação por evento no futuro. A versão inicial da Assistente
// usa polling seguro pela API para detectar alterações sem precisar
// publicar a planilha.
// 
// O código abaixo é apenas um modelo e não é ativado automaticamente.
// function onEdit(e) {
//   const url = "https://SEU-ENDPOINT/api/sheets/webhook";
//   UrlFetchApp.fetch(url, {
//     method: "post",
//     contentType: "application/json",
//     payload: JSON.stringify({
//       spreadsheetId: e.source.getId(),
//       sheet: e.range.getSheet().getName(),
//       row: e.range.getRow(),
//       column: e.range.getColumn(),
//       oldValue: e.oldValue || "",
//       value: e.value || ""
//     }),
//     muteHttpExceptions: true
//   });
// }
