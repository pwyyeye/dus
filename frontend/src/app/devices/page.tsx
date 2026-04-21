"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMachines, fetchMachinesDashboard, MachineDashboard } from "@/lib/api";
import { DeviceCard } from "@/components/device-card";
import {
  Card,
  CardContent,
} from "@/components/ui/card";

export default function DevicesPage() {
  const { data: machines, isLoading: machinesLoading } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ["machines-dashboard"],
    queryFn: fetchMachinesDashboard,
  });

  const isLoading = machinesLoading || dashboardLoading;

  const onlineCount = machines?.filter((m) => m.status === "online").length ?? 0;
  const totalMachines = machines?.length ?? 0;
  const enabledCount = machines?.filter((m) => m.is_enabled).length ?? 0;
  const busyCount = dashboard?.filter((m) => m.running_tasks.length > 0).length ?? 0;
  const totalRunningTasks = dashboard?.reduce((acc, m) => acc + m.running_tasks.length, 0) ?? 0;
  const totalCompletedToday = dashboard?.reduce((acc, m) => acc + m.completed_tasks_count, 0) ?? 0;

  const stats = [
    { title: "在线设备", value: `${onlineCount} / ${totalMachines}`, desc: "当前在线 / 总注册" },
    { title: "可用设备", value: `${enabledCount} / ${totalMachines}`, desc: "已启用设备" },
    { title: "忙碌设备", value: busyCount, desc: "正在执行任务" },
    { title: "执行中任务", value: totalRunningTasks, desc: "已分派或运行中" },
    { title: "今日完成", value: totalCompletedToday, desc: "任务完成数" },
  ];

  const getDashboardForMachine = (machineId: string): MachineDashboard | undefined => {
    return dashboard?.find((d) => d.id === machineId);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">设备概览</h2>
        <p className="text-muted-foreground">查看所有设备状态并快速下发任务</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {stats.map((s) => (
          <Card key={s.title}>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground">{s.desc}</div>
              <div className="text-2xl font-bold mt-1">
                {isLoading ? "..." : s.value}
              </div>
              <div className="text-sm font-medium mt-1">{s.title}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">设备列表</h3>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">加载中...</p>
        ) : !machines?.length ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              暂无注册设备
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {machines.map((machine) => {
              const dash = getDashboardForMachine(machine.id);
              return (
                <DeviceCard
                  key={machine.id}
                  machine={machine}
                  runningTasks={dash?.running_tasks ?? []}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
