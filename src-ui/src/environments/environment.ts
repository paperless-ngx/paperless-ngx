// This file can be replaced during build by using the `fileReplacements` array.
// `ng build --configuration production` replaces `environment.ts` with `environment.prod.ts`.
// The list of file replacements can be found in `angular.json`.

export const DEFAULT_APP_TITLE = 'Paperless-ngx'

export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000/api/',
  apiVersion: '10',
  appTitle: DEFAULT_APP_TITLE,
  tag: 'dev',
  version: 'DEVELOPMENT',
  webSocketHost: 'localhost:8000',
  webSocketProtocol: 'ws:',
  webSocketBaseUrl: '/ws/',
}
