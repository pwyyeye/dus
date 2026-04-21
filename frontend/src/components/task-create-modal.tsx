"use client";

import { useState } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { createTask, fetchMachines, fetchProjects, Machine, Project } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TaskFormData {
  instruction: string;
  target_machine_id: string;
  project_id: string;
}

interface TaskCreateModalProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

export function TaskCreateModal({ open, onOpenChange, trigger, onSuccess }: TaskCreateModalProps) {
  const [internalOpen, setInternalOpen] = useState(false);

  const queryClient = useQueryClient();

  const { data: machines } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<TaskFormData>({
    defaultValues: {
      instruction: "",
      target_machine_id: "",
      project_id: "",
    },
  });

  const targetMachineId = watch("target_machine_id");
  const projectId = watch("project_id");

  const mutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      handleClose();
      onSuccess?.();
    },
  });

  const isControlled = open !== undefined;
  const isOpen = isControlled ? open : internalOpen;
  const setIsOpen = isControlled ? onOpenChange! : setInternalOpen;

  const handleClose = () => {
    reset();
    setIsOpen(false);
  };

  const onSubmit = (data: TaskFormData) => {
    mutation.mutate({
      instruction: data.instruction,
      target_machine_id: data.target_machine_id || undefined,
      project_id: data.project_id || undefined,
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      {trigger && <DialogTrigger>{trigger}</DialogTrigger>}
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>创建新任务</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="task-instruction">执行指令</Label>
            <Textarea
              id="task-instruction"
              placeholder="描述 Agent 需要执行的指令..."
              rows={5}
              {...register("instruction", { required: "指令不能为空" })}
              required
            />
            {errors.instruction && (
              <p className="text-xs text-destructive">{errors.instruction.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="task-machine">目标设备</Label>
            <Select
              value={targetMachineId || ""}
              onValueChange={(val) => setValue("target_machine_id", val || "")}
            >
              <SelectTrigger id="task-machine">
                <SelectValue placeholder="不指定设备" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">不指定设备</SelectItem>
                {machines?.map((m: Machine) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.machine_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="task-project">关联项目</Label>
            <Select
              value={projectId || ""}
              onValueChange={(val) => setValue("project_id", val || "")}
            >
              <SelectTrigger id="task-project">
                <SelectValue placeholder="不关联项目" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">不关联项目</SelectItem>
                {projects?.map((p: Project) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.project_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={handleClose}>
              取消
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "创建中..." : "创建"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}