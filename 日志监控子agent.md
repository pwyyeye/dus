### 日志监控子 Agent

一个后台日志监控系统，自动检测后端错误日志，并在 Agent 空闲时通知 Claude Code 处理。

**设计思路**：开发过程中后端可能产生错误日志，但 Agent 正忙于编码时不应被打断。本系统通过空闲检测机制，只在 Agent 空闲时才推送错误通知，避免干扰正在进行的工作。

#### 架构

```
log_monitor.py ──扫描──> 日志文件 (bridge-stdout.log, uvicorn.log 等)
     │
     ├─ 检测 Agent 空闲？──否──> 抑制通知（Agent 正在编码）
     │
     └─ 是 ──写入──> .dus/log_errors.json
                          │
                          └─ Claude Code 定时任务每 2 分钟读取 ──> 处理错误
```

#### 启动监控

```bash
D:/ProgramData/miniconda3/python.exe -u scripts/log_monitor.py
```

可选指定配置文件路径：

```bash
python -u scripts/log_monitor.py --config .dus/log_monitor.json
```

#### 配置说明

配置文件：`.dus/log_monitor.json`

| 配置项                     | 类型     | 默认值                                                                       | 说明                                                   |
| -------------------------- | -------- | ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| `log_files`              | string[] | `[".dus/bridge-stdout.log", "cloud/uvicorn.log"]`                          | 要监控的日志文件列表                                   |
| `project_dir`            | string   | `"."`                                                                      | 项目根目录                                             |
| `idle_threshold_seconds` | int      | `30`                                                                       | Agent 空闲判定阈值（秒），超过此时间无文件修改视为空闲 |
| `scan_interval_seconds`  | int      | `10`                                                                       | 扫描间隔（秒）                                         |
| `error_output`           | string   | `".dus/log_errors.json"`                                                   | 错误通知输出文件                                       |
| `error_patterns`         | string[] | `ERROR, CRITICAL, Traceback, Exception:, 500 error, Internal Server Error` | 错误匹配正则表达式                                     |
| `ignore_patterns`        | string[] | `health, ping`                                                             | 忽略匹配的正则表达式（过滤已知/重复错误）              |

#### 空闲检测机制

监控脚本通过文件修改时间判断 Agent 是否空闲：

1. 定期扫描 `cloud/`、`bridge/`、`frontend/src/` 目录下 `.py`、`.ts`、`.tsx`、`.js` 等文件的最后修改时间
2. 若最近一次修改距今超过 `idle_threshold_seconds`（默认 30 秒），判定 Agent 为空闲
3. Agent 空闲时才将错误写入通知文件；Agent 活跃时仅打印日志，不触发通知

#### Claude Code 定时任务设置

在 Claude Code 中设置定时任务，每 2 分钟检查错误通知文件：

```
/loop 2m 检查 .dus/log_errors.json 是否有新的错误通知，如有则分析并处理，处理完毕后清空 errors 数组
```

通知文件 `.dus/log_errors.json` 格式：

```json
{
  "errors": [
    {
      "source": "uvicorn.log",
      "line_no": 1234,
      "message": "ERROR: ...",
      "timestamp": "2026-05-11 14:30:00"
    }
  ],
  "last_updated": "2026-05-11 14:30:00"
}
```

---