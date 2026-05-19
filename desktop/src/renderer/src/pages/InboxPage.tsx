import { useEffect, useState, useCallback } from "react";
import { fetchInboxItems, markInboxRead, type InboxItem } from "../lib/api";
import { RefreshCw, Loader2, Mail, MailOpen } from "lucide-react";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchInboxItems({ limit: 50 });
      setItems(res.items);
      setTotal(res.total);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRead = async (id: string) => {
    try {
      await markInboxRead(id);
      setItems((prev) => prev.map((i) => i.id === id ? { ...i, is_read: true } : i));
    } catch {}
  };

  const unread = items.filter((i) => !i.is_read).length;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold">收件箱</h1>
          {unread > 0 && (
            <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-400">{unread} 未读</span>
          )}
        </div>
        <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <RefreshCw size={14} />刷新
        </button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--muted-foreground)]">暂无消息</div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className={`flex items-start gap-3 rounded-lg border p-4 transition-colors cursor-pointer ${
                  item.is_read
                    ? "border-[var(--border)]/50 bg-transparent"
                    : "border-[var(--primary)]/30 bg-[var(--primary)]/5"
                }`}
                onClick={() => !item.is_read && handleRead(item.id)}
              >
                {item.is_read ? <MailOpen size={18} className="mt-0.5 text-[var(--muted-foreground)]" /> : <Mail size={18} className="mt-0.5 text-[var(--primary)]" />}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${item.is_read ? "text-[var(--muted-foreground)]" : "font-medium"}`}>{item.title}</p>
                  {item.message && <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">{item.message}</p>}
                </div>
                <span className="shrink-0 text-xs text-[var(--muted-foreground)]">{formatTime(item.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
