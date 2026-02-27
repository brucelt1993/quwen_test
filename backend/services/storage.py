import logging
import uuid
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from backend.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.aws_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_s3_region,
        )
        self.bucket = settings.aws_s3_bucket
        self.prefix = settings.aws_s3_prefix
        self.public_url = settings.aws_public_url

    def upload_image(self, file_bytes: bytes, filename: str) -> str:
        """
        上传图片到 R2，返回公网 URL

        Args:
            file_bytes: 图片二进制数据
            filename: 原始文件名

        Returns:
            公网可访问的 URL
        """
        # 生成唯一文件名
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
        key = f"{self.prefix}/{uuid.uuid4().hex}.{ext}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=BytesIO(file_bytes),
                ContentType=f"image/{ext}",
            )
            logger.info(f"上传成功: {key}")

            # 返回公网 URL
            public_url = f"{self.public_url}/{key}"
            return public_url

        except ClientError as e:
            logger.error(f"上传失败: {e}")
            raise

    def delete_image(self, url: str):
        """删除图片（从 URL 提取 key）"""
        key = url.replace(f"{self.public_url}/", "")
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"删除成功: {key}")
        except ClientError as e:
            logger.error(f"删除失败: {e}")


storage_service = StorageService()
