# 图片分层工具 - 实现计划

## 实现顺序

按依赖关系从底层到上层，共 8 个步骤。每步完成后可独立验证。

---

## Step 1: 项目初始化 + 配置

**目标**：搭建后端项目骨架，配置读取 `.env`。

**文件**：
- `backend/config.py`
- `backend/main.py`
- `backend/models.py`
- `backend/requirements.txt`
- `.env`
- `pyproject.toml`（uv 项目配置）

**验证**：`uv run python -m backend.main` 启动成功，访问 `http://localhost:8000/docs` 看到 Swagger UI。

---

## Step 2: R2 存储服务

**目标**：实现图片上传到 Cloudflare R2，返回公网 URL。

**文件**：
- `backend/services/storage.py`

**关键逻辑**：
- `upload_image(file_bytes, filename) -> str`：上传到 R2，返回公网 URL
- 使用 boto3 S3 兼容接口
- key 格式：`{prefix}/{uuid}_{filename}`

**验证**：写个简单脚本上传一张测试图片，确认返回的 URL 可公网访问。

---

## Step 3: 302ai 接口封装

**目标**：封装提交分层任务 + 轮询结果。

**文件**：
- `backend/services/layer_api.py`

**关键逻辑**：
- `submit_task(image_url) -> str`：提交任务，返回 request_id
- `poll_result(request_id) -> dict | None`：单次查询结果
- 使用 httpx 异步请求
- Header 带 Authorization Bearer token

**验证**：用 Step 2 上传的图片 URL 调用，确认能拿到 request_id 并最终轮询到分层结果。

---

## Step 4: PSD 合成服务

**目标**：将 test.py 的 write_psd 封装为服务模块。

**文件**：
- `backend/services/psd_builder.py`

**关键逻辑**：
- `build_psd(layer_images: list[tuple[str, bytes]], output_path: str)`
  - 接收 (name, png_bytes) 列表
  - 用 Pillow 解码为 RGBA numpy 数组
  - 调用 write_psd 生成文件
- `build_psd_to_bytes(...)` → 返回 bytes（用于流式下载）

**验证**：用几张测试 PNG 调用，生成的 PSD 在 Photoshop 中打开正常。

---

## Step 5: API 路由 - 上传 + 任务状态 + 下载

**目标**：实现三个核心 API 端点。

**文件**：
- `backend/routers/task.py`
- `backend/models.py`（补充 Pydantic 模型）

**API 实现**：

### POST /api/upload
1. 校验文件类型 + 大小
2. 上传 R2 → 拿到 image_url
3. 调 302ai submit → 拿到 request_id
4. 创建内存任务记录（status=PROCESSING）
5. 启动后台轮询协程
6. 返回 `{task_id, status: "PROCESSING"}`

### GET /api/task/{task_id}
1. 查内存字典
2. 如果 PROCESSING，查一次 302ai
3. 如果 302ai 返回结果，更新状态为 COMPLETED + 存 layers
4. 返回当前状态

### GET /api/download/{task_id}
1. 查任务，确认 COMPLETED
2. 下载所有分层 PNG（httpx，失败重试 2 次）
3. 调 psd_builder 合成
4. 返回 StreamingResponse

**验证**：用 curl/httpie 走完整流程：上传 → 轮询 → 下载 PSD。

---

## Step 6: 前端项目初始化

**目标**：搭建 Vue3 + Tailwind + shadcn-vue 项目。

**文件**：
- `frontend/` 整个目录
- `frontend/package.json`
- `frontend/src/main.ts`
- `frontend/src/App.vue`
- `frontend/src/api/index.ts`

**命令**：
```bash
cd frontend
npm create vite@latest . -- --template vue-ts
npm install
npx shadcn-vue@latest init
npx tailwindcss init -p
```

**验证**：`npm run dev` 启动，页面正常渲染。

---

## Step 7: 前端页面实现

**目标**：实现单页面三状态 UI。

**文件**：
- `frontend/src/views/Home.vue`（主页面状态机）
- `frontend/src/components/ImageUploader.vue`（拖拽上传）
- `frontend/src/components/ProcessingView.vue`（处理中动画）
- `frontend/src/components/ResultView.vue`（分层预览 + 下载）
- `frontend/src/components/LayerPreview.vue`（单个图层卡片，棋盘格背景）
- `frontend/src/api/index.ts`（API 调用封装）

**关键交互**：
- 上传：拖拽 + 点击，前端校验类型/大小，调 POST /api/upload
- 处理中：每 2 秒轮询 GET /api/task/{id}，显示动画
- 完成：网格展示分层缩略图，点击放大，下载 PSD 按钮
- 失败：显示错误信息 + 重试按钮

**验证**：前端连后端，完整走通上传 → 等待 → 预览 → 下载。

---

## Step 8: 前后端联调 + 静态文件部署

**目标**：前端 build 后由 FastAPI 托管静态文件，单端口部署。

**修改**：
- `backend/main.py`：挂载 `frontend/dist` 为静态文件
- 开发时 CORS 允许 localhost:5173
- 生产时前端 build 产物直接由后端 serve

**验证**：`npm run build` → `uv run python -m backend.main` → 访问 `http://localhost:8000` 完整可用。

---

## 依赖关系

```
Step 1 (初始化)
  ├→ Step 2 (R2 存储)
  ├→ Step 3 (302ai 接口)
  └→ Step 4 (PSD 合成)
       ↓
Step 5 (API 路由) ← 依赖 2, 3, 4
       ↓
Step 6 (前端初始化)
       ↓
Step 7 (前端页面)
       ↓
Step 8 (联调部署)
```

Step 2/3/4 可并行开发，Step 5 需要它们全部完成。

---

## 技术要点备忘

- 后台轮询用 `asyncio.create_task`，不阻塞请求
- 轮询 302ai 间隔 3 秒，最多 40 次（120 秒超时）
- PSD 合成在内存中完成，用 `io.BytesIO` 避免临时文件
- 前端轮询用 `setInterval`，组件卸载时 `clearInterval`
- 分层图片下载失败重试 2 次，间隔 1 秒
