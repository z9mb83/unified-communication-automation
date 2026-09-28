/** Builds the AUTOMATION MANAGER menu. Handlers only collect input and call the API. */
function buildAutomationMenu_() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu(UCA.MENU_NAME)
    .addSubMenu(ui.createMenu('EMAIL')
      .addItem('Send Email to Selected Rows', 'menuSendEmailSelected')
      .addItem('Run Existing Email Automation', 'menuRunExistingEmail')
      .addItem('Start Email Automation', 'menuStartEmail')
      .addItem('Stop Email Automation', 'menuStopEmail')
      .addItem('Check Email Status', 'menuEmailStatus'))
    .addSubMenu(ui.createMenu('WHATSAPP')
      .addItem('Send WhatsApp to Selected Rows', 'menuSendWhatsAppSelected')
      .addItem('Select Approved Template', 'menuSelectWaTemplate')
      .addItem('Sync Approved Templates', 'menuSyncWaTemplates')
      .addItem('Start WhatsApp Automation', 'menuStartWhatsApp')
      .addItem('Stop WhatsApp Automation', 'menuStopWhatsApp')
      .addItem('Check WhatsApp Status', 'menuWhatsAppStatus'))
    .addSubMenu(ui.createMenu('SMS')
      .addItem('Send SMS to Selected Rows', 'menuSendSmsSelected')
      .addItem('Select Approved SMS Template', 'menuSelectSmsTemplate')
      .addItem('Start SMS Automation', 'menuStartSms')
      .addItem('Stop SMS Automation', 'menuStopSms'))
    .addSubMenu(ui.createMenu('SYSTEM')
      .addItem('Start All Enabled Automations', 'menuStartAll')
      .addItem('Stop All Automations', 'menuStopAll')
      .addItem('Emergency Stop', 'menuEmergencyStop')
      .addItem('View Job Status', 'menuViewJobStatus')
      .addItem('Validate Configuration', 'menuValidateConfiguration')
      .addSeparator()
      .addItem('Import Consent from Selected Rows', 'menuImportConsent')
      .addItem('Set Up Configuration Tabs', 'setupConfigurationTabs'))
    .addToUi();
}

function guarded_(fn) {
  try { fn(); } catch (error) { showError_(error); }
}

// EMAIL
function menuSendEmailSelected() { guarded_(sendEmailToSelectedRows_); }
function menuRunExistingEmail() { guarded_(runExistingEmailAutomation_); }
function menuStartEmail() { guarded_(function () { startChannel_('email'); }); }
function menuStopEmail() { guarded_(function () { stopChannel_('email'); }); }
function menuEmailStatus() { guarded_(function () { showChannelStatus_('email'); }); }
// WHATSAPP
function menuSendWhatsAppSelected() { guarded_(function () { openTemplateSidebar_('whatsapp'); }); }
function menuSelectWaTemplate() { guarded_(function () { openTemplateSidebar_('whatsapp'); }); }
function menuSyncWaTemplates() { guarded_(syncWhatsAppTemplates_); }
function menuStartWhatsApp() { guarded_(function () { startChannel_('whatsapp'); }); }
function menuStopWhatsApp() { guarded_(function () { stopChannel_('whatsapp'); }); }
function menuWhatsAppStatus() { guarded_(function () { showChannelStatus_('whatsapp'); }); }
// SMS
function menuSendSmsSelected() { guarded_(function () { openTemplateSidebar_('sms'); }); }
function menuSelectSmsTemplate() { guarded_(function () { openTemplateSidebar_('sms'); }); }
function menuStartSms() { guarded_(function () { startChannel_('sms'); }); }
function menuStopSms() { guarded_(function () { stopChannel_('sms'); }); }
// SYSTEM
function menuStartAll() { guarded_(startAll_); }
function menuStopAll() { guarded_(stopAll_); }
function menuEmergencyStop() { guarded_(emergencyStop_); }
function menuViewJobStatus() { guarded_(viewJobStatus_); }
function menuValidateConfiguration() { guarded_(validateConfiguration_); }
function menuImportConsent() { guarded_(importConsentFromSelection_); }
