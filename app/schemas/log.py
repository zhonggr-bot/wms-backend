from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationLogResponse(BaseModel):
    """操作日志响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    target: str | None
    target_id: int | None
    detail: str | None
    created_at: datetime
