# 图片分层工具 - 设计文档

## 概述

面向客户的 Web 工具：用户上传图片 → AI 自动分层 → 预览各图层 → 下载 PSD 文件。

## 技术栈

- 前端：Vue3 + Tailwind CSS + shadcn-vue
- 后端：FastAPI + httpx + boto3
- 存储：Cloudflare R2（S3 兼容）做图片中转
- AI 接口：302ai qwen-image-layered
- PSD 生成：手写二进制（已验证，无第三方依赖问题）

## 数据流

```
用户上传图片
  → 后端接收，上传到 R2，拿到公网 URL
  → 调 302ai 提交分层任务（传入 image_url）
  → 轮询 302ai 获取结果（返回分层 PNG URL 列表）
  → 下载所有分层 PNG，合成 PSD
  → 前端展示分层预览 + PSD 下载
```

## 项目结构

```
quwen_test/
├── backend/
│   ├── main.py              # FastAPI 入口，挂载静态文件 + CORS
│   ├── config.py            # 从 .env 读取配置
│   ├── routers/
│   │   └── task.py          # API 路由
│   ├── services/
│   │   ├── storage.py       # R2 上传/删除
│   │   ├── layer_api.py     # 302ai 接口封装
│   │   └── psd_builder.py   # PSD 合成
│   ├── models.py            # Pydantic 模型
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── views/Home.vue
│   │   ├── components/
│   │   │   ├── ImageUploader.vue
│   │   │   ├── LayerPreview.vue
│   │   │   └── ProgressBar.vue
│   │   └── api/index.ts
│   └── package.json
├── .env                     # 密钥配置（gitignore）
└── docs/plans/
```

## API 设计

### POST /api/upload

接收 multipart 图片，返回任务 ID。

请求：`multipart/form-data`，字段 `file`
响应：`{"task_id": "uuid", "status": "PENDING"}`

内部流程：
1. 校验文件类型（PNG/JPG）和大小（≤10MB）
2. 上传到 R2，拿到公网 URL
3. 调 302ai 提交分层任务
4. 创建内存任务记录，返回 task_id

### GET /api/task/{task_id}

轮询任务状态。

响应（处理中）：
```json
{"status": "PROCESSING", "message": "AI 分层中..."}
```

响应（完成）：
```json
{
  "status": "COMPLETED",
  "layers": [
    {"name": "Layer_0", "url": "https://...", "width": 640, "height": 640},
    {"name": "Layer_1", "url": "https://...", "width": 640, "height": 640}
  ]
}
```

响应（失败）：
```json
{"status": "FAILED", "error": "接口超时"}
```

内部流程：如果任务还在 PROCESSING，后端主动请求一次 302ai 查询结果。

### GET /api/download/{task_id}

返回 PSD 文件流。

内部流程：
1. 下载所有分层 PNG
2. 调用 psd_builder 合成
3. 返回文件流（Content-Disposition: attachment）

## 前端页面设计

单页面，三个状态：

### 状态一：待上传
- 居中拖拽上传区域
- 支持拖拽 + 点击选择
- 提示"支持 PNG、JPG，最大 10MB"

### 状态二：处理中
- 左侧：原图预览
- 右侧：进度动画 + 文字"AI 分层中，预计 30 秒..."
- 前端每 2 秒轮询 /api/task/{id}

### 状态三：已完成
- 左侧：原图预览
- 右侧：分层缩略图网格（透明背景用棋盘格）
- 点击缩略图 → 弹窗放大预览
- 底部按钮：「下载 PSD」「重新上传」

## 错误处理

| 场景 | 处理 |
|------|------|
| 非图片文件 | 前端校验拒绝 |
| 超过 10MB | 前端拦截提示 |
| 302ai 超时 | 轮询 120 秒上限，超时标记 FAILED |
| 302ai 返回错误 | 透传错误 + 重试按钮 |
| PSD 合成失败 | 返回 FAILED + 错误原因 |
| 分层图片下载失败 | 重试 2 次 |

## 配置管理

`.env` 文件：
```
# 302ai
API_302_KEY=sk-xxx
API_302_BASE_URL=https://api.302ai.cn

# Cloudflare R2
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_S3_BUCKET=bruceluo
AWS_S3_REGION=apac
AWS_S3_PREFIX=layer-images
AWS_ENDPOINT=https://xxx.r2.cloudflarestorage.com
AWS_PUBLIC_URL=https://image.bruceleo.com
```

## 任务存储

MVP 用内存字典，不上数据库：
```python
tasks: dict[str, TaskInfo] = {}
```

TaskInfo 包含：status, request_id, image_url, layers, psd_path, created_at
