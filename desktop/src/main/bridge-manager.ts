import { app, ipcMain, BrowserWindow } from "electron";
import { spawn, type ChildProcess } from "child_process";
import { existsSync } from "fs";
import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import { homedir } from "os";
import type { BridgeStatus, DaemonPrefs } from "../shared/daemon-types";

const DEFAULT_HEALTH_PORT = 19514;
const POLL_INTERVAL_MS = 5_000;
const PREFS_PATH = join(homedir(), ".dus", "desktop_prefs.json");

const DEFAULT_PREFS: DaemonPrefs = { autoStart: true, autoStop: false };

let statusPollTimer: ReturnType<typeof setInterval> | null = null;
let currentState: BridgeStatus["state"] = "stopped";
let bridgeProcess: ChildProcess | null = null;
let getMainWindow: () => BrowserWindow | null = () => null;
let operationInProgress = false;

function sendStatus(status: BridgeStatus): void {
  const win = getMainWindow();
  win?.webContents.send("bridge:status", status);
}

async function fetchHealth(): Promise<BridgeStatus> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2_000);
    const res = await fetch(
      `http://127.0.0.1:${DEFAULT_HEALTH_PORT}/health`,
      { signal: controller.signal }
    );
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as Record<string, unknown>;
    currentState = "running";
    const status: BridgeStatus = {
      state: "running",
      pid: data.pid as number | undefined,
      machineId: data.machine_id as string | undefined,
      agents: data.agents as string[] | undefined,
      activeTaskCount: data.active_task_count as number | undefined,
      healthPort: DEFAULT_HEALTH_PORT,
    };
    sendStatus(status);
    return status;
  } catch {
    if (bridgeProcess && bridgeProcess.exitCode === null) {
      currentState = "starting";
    } else {
      currentState = "stopped";
    }
    const status: BridgeStatus = { state: currentState };
    sendStatus(status);
    return status;
  }
}

function startPolling(): void {
  stopPolling();
  statusPollTimer = setInterval(() => fetchHealth(), POLL_INTERVAL_MS);
}

function stopPolling(): void {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

/**
 * Resolve the bridge command, working directory, and environment.
 *
 * Priority order:
 * 1. Bundled standalone binary (PyInstaller, production)
 * 2. Bundled Python venv (production, self-contained)
 * 3. User-local install (~/.dus/bridge/)
 * 4. Dev mode (project root/bridge/)
 * 5. System Python + bridge module on PYTHONPATH
 */
function resolveBridgeCommand(): { cmd: string; args: string[]; cwd: string; env?: Record<string, string> } | null {
  const isPackaged = app.isPackaged;
  const resourcesPath = process.resourcesPath;

  // 1. Bundled standalone binary (PyInstaller output)
  const bundledExe = process.platform === "win32"
    ? join(resourcesPath, "bridge", "bridge.exe")
    : join(resourcesPath, "bridge", "bridge");
  if (existsSync(bundledExe)) {
    console.log("[bridge] found bundled binary:", bundledExe);
    return { cmd: bundledExe, args: [], cwd: join(resourcesPath, "bridge") };
  }

  // 2. Bundled Python venv (production: resources/bridge/ has venv + bridge module)
  const bundledVenvPython = process.platform === "win32"
    ? join(resourcesPath, "bridge", "venv", "Scripts", "python.exe")
    : join(resourcesPath, "bridge", "venv", "bin", "python3");
  const bundledBridgeModule = join(resourcesPath, "bridge", "bridge", "__init__.py");
  if (existsSync(bundledVenvPython) && existsSync(bundledBridgeModule)) {
    console.log("[bridge] found bundled venv:", bundledVenvPython);
    return { cmd: bundledVenvPython, args: ["-m", "bridge.main"], cwd: join(resourcesPath, "bridge") };
  }

  // 3. User-local install (~/.dus/bridge/)
  const userLocalBridge = join(homedir(), ".dus", "bridge");
  const userLocalInit = join(userLocalBridge, "bridge", "__init__.py");
  const userLocalConfig = join(userLocalBridge, "config.yaml");
  if (existsSync(userLocalInit) || existsSync(userLocalConfig)) {
    const pythonCmd = process.platform === "win32" ? "python" : "python3";
    console.log("[bridge] found user-local bridge:", userLocalBridge);
    return { cmd: pythonCmd, args: ["-m", "bridge.main"], cwd: userLocalBridge };
  }

  // 4. Dev mode: bridge/ is a sibling of desktop/ in the project tree
  if (!isPackaged) {
    // __dirname in dev = desktop/src/main, project root = ../../../
    const devBridgeDir = join(__dirname, "../../../bridge");
    const devBridgeInit = join(devBridgeDir, "bridge", "__init__.py");
    if (existsSync(devBridgeInit)) {
      const pythonCmd = process.platform === "win32" ? "python" : "python3";
      console.log("[bridge] found dev bridge:", devBridgeDir);
      return { cmd: pythonCmd, args: ["-m", "bridge.main"], cwd: devBridgeDir };
    }
  }

  // 5. System Python + bridge module accessible via PYTHONPATH
  const pythonCmd = process.platform === "win32" ? "python" : "python3";
  if (isPackaged) {
    // In production, don't fall back to system Python silently
    console.error("[bridge] no bridge found. Install bridge to ~/.dus/bridge/ or bundle with app.");
    return null;
  }

  // Dev fallback: try from project root anyway
  const projectRoot = join(__dirname, "../../..");
  console.log("[bridge] dev fallback, project root:", projectRoot);
  return { cmd: pythonCmd, args: ["-m", "bridge.main"], cwd: projectRoot };
}

async function startBridge(): Promise<{ success: boolean; error?: string }> {
  if (operationInProgress) return { success: false, error: "Operation in progress" };
  if (bridgeProcess && bridgeProcess.exitCode === null) {
    return { success: true };
  }

  operationInProgress = true;
  currentState = "starting";
  sendStatus({ state: "starting" });

  try {
    const resolved = resolveBridgeCommand();
    if (!resolved) {
      currentState = "error";
      sendStatus({ state: "error" });
      return { success: false, error: "Bridge binary not found" };
    }

    const { cmd, args, cwd, env } = resolved;
    console.log(`[bridge] starting: ${cmd} ${args.join(" ")} (cwd: ${cwd})`);
    bridgeProcess = spawn(cmd, args, {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
      env: env ? { ...process.env, ...env } : undefined,
    });

    bridgeProcess.on("error", (err) => {
      console.error("[bridge] spawn error:", err);
      currentState = "error";
      sendStatus({ state: "error" });
    });

    bridgeProcess.on("exit", (code) => {
      console.log(`[bridge] exited with code ${code}`);
      bridgeProcess = null;
      currentState = "stopped";
      sendStatus({ state: "stopped" });
    });

    bridgeProcess.stdout?.on("data", (data) => {
      const win = getMainWindow();
      win?.webContents.send("bridge:log-line", data.toString());
    });

    bridgeProcess.stderr?.on("data", (data) => {
      const win = getMainWindow();
      win?.webContents.send("bridge:log-line", data.toString());
    });

    startPolling();
    return { success: true };
  } catch (err) {
    currentState = "error";
    sendStatus({ state: "error" });
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    operationInProgress = false;
  }
}

async function stopBridge(): Promise<{ success: boolean; error?: string }> {
  if (operationInProgress) return { success: false, error: "Operation in progress" };
  if (!bridgeProcess || bridgeProcess.exitCode !== null) {
    currentState = "stopped";
    sendStatus({ state: "stopped" });
    return { success: true };
  }

  operationInProgress = true;
  currentState = "stopping" as BridgeStatus["state"];
  sendStatus({ state: "stopping" as BridgeStatus["state"] });

  try {
    stopPolling();
    bridgeProcess.kill("SIGTERM");

    // Wait up to 5s for graceful exit
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        bridgeProcess?.kill("SIGKILL");
        resolve();
      }, 5_000);
      bridgeProcess?.on("exit", () => {
        clearTimeout(timeout);
        resolve();
      });
    });

    bridgeProcess = null;
    currentState = "stopped";
    sendStatus({ state: "stopped" });
    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    operationInProgress = false;
  }
}

