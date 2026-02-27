import asyncio
import logging
import time
import uuid
from typing import Dict

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.config import settings
from backend.models import LayerInfo, TaskResponse, TaskStatus, UploadResponse
from backend.services.layer_api import layer_api_service
from backend.services.psd_builder import build_psd_to_bytes
from backend.services.storage import storage_service

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg"}

# 内存任务存储
tasks: Dict[str, dict] = {}


@router.post("/upload", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    num_layers: int = Form(4),
    prompt: str = Form(""),
):
    """上传图片，提交分层任务"""
    # 校验文件类型
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")

    # 读取文件
    file_bytes = await file.read()

    # 校验大小
    if len(file_bytes) > settings.max_upload_size:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    # 上传到 R2
    try:
        image_url = storage_service.upload_image(file_bytes, file.filename or "upload.png")
        logger.info(f"图片已上传到 R2: {image_url}")
    except Exception as e:
        logger.error(f"R2 上传失败: {e}")
        raise HTTPException(status_code=500, detail="图片上传失败")

    # 提交 302ai 分层任务
    try:
        request_id = await layer_api_service.submit_task(image_url, num_layers, prompt)
        logger.info(f"分层任务已提交: request_id={request_id}, num_layers={num_layers}, prompt={prompt}")
    except Exception as e:
        logger.error(f"提交分层任务失败: {e}")
        raise HTTPException(status_code=500, detail="提交分层任务失败")
        logger.info(f"分层任务已提交: request_id={request_id}")
    except Exception as e:
        logger.error(f"提交分层任务失败: {e}")
        raise HTTPException(status_code=500, detail="提交分层任务失败")

    # 创建任务记录
    task_id = uuid.uuid4().hex[:12]
    tasks[task_id] = {
        "status": TaskStatus.PROCESSING,
        "request_id": request_id,
        "image_url": image_url,
        "layers": [],
        "error": "",
        "created_at": time.time(),
    }

    # 启动后台轮询
    asyncio.create_task(_poll_task(task_id))

    return UploadResponse(task_id=task_id, status=TaskStatus.PROCESSING)


@router.get("/task/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] == TaskStatus.COMPLETED:
        return TaskResponse(
            status=TaskStatus.COMPLETED,
            layers=task["layers"],
        )
    elif task["status"] == TaskStatus.FAILED:
        return TaskResponse(
            status=TaskStatus.FAILED,
            error=task["error"],
        )
    else:
        return TaskResponse(
            status=TaskStatus.PROCESSING,
            message="AI 分层中...",
        )


@router.get("/download/{task_id}")
async def download_psd(task_id: str):
    """下载 PSD 文件"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    layers = task["layers"]
    if not layers:
        raise HTTPException(status_code=500, detail="没有分层数据")

    # 下载所有分层 PNG
    layer_images = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, layer in enumerate(layers):
            png_bytes = await _download_with_retry(client, layer.url)
            if png_bytes is None:
                raise HTTPException(status_code=500, detail=f"下载图层 {i} 失败")
            layer_images.append((layer.name, png_bytes))

    # 合成 PSD
    try:
        max_w = max(l.width for l in layers)
        max_h = max(l.height for l in layers)
        psd_bytes = build_psd_to_bytes(layer_images, max_w, max_h)
    except Exception as e:
        logger.error(f"PSD 合成失败: {e}")
        raise HTTPException(status_code=500, detail="PSD 合成失败")

    return Response(
        content=psd_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=layered_{task_id}.psd"},
    )


async def _poll_task(task_id: str):
    """后台轮询 302ai 任务结果"""
    task = tasks.get(task_id)
    if not task:
        return

    request_id = task["request_id"]
    max_attempts = settings.poll_timeout // settings.poll_interval
    attempt = 0

    while attempt < max_attempts:
        await asyncio.sleep(settings.poll_interval)
        attempt += 1

        try:
            result = await layer_api_service.poll_result(request_id)
            if result and "images" in result:
                # 任务完成
                layers = []
                for i, img in enumerate(result["images"]):
                    layers.append(LayerInfo(
                        name=f"Layer_{i}",
                        url=img["url"],
                        width=img.get("width", 0),
                        height=img.get("height", 0),
                    ))
                task["status"] = TaskStatus.COMPLETED
                task["layers"] = layers
                logger.info(f"任务完成: task_id={task_id}, 图层数={len(layers)}")
                return
        except Exception as e:
            logger.error(f"轮询失败 (attempt {attempt}): {e}")

    # 超时
    task["status"] = TaskStatus.FAILED
    task["error"] = "处理超时，请重试"
    logger.error(f"任务超时: task_id={task_id}")


async def _download_with_retry(client: httpx.AsyncClient, url: str, retries: int = 2) -> bytes | None:
    """下载文件，失败重试"""
    for i in range(retries + 1):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"下载失败 (attempt {i + 1}): {url}, {e}")
            if i < retries:
                await asyncio.sleep(1)
    return None
