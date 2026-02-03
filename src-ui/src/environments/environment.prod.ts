const base_url = new URL(document.baseURI)

export const environment = {
  production: true,
  apiBaseUrl: document.baseURI + 'api/',
  apiVersion: '9', // match src/paperless/settings.py
  appTitle: 'Paperless-ngx',
  tag: 'prod',
  version: '2.20.6',
  webSocketHost: window.location.host,
  webSocketProtocol: window.location.protocol == 'https:' ? 'wss:' : 'ws:',
  webSocketBaseUrl: base_url.pathname + 'ws/',
}
