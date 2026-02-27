import logging
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class LayerAPIService:
    def __init__(self):
        self.base_url = settings.api_302_base_url
        self.api_key = settings.api_302_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def submit_task(self, image_url: str, num_layers: int = 4, prompt: str = "") -> str:
        """
        提交分层任务

        Args:
            image_url: 图片公网 URL
            num_layers: 分层数量，默认 4
            prompt: 提示词，可选

        Returns:
            request_id
        """
        url = f"{self.base_url}/302/submit/qwen-image-layered"
        payload = {
            "image_url": image_url,
            "prompt": prompt,
            "num_layers": num_layers,
            "enable_safety_checker": True,
            "output_format": "png",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                request_id = data.get("request_id")
                logger.info(f"提交任务成功: request_id={request_id}")
                return request_id
            except httpx.HTTPError as e:
                logger.error(f"提交任务失败: {e}")
                raise

    async def poll_result(self, request_id: str) -> Optional[dict]:
        """
        查询任务结果（单次）

        Args:
            request_id: 任务 ID

        Returns:
            如果完成返回结果字典，否则返回 None
        """
        url = f"{self.base_url}/302/submit/qwen-image-layered"
        params = {"request_id": request_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                # 检查是否有 images 字段（完成标志）
                if "images" in data and data["images"]:
                    logger.info(f"任务完成: request_id={request_id}, 图层数={len(data['images'])}")
                    return data

                logger.info(f"任务处理中: request_id={request_id}")
                return None

            except httpx.HTTPError as e:
                logger.error(f"查询任务失败: {e}")
                raise


layer_api_service = LayerAPIService()
