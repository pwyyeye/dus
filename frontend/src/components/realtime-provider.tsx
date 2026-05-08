"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { wsClient } from "@/lib/websocket";

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const connectedRef = useRef(false);

  useEffect(() => {
    const handleMessage = (data: { type: string; payload: unknown }) => {
      const payload = data.payload as Record<string, unknown>;
      const id = payload.id as string | undefined;

      switch (data.type) {
        case "task.created":
        case "task.updated":
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          if (id) {
            queryClient.invalidateQueries({ queryKey: ["task", id] });
          }
          queryClient.invalidateQueries({ queryKey: ["machines-dashboard"] });
          queryClient.invalidateQueries({ queryKey: ["unassigned"] });
          break;
        case "issue.created":
        case "issue.updated":
        case "issue.deleted":
          queryClient.invalidateQueries({ queryKey: ["issues"] });
          if (id) {
            queryClient.invalidateQueries({ queryKey: ["issue", id] });
            queryClient.invalidateQueries({ queryKey: ["issue-tasks", id] });
          }
          break;
        case "machine.updated":
          queryClient.invalidateQueries({ queryKey: ["machines"] });
          queryClient.invalidateQueries({ queryKey: ["machines-dashboard"] });
          if (id) {
            queryClient.invalidateQueries({ queryKey: ["machine", id] });
          }
          break;
      }
    };

    const unsubMsg = wsClient.onMessage(handleMessage);
    const unsubOpen = wsClient.onOpen(() => {
      connectedRef.current = true;
    });
    const unsubClose = wsClient.onClose(() => {
      connectedRef.current = false;
    });

    wsClient.connect();

    return () => {
      unsubMsg();
      unsubOpen();
      unsubClose();
      wsClient.disconnect();
    };
  }, [queryClient]);

  return <>{children}</>;
}
