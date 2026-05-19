export interface RuntimeConfig {
  schemaVersion: 1;
  apiUrl: string;
  wsUrl: string;
}

export interface RuntimeConfigError {
  message: string;
}

export type RuntimeConfigResult =
  | { ok: true; config: RuntimeConfig }
  | { ok: false; error: RuntimeConfigError };

export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = Object.freeze({
  schemaVersion: 1,
  apiUrl: "http://localhost:8000/api/v1",
  wsUrl: "ws://localhost:8000/ws",
});

export function deriveWsUrl(apiUrl: string): string {
  const url = new URL(apiUrl);
  if (url.protocol === "https:") url.protocol = "wss:";
  else if (url.protocol === "http:") url.protocol = "ws:";
  url.pathname = url.pathname.replace(/\/+$/, "") + "/ws";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/+$/, "");
}
