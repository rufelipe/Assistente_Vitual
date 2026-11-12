const ASSISTANT_API_URL = 'https://assistente-virtual-api.onrender.com';

function onHomepage(e) {
  return buildHomeCard();
}

function buildHomeCard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss ? ss.getActiveSheet() : null;
  const spreadsheetName = ss ? ss.getName() : 'Google Sheets';
  const sheetName = sheet ? sheet.getName() : 'Aba atual';

  const header = CardService.newCardHeader()
    .setTitle('Assistente YODA')
    .setSubtitle('Assistente Virtual para Google Sheets')
    .setImageUrl('https://raw.githubusercontent.com/rufelipe/Assistente_Vitual/feature/google-sheets-alerts/assets/baby-yoda-head.png')
    .setImageStyle(CardService.newImageStyle().setImageType(CardService.ImageType.CIRCLE));

  const context = CardService.newTextParagraph()
    .setText('<b>Planilha:</b> ' + escapeHtml(spreadsheetName) + '<br><b>Aba:</b> ' + escapeHtml(sheetName) + '<br><font color="#5f6368">O YODA pode consultar os dados da aba atual e conversar com sua Assistente Virtual.</font>');

  const input = CardService.newTextInput()
    .setFieldName('message')
    .setTitle('Pergunte ao YODA')
    .setHint('Ex.: quem devo ligar primeiro?');

  const send = CardService.newTextButton()
    .setText('Enviar pergunta')
    .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
    .setOnClickAction(CardService.newAction().setFunctionName('askYodaAction'));

  const openChat = CardService.newTextButton()
    .setText('Abrir conversa')
    .setOnClickAction(CardService.newAction().setFunctionName('openChat'));

  const section = CardService.newCardSection()
    .addWidget(context)
    .addWidget(input)
    .addWidget(send)
    .addWidget(openChat);

  return CardService.newCardBuilder()
    .setHeader(header)
    .addSection(section)
    .build();
}

function openChat() {
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(buildChatCard('')))
    .build();
}

function buildChatCard(reply) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss ? ss.getActiveSheet() : null;
  const spreadsheetName = ss ? ss.getName() : 'Google Sheets';
  const sheetName = sheet ? sheet.getName() : 'Aba atual';

  const header = CardService.newCardHeader()
    .setTitle('YODA • Conversa')
    .setSubtitle(spreadsheetName + ' • ' + sheetName)
    .setImageUrl('https://raw.githubusercontent.com/rufelipe/Assistente_Vitual/feature/google-sheets-alerts/assets/baby-yoda-head.png')
    .setImageStyle(CardService.newImageStyle().setImageType(CardService.ImageType.CIRCLE));

  const section = CardService.newCardSection();

  if (reply) {
    section
      .addWidget(CardService.newTextParagraph().setText('<b>YODA:</b> ' + escapeHtml(reply)))
      .addWidget(CardService.newDivider());
  } else {
    section.addWidget(CardService.newTextParagraph().setText('Olá! Estou conectado à planilha atual. Faça uma pergunta sobre os dados da aba.'));
  }

  section
    .addWidget(CardService.newTextInput()
      .setFieldName('message')
      .setTitle('Sua pergunta')
      .setHint('Digite uma nova pergunta...'))
    .addWidget(CardService.newTextButton()
      .setText('Enviar')
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
      .setOnClickAction(CardService.newAction().setFunctionName('askYodaAction')))
    .addWidget(CardService.newTextButton()
      .setText('Voltar')
      .setOnClickAction(CardService.newAction().setFunctionName('backHome')));

  return CardService.newCardBuilder().setHeader(header).addSection(section).build();
}

function backHome() {
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().popToRoot())
    .build();
}

function askYodaAction(e) {
  const message = getFormValue(e, 'message');
  if (!message) {
    return CardService.newActionResponseBuilder()
      .setNotification(CardService.newNotification().setText('Digite uma pergunta antes de enviar.'))
      .build();
  }

  try {
    const reply = askYoda(message);
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(buildChatCard(reply)))
      .build();
  } catch (error) {
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(buildChatCard('Não consegui consultar a Assistente agora. ' + error.message)))
      .build();
  }
}

function askYoda(message) {
  const response = UrlFetchApp.fetch(ASSISTANT_API_URL + '/api/chat', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      message: String(message || ''),
      sheet_context: getSheetContext()
    }),
    muteHttpExceptions: true
  });

  const status = response.getResponseCode();
  const body = response.getContentText();

  if (status < 200 || status >= 300) {
    throw new Error('Assistente retornou HTTP ' + status + '.');
  }

  let data;
  try {
    data = JSON.parse(body);
  } catch (error) {
    throw new Error('A resposta da Assistente não veio em JSON válido.');
  }

  return data.reply || 'Não encontrei uma resposta.';
}

function getSheetContext() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) {
    return {
      spreadsheetName: '',
      sheetName: '',
      values: [],
      updatedAt: new Date().toISOString()
    };
  }

  const sheet = ss.getActiveSheet();
  const dataRange = sheet.getDataRange();
  const values = dataRange.getDisplayValues().slice(0, 200);

  return {
    spreadsheetName: ss.getName(),
    spreadsheetUrl: ss.getUrl(),
    sheetName: sheet.getName(),
    range: dataRange.getA1Notation(),
    values: values,
    updatedAt: new Date().toISOString()
  };
}

function getFormValue(e, fieldName) {
  try {
    const values = e.commonEventObject.formInputs[fieldName].stringInputs.value;
    return values && values.length ? String(values[0]).trim() : '';
  } catch (error) {
    return e && e.parameters && e.parameters[fieldName]
      ? String(e.parameters[fieldName]).trim()
      : '';
  }
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Mantidos para compatibilidade com a versão antiga vinculada à planilha.
// O novo add-on não depende dessas funções para funcionar.
function recordEdit(e) {
  if (!e || !e.range) return;
  PropertiesService.getDocumentProperties().setProperty('YODA_LAST_EDIT', JSON.stringify({
    sheet: e.range.getSheet().getName(),
    cell: e.range.getA1Notation(),
    oldValue: e.oldValue || '',
    value: e.value || '',
    at: new Date().toISOString()
  }));
}

function getLastEdit() {
  const raw = PropertiesService.getDocumentProperties().getProperty('YODA_LAST_EDIT');
  return raw ? JSON.parse(raw) : null;
}
