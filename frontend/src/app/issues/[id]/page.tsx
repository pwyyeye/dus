"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchIssue,
  fetchIssueTasks,
  fetchLabels,
  createComment,
  deleteComment,
  addIssueDependency,
  removeIssueDependency,
  fetchIssueMessages,
  type Issue,
  type Label,
  type Comment,
  type ChatMessage,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeftIcon,
  EyeIcon,
  LinkIcon,
  MessageSquareIcon,
  ReplyIcon,
  SendIcon,
  XIcon,
  SubscriptIcon,
  GitBranchIcon,
  BotIcon,
} from "lucide-react";

interface PageProps {
  params: Promise<{ id: string }>;
}

const priorityConfig: Record<string, { label: string; color: string }> = {
  low: { label: "低", color: "text-muted-foreground" },
  medium: { label: "中", color: "text-blue-600" },
  high: { label: "高", color: "text-orange-600" },
  urgent: { label: "紧急", color: "text-red-600" },
};

const depTypeConfig: Record<string, { label: string; color: string }> = {
  blocks: { label: "阻塞", color: "bg-red-100 text-red-700" },
  blocked_by: { label: "被阻塞", color: "bg-orange-100 text-orange-700" },
  related: { label: "相关", color: "bg-blue-100 text-blue-700" },
};

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

// ── Comment Tree Component ──

