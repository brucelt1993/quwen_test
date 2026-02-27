from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 302ai
    api_302_key: str
    api_302_base_url: str = "https://api.302ai.cn"

    # Cloudflare R2
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket: str = "bruceluo"
    aws_s3_region: str = "apac"
    aws_s3_prefix: str = "layer-images"
    aws_endpoint: str
    aws_public_url: str

    # 应用
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    poll_interval: int = 3  # 秒
    poll_timeout: int = 120  # 秒

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
