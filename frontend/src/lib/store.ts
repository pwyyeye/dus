import { create } from "zustand";

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));

interface TaskFiltersState {
  status: string | null;
  projectId: string | null;
  machineId: string | null;
  setStatus: (status: string | null) => void;
  setProjectId: (projectId: string | null) => void;
  setMachineId: (machineId: string | null) => void;
  resetFilters: () => void;
}

export const useTaskFiltersStore = create<TaskFiltersState>((set) => ({
  status: null,
  projectId: null,
  machineId: null,
  setStatus: (status) => set({ status }),
  setProjectId: (projectId) => set({ projectId }),
  setMachineId: (machineId) => set({ machineId }),
  resetFilters: () => set({ status: null, projectId: null, machineId: null }),
}));
