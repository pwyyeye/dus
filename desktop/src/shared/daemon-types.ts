export interface BridgeStatus {
  state:
    | "starting"
    | "running"
    | "stopped"
    | "error"
    | "installing";
  pid?: number;
  uptime?: string;
  machineId?: string;
  machineName?: string;
  agents?: string[];
  activeTaskCount?: number;
  healthPort?: number;
}

export interface DaemonPrefs {
  autoStart: boolean;
  autoStop: boolean;
}
