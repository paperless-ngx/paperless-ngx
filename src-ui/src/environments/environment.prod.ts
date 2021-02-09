export const environment = {
  production: true,
  apiBaseUrl: "/api/",
  appTitle: "Paperless-ng",
  version: "1.1.1",
  webSocketHost: window.location.host,
  webSocketProtocol: (window.location.protocol == "https:" ? "wss:" : "ws:")
};
