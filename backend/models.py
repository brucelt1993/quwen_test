from enum import Enum
from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LayerInfo(BaseModel):
    name: str
    url: str
    width: int
    height: int


class UploadResponse(BaseModel):
    task_id: str
    status: TaskStatus


class TaskResponse(BaseModel):
    status: TaskStatus
    message: str = ""
    layers: list[LayerInfo] = []
    error: str = ""
