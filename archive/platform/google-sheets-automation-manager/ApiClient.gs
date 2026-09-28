/**
 * Authenticated calls to the Cloud Run API.
 * - Identity: ScriptApp.getIdentityToken() (Google-signed OIDC token of the
 *   signed-in user; requires the 'openid' and 'userinfo.email' scopes).
 * - Replay protection: every mutating call sends a single-use request ID and a timestamp.
 */
function getApiBaseUrl_() {
  var url = PropertiesService.getScriptProperties().getProperty(UCA.API_URL_PROPERTY);
  if (!url || url.indexOf('https://') !== 0) {
    throw new Error('Script property ' + UCA.API_URL_PROPERTY + ' is not set to the https URL of uca-api. ' +
      'Ask an admin to set it (Extensions → Apps Script → Project Settings → Script Properties).');
  }
  return url.replace(/\/+$/, '');
}

function newRequestId_() {
  return Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '').slice(0, 8);
}

function apiRequest_(method, path, body) {
  var token = ScriptApp.getIdentityToken();
  if (!token) throw new Error('Could not obtain your Google identity token (check the openid scope).');
  var headers = { Authorization: 'Bearer ' + token };
  var upper = String(method).toUpperCase();
  if (upper !== 'GET') {
    headers['X-UCA-Request-Id'] = newRequestId_();
    headers['X-UCA-Timestamp'] = new Date().toISOString();
  }
  var options = { method: upper.toLowerCase(), headers: headers, muteHttpExceptions: true, followRedirects: false };
  if (body !== undefined && body !== null) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }
  var response = UrlFetchApp.fetch(getApiBaseUrl_() + path, options);
  var code = response.getResponseCode();
  var text = response.getContentText();
  var data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { message: text.slice(0, 300) }; }
  if (code >= 400) {
    throw new Error(formatApiError_(code, data));
  }
  data._correlation = (response.getHeaders() || {})['X-Correlation-Id'] || '';
  return data;
}

function formatApiError_(code, data) {
  var parts = ['API error ' + code];
  if (data && data.error_code) parts.push('[' + data.error_code + ']');
  if (data && (data.message || data.detail)) parts.push(String(data.message || JSON.stringify(data.detail)));
  return parts.join(' ');
}

function apiGet_(path, query) {
  var qs = Object.keys(query || {}).map(function (k) {
    return encodeURIComponent(k) + '=' + encodeURIComponent(query[k]);
  }).join('&');
  return apiRequest_('GET', path + (qs ? '?' + qs : ''), null);
}

function apiPost_(path, body) {
  return apiRequest_('POST', path, body || {});
}
