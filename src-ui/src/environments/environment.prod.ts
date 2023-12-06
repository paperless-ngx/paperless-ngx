const base_url = new URL(document.baseURI)

export const environment = {
  production: true,
  baseUrl: base_url,
  apiBaseUrl: `${base_url}api/`,
  apiVersion: '3',
  appTitle: 'Paperless-ngx',
  version: '2.1.0-dev',
  webSocketHost: window.location.host,
  webSocketProtocol: window.location.protocol == 'https:' ? 'wss:' : 'ws:',
  webSocketBaseUrl: base_url.pathname + 'ws/',
}
