const ASSISTANT_API_URL = 'https://assistente-virtual-api.onrender.com';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('🤖 YODA')
    .addItem('Abrir Assistente', 'showYoda')
    .addItem('Configurar Assistente', 'showSetup')
    .addToUi();
}

function showYoda() {
  SpreadsheetApp.getUi().showSidebar(
    HtmlService.createHtmlOutputFromFile('YODA').setTitle('Assistente YODA')
  );
}

function showSetup() {
  SpreadsheetApp.getUi().showSidebar(
    HtmlService.createHtmlOutput('<div style="font-family:Arial;padding:16px"><h2>🤖 Assistente YODA</h2><p>Use o menu <b>🤖 YODA → Abrir Assistente</b>.</p><p>API: <code>'+ASSISTANT_API_URL+'</code></p></div>').setTitle('Configuração YODA')
  );
}

function getSheetContext() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();
  return {spreadsheetName:ss.getName(), sheetName:sheet.getName(), values:sheet.getDataRange().getDisplayValues().slice(0,200), updatedAt:new Date().toISOString()};
}

function askYoda(message) {
  const response = UrlFetchApp.fetch(ASSISTANT_API_URL + '/api/chat', {
    method:'post', contentType:'application/json',
    payload:JSON.stringify({message:String(message||''), sheet_context:getSheetContext()}),
    muteHttpExceptions:true
  });
  if(response.getResponseCode()<200 || response.getResponseCode()>=300) throw new Error('Assistente retornou HTTP '+response.getResponseCode()+'.');
  return JSON.parse(response.getContentText()).reply || 'Não encontrei uma resposta.';
}

function recordEdit(e) {
  if(!e || !e.range) return;
  PropertiesService.getDocumentProperties().setProperty('YODA_LAST_EDIT', JSON.stringify({
    sheet:e.range.getSheet().getName(), cell:e.range.getA1Notation(),
    oldValue:e.oldValue||'', value:e.value||'', at:new Date().toISOString()
  }));
}

function getLastEdit() {
  const raw=PropertiesService.getDocumentProperties().getProperty('YODA_LAST_EDIT');
  return raw ? JSON.parse(raw) : null;
}
