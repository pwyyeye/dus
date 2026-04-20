# DUS Frontend

分布式AI终端统一调度系统 - 前端管理界面

## 技术栈

- **Next.js 16** (App Router) - Web 框架
- **React 19** - UI 库
- **Tailwind CSS v4** - 样式
- **shadcn/ui** - UI 组件库
- **TanStack Query (React Query)** - 数据请求与缓存
- **Zustand** - 客户端状态管理
- **Zod** - 数据校验

## 项目结构

```
frontend/src/
├── app/
│   ├── layout.tsx         # 根布局（含侧边栏）
│   ├── page.tsx          # 首页仪表盘
│   ├── machines/          # 设备管理页面
│   │   └── page.tsx
│   ├── tasks/            # 任务管理页面
│   │   └── page.tsx
│   └── projects/         # 项目管理页面
│       └── page.tsx
├── components/
│   ├── sidebar.tsx       # 侧边导航栏
│   └── ui/               # shadcn/ui 组件
├── lib/
│   ├── api.ts            # API 客户端封装
│   ├── providers.tsx     # React Query Provider
│   └── utils.ts          # 工具函数
└── app/globals.css
```

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量

```bash
# 创建 .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_API_KEY=change-me-to-a-strong-random-string-at-least-32-chars
```

### 3. 启动开发服务器

```bash
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000) 查看。

### 4. 构建生产版本

```bash
npm run build
npm run start
```

## 页面功能

### 首页仪表盘
- 系统概览：在线设备数、待处理/执行中/已完成/失败任务数、活跃项目数
- 最近任务列表（最近 5 条）

### 设备管理 (`/machines`)
- 设备列表展示（设备ID、名称、Agent类型、执行能力、状态、最后心跳）
- 状态 badge：在线（绿色）/ 离线（红色）
- Agent 类型 badge：remote_execution（远程执行）/ manual_only（手动）

### 任务管理 (`/tasks`)
- 任务列表（任务ID、标题、优先级、状态、创建时间）
- 创建任务：标题、执行指令、优先级、目标设备选择
- 状态 badge：待处理 / 已分派 / 运行中 / 已完成 / 失败 / 已取消 / 待手动
- 优先级 badge：低 / 中 / 高 / 紧急

### 项目管理 (`/projects`)
- 项目列表（项目ID、名称、根路径、闲置时长、闲置阈值、创建时间）
- 创建项目：项目名称、根路径
- 闲置提醒 badge：超过阈值显示红色

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEXT_PUBLIC_API_URL` | 云端 API 地址 | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_API_KEY` | API 认证密钥 | - |

## 与后端通信

前端通过 `lib/api.ts` 中的函数与 Cloud API 交互，认证方式为 `X-API-Key` Header。

详细 API 文档请参考 [Cloud API README](../cloud/README.md)。

## License

Internal use only.
