const base_url = new URL(document.baseURI)

export const DEFAULT_APP_TITLE = 'Paperless-ngx'

export const environment = {
  production: true,
  apiBaseUrl: document.baseURI + 'api/',
  apiVersion: '10', // match src/paperless/settings.py
  appTitle: DEFAULT_APP_TITLE,
  tag: 'prod',
  version: '3.0.2',
  webSocketHost: window.location.host,
  webSocketProtocol: window.location.protocol == 'https:' ? 'wss:' : 'ws:',
  webSocketBaseUrl: base_url.pathname + 'ws/',
}