async function restartBridge(): Promise<{ success: boolean; error?: string }> {
  await stopBridge();
  return startBridge();
}

// --- Preferences ---

async function loadPrefs(): Promise<DaemonPrefs> {
  try {
    const raw = await readFile(PREFS_PATH, "utf-8");
    return { ...DEFAULT_PREFS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PREFS;
  }
}

async function savePrefs(prefs: DaemonPrefs): Promise<void> {
  await mkdir(join(homedir(), ".dus"), { recursive: true });
  await writeFile(PREFS_PATH, JSON.stringify(prefs, null, 2), "utf-8");
}

// --- Guard ---

function withGuard<T>(
  fn: () => Promise<T>
): Promise<T | { success: false; error: string }> {
  return fn().catch((err) => ({
    success: false as const,
    error: err instanceof Error ? err.message : String(err),
  }));
}

// --- Setup ---

export function setupBridgeManager(
  windowGetter: () => BrowserWindow | null
): void {
  getMainWindow = windowGetter;

  ipcMain.handle("bridge:start", () => withGuard(() => startBridge()));
  ipcMain.handle("bridge:stop", () => withGuard(() => stopBridge()));
  ipcMain.handle("bridge:restart", () => withGuard(() => restartBridge()));
  ipcMain.handle("bridge:get-status", () => fetchHealth());
  ipcMain.handle("bridge:get-prefs", () => loadPrefs());
  ipcMain.handle(
    "bridge:set-prefs",
    (_event, prefs: Partial<DaemonPrefs>) =>
      loadPrefs().then((cur) => {
        const merged = { ...cur, ...prefs };
        return savePrefs(merged).then(() => merged);
      })
  );

  ipcMain.handle("bridge:auto-start", async () => {
    const prefs = await loadPrefs();
    if (!prefs.autoStart) return;
    const health = await fetchHealth();
    if (health.state === "running") return;
    await startBridge();
  });

  // Quit handling: auto-stop
  let isQuitting = false;
  app.on("before-quit", (event) => {
    if (isQuitting) return;
    stopPolling();
    loadPrefs().then(async (prefs) => {
      if (prefs.autoStop && bridgeProcess) {
        isQuitting = true;
        event.preventDefault();
        try {
          await stopBridge();
        } catch {
          // best-effort
        }
        app.quit();
      }
    });
  });

  // Initial health check and polling
  fetchHealth();
  startPolling();

  // Auto-start bridge on app launch (don't wait for renderer IPC)
  // Small delay to let the window initialize first
  setTimeout(() => loadPrefs().then(async (prefs) => {
    if (!prefs.autoStart) return;
    const health = await fetchHealth();
    if (health.state === "running") {
      console.log("[bridge] already running, skipping auto-start");
      return;
    }
    console.log("[bridge] auto-starting...");
    await startBridge();
  }).catch((err) => {
    console.error("[bridge] auto-start failed:", err);
  }), 500);
}