function CommentItem({
  comment,
  depth = 0,
  onReply,
  onDelete,
}: {
  comment: Comment;
  depth?: number;
  onReply: (parentId: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className={depth > 0 ? "ml-6 border-l-2 border-muted pl-3" : ""}>
      <div className="flex items-start gap-2 py-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {comment.author_name || "匿名"}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatTime(comment.created_at)}
            </span>
          </div>
          <p className="text-sm mt-1 whitespace-pre-wrap">{comment.content}</p>
          <div className="flex gap-2 mt-1">
            <Button
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              onClick={() => onReply(comment.id)}
            >
              <ReplyIcon className="size-3 mr-1" />
              回复
            </Button>
            <Button
              variant="ghost"
              size="xs"
              className="text-muted-foreground hover:text-destructive"
              onClick={() => onDelete(comment.id)}
            >
              删除
            </Button>
          </div>
        </div>
      </div>
      {comment.replies?.map((reply) => (
        <CommentItem
          key={reply.id}
          comment={reply}
          depth={depth + 1}
          onReply={onReply}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

// ── Main Page Component ──

export default function IssueDetailPage({ params }: PageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { id } = React.use(params);

  const [commentText, setCommentText] = useState("");
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState("");
  const [newDepId, setNewDepId] = useState("");

  const { data: issue, isLoading: issueLoading } = useQuery({
    queryKey: ["issue", id],
    queryFn: () => fetchIssue(id),
  });

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["issue-tasks", id],
    queryFn: () => fetchIssueTasks(id),
    refetchInterval: 5000,
  });

  const { data: labels } = useQuery({
    queryKey: ["labels"],
    queryFn: fetchLabels,
  });

  const { data: chatMessages } = useQuery({
    queryKey: ["issue-messages", id],
    queryFn: () => fetchIssueMessages(id),
    enabled: !!id,
  });

  const createCommentMut = useMutation({
    mutationFn: createComment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", id] });
      setCommentText("");
      setReplyTo(null);
    },
  });

  const deleteCommentMut = useMutation({
    mutationFn: deleteComment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", id] });
    },
  });

  const addDepMut = useMutation({
    mutationFn: (data: { depends_on_issue_id: string }) =>
      addIssueDependency(id, { ...data, dependency_type: "blocks" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", id] });
      setNewDepId("");
    },
  });

  const removeDepMut = useMutation({
    mutationFn: (depId: string) => removeIssueDependency(id, depId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", id] });
    },
  });

  const handleSubmitComment = () => {
    if (!commentText.trim()) return;
    createCommentMut.mutate({
      issue_id: id,
      content: commentText,
      parent_id: replyTo || undefined,
      author_name: authorName || undefined,
    });
  };

  const handleAddDependency = () => {
    if (!newDepId.trim()) return;
    addDepMut.mutate({ depends_on_issue_id: newDepId });
  };

  if (issueLoading) {
    return (
      <div className="space-y-6">
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      </div>
    );
  }

  if (!issue) {
    return (
      <div className="space-y-6">
        <div className="text-center py-8 text-muted-foreground">
          Issue 不存在或已删除
        </div>
      </div>
    );
  }

  const pConfig = priorityConfig[issue.priority] ?? {
    label: issue.priority,
    color: "",
  };
  const issueLabels = issue.labels ?? [];
  const subIssues = issue.sub_issues ?? [];
  const dependencies = issue.dependencies ?? [];
  const comments = issue.comments ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => router.push("/issues")}
        >
          <ArrowLeftIcon className="size-4 mr-1" />
          返回列表
        </Button>
      </div>

      <div>
        <h2 className="text-2xl font-bold tracking-tight">{issue.title}</h2>
        <p className="text-muted-foreground font-mono text-xs mt-1">
          {issue.issue_id}
        </p>
      </div>

      {/* Labels */}
      {issueLabels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {issueLabels.map((label) => (
            <Badge
              key={label.id}
              variant="outline"
              style={label.color ? { borderColor: label.color, color: label.color } : undefined}
            >
              {label.name}
            </Badge>
          ))}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>状态</CardDescription>
          </CardHeader>
          <CardContent>
            <StatusBadge status={issue.status} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>优先级</CardDescription>
          </CardHeader>
          <CardContent>
            <span className={`font-medium ${pConfig.color}`}>
              {pConfig.label}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>执行次数</CardDescription>
          </CardHeader>
          <CardContent>
            <span className="font-medium">{tasks?.length ?? 0}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>分配对象</CardDescription>
          </CardHeader>
          <CardContent>
            <span className="text-sm">
              {issue.assignee_type === "agent"
                ? `智能体 (${issue.assignee_id?.slice(0, 8) ?? "-"})`
                : issue.assignee_type === "machine"
                  ? `设备 (${issue.assignee_id?.slice(0, 8) ?? "-"})`
                  : "未分配"}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>更新时间</CardDescription>
          </CardHeader>
          <CardContent>
            <span className="text-sm">{formatTime(issue.updated_at)}</span>
          </CardContent>
        </Card>
      </div>

      {/* Description */}
      {issue.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">描述</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{issue.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Sub-issues */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <SubscriptIcon className="size-4" />
            子任务
          </CardTitle>
          <CardDescription>属于当前 Issue 的子工作项</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {subIssues.length === 0 ? (
            <div className="py-6 text-center text-muted-foreground text-sm">
              暂无子任务
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>优先级</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subIssues.map((sub) => (
                  <TableRow
                    key={sub.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/issues/${sub.id}`)}
                  >
                    <TableCell>
                      <div>
                        <p className="font-medium text-sm">{sub.title}</p>
                        <p className="font-mono text-xs text-muted-foreground">
                          {sub.issue_id}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={sub.status} />
                    </TableCell>
                    <TableCell>
                      <span
                        className={`text-sm ${(priorityConfig[sub.priority]?.color ?? "")}`}
                      >
                        {priorityConfig[sub.priority]?.label ?? sub.priority}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/issues/${sub.id}`);
                        }}
                      >
                        <EyeIcon className="size-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Dependencies */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <GitBranchIcon className="size-4" />
            依赖关系
          </CardTitle>
          <CardDescription>与其他 Issue 的关联和阻塞关系</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Add dependency form */}
          <div className="flex gap-2 mb-4">
            <Input
              placeholder="输入依赖 Issue 的 UUID..."
              value={newDepId}
              onChange={(e) => setNewDepId(e.target.value)}
              className="flex-1"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={handleAddDependency}
              disabled={!newDepId.trim() || addDepMut.isPending}
            >
              <LinkIcon className="size-3 mr-1" />
              添加
            </Button>
          </div>

          {dependencies.length === 0 ? (
            <div className="py-4 text-center text-muted-foreground text-sm">
              暂无依赖关系
            </div>
          ) : (
            <div className="space-y-2">
              {dependencies.map((dep) => (
                <div
                  key={dep.id}
                  className="flex items-center justify-between p-2 rounded border"
                >
                  <div className="flex items-center gap-3">
                    <Badge
                      variant="outline"
                      className={depTypeConfig[dep.dependency_type]?.color}
                    >
                      {depTypeConfig[dep.dependency_type]?.label ??
                        dep.dependency_type}
                    </Badge>
                    <div>
                      <p className="text-sm font-medium">
                        {dep.depends_on?.title ?? "Unknown"}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {dep.depends_on?.issue_id ?? dep.depends_on_issue_id}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {dep.depends_on && (
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        onClick={() =>
                          router.push(`/issues/${dep.depends_on_issue_id}`)
                        }
                      >
                        <EyeIcon className="size-3.5" />
                      </Button>
                    )}
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => removeDepMut.mutate(dep.id)}
                    >
                      <XIcon className="size-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Conversation */}
      {chatMessages && chatMessages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BotIcon className="size-4" />
              AI 会话
            </CardTitle>
            <CardDescription>与智能体的对话历史</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-2 ${msg.role === "user" ? "flex-row" : "flex-row-reverse"}`}
                >
                  <div
                    className={`px-3 py-2 rounded-lg text-sm max-w-[80%] ${
                      msg.role === "user"
                        ? "bg-blue-100 text-blue-900"
                        : "bg-gray-100 text-gray-900"
                    }`}
                  >
                    <div className="text-xs opacity-60 mb-1">
                      {msg.role === "user" ? "用户" : "助手"}
                    </div>
                    <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comments */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <MessageSquareIcon className="size-4" />
            评论
          </CardTitle>
          <CardDescription>讨论和备注</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Comment list */}
          {comments.length === 0 ? (
            <div className="py-4 text-center text-muted-foreground text-sm">
              暂无评论
            </div>
          ) : (
            <div className="space-y-1 mb-4">
              {comments.map((c) => (
                <CommentItem
                  key={c.id}
                  comment={c}
                  onReply={(parentId) => setReplyTo(parentId)}
                  onDelete={(commentId) => deleteCommentMut.mutate(commentId)}
                />
              ))}
            </div>
          )}

          {/* Reply indicator */}
          {replyTo && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <ReplyIcon className="size-3" />
              <span>
                回复 {replyTo.slice(0, 8)}...
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => setReplyTo(null)}
              >
                <XIcon className="size-3" />
              </Button>
            </div>
          )}

          {/* Comment input */}
          <div className="space-y-2">
            <div className="flex gap-2">
              <Input
                placeholder="你的名字（可选）"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                className="w-32"
              />
            </div>
            <div className="flex gap-2">
              <Textarea
                placeholder="写下评论..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={2}
                className="flex-1"
              />
              <Button
                size="sm"
                className="self-end"
                onClick={handleSubmitComment}
                disabled={!commentText.trim() || createCommentMut.isPending}
              >
                <SendIcon className="size-3 mr-1" />
                发送
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Execution History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行历史</CardTitle>
          <CardDescription>该 Issue 关联的所有任务执行记录</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {tasksLoading ? (
            <div className="py-8 text-center text-muted-foreground">
              加载中...
            </div>
          ) : !tasks || tasks.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              暂无执行记录
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务ID</TableHead>
                  <TableHead>指令</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>目标设备</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-mono text-xs">
                      {task.task_id}
                    </TableCell>
                    <TableCell>
                      <p className="text-sm line-clamp-2 max-w-[300px]">
                        {truncate(task.instruction, 60)}
                      </p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.target_machine_id
                        ? task.target_machine_id.slice(0, 8)
                        : "-"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTime(task.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        onClick={() => router.push(`/tasks/${task.id}`)}
                        title="查看任务详情"
                      >
                        <EyeIcon className="size-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
