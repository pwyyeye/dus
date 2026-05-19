import { contextBridge, ipcRenderer } from "electron";
import { electronAPI } from "@electron-toolkit/preload";
import type { BridgeStatus, DaemonPrefs } from "../shared/daemon-types";

// Sync app info fetch
function fetchAppInfo(): {
  version: string;
  os: "macos" | "windows" | "linux" | "unknown";
} {
  try {
    const info = ipcRenderer.sendSync("app:get-info") as
      | { version: string; os: "macos" | "windows" | "linux" | "unknown" }
      | undefined;
    if (info && typeof info.version === "string") return info;
  } catch {
    // fall through
  }
  const p = process.platform;
  const os =
    p === "darwin" ? "macos" : p === "win32" ? "windows" : p === "linux" ? "linux" : "unknown";
  return { version: "unknown", os };
}

const appInfo = fetchAppInfo();

const desktopAPI = {
  appInfo,
  openExternal: (url: string) => ipcRenderer.invoke("shell:openExternal", url),
};

const bridgeAPI = {
  start: (): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke("bridge:start"),
  stop: (): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke("bridge:stop"),
  restart: (): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke("bridge:restart"),
  getStatus: (): Promise<BridgeStatus> =>
    ipcRenderer.invoke("bridge:get-status"),
  onStatusChange: (callback: (status: BridgeStatus) => void) => {
    const handler = (_: unknown, status: BridgeStatus) => callback(status);
    ipcRenderer.on("bridge:status", handler);
    return () => ipcRenderer.removeListener("bridge:status", handler);
  },
  getPrefs: (): Promise<DaemonPrefs> =>
    ipcRenderer.invoke("bridge:get-prefs"),
  setPrefs: (
    prefs: Partial<DaemonPrefs>
  ): Promise<DaemonPrefs> =>
    ipcRenderer.invoke("bridge:set-prefs", prefs),
  autoStart: (): Promise<void> =>
    ipcRenderer.invoke("bridge:auto-start"),
  onLogLine: (callback: (line: string) => void) => {
    const handler = (_: unknown, line: string) => callback(line);
    ipcRenderer.on("bridge:log-line", handler);
    return () => ipcRenderer.removeListener("bridge:log-line", handler);
  },
};

if (process.contextIsolated) {
  contextBridge.exposeInMainWorld("electron", electronAPI);
  contextBridge.exposeInMainWorld("desktopAPI", desktopAPI);
  contextBridge.exposeInMainWorld("bridgeAPI", bridgeAPI);
} else {
  // @ts-expect-error fallback for non-isolated context
  window.electron = electronAPI;
  // @ts-expect-error fallback
  window.desktopAPI = desktopAPI;
  // @ts-expect-error fallback
  window.bridgeAPI = bridgeAPI;
}
