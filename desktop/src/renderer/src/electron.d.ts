import type { BridgeStatus, DaemonPrefs } from "../../shared/daemon-types";

interface DesktopAPI {
  appInfo: {
    version: string;
    os: "macos" | "windows" | "linux" | "unknown";
  };
  openExternal: (url: string) => Promise<void>;
}

interface BridgeAPI {
  start: () => Promise<{ success: boolean; error?: string }>;
  stop: () => Promise<{ success: boolean; error?: string }>;
  restart: () => Promise<{ success: boolean; error?: string }>;
  getStatus: () => Promise<BridgeStatus>;
  onStatusChange: (callback: (status: BridgeStatus) => void) => () => void;
  getPrefs: () => Promise<DaemonPrefs>;
  setPrefs: (prefs: Partial<DaemonPrefs>) => Promise<DaemonPrefs>;
  autoStart: () => Promise<void>;
  onLogLine: (callback: (line: string) => void) => () => void;
}

declare global {
  interface Window {
    desktopAPI: DesktopAPI;
    bridgeAPI: BridgeAPI;
  }
}
