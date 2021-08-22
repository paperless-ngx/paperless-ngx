const base_url = new URL(document.baseURI)

export const environment = {
  production: true,
  apiBaseUrl: document.baseURI + "api/",
  apiVersion: "2",
  appTitle: "Paperless-ng",
  version: "1.5.0",
  webSocketHost: window.location.host,
  webSocketProtocol: (window.location.protocol == "https:" ? "wss:" : "ws:"),
  webSocketBaseUrl: base_url.pathname + "ws/",
};
