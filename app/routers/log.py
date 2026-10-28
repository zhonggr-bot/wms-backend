from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.pagination import paginate
from app.models.operation_log import OperationLog
from app.models.user import User
from app.schemas.log import OperationLogResponse
from app.dependencies import get_current_admin

router = APIRouter(prefix="/api/logs", tags=["操作日志"])

@router.get("")
def list_logs(
    db: Session = Depends(get_db),
    user_id: int | None = Query(default=None, description="按操作人筛选"),
    action: str | None = Query(default=None, description="按操作类型筛选：login/register/create_outbound/approve_outbound/..."),
    target: str | None = Query(default=None, description="按操作对象筛选：product/outbound_order/user"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，最大 100"),
    current_user: User = Depends(get_current_admin)
):
    """
    操作日志查询（仅管理员可查）
    """
    query = db.query(OperationLog)

    if user_id:
        query = query.filter(OperationLog.user_id == user_id)
    if action:
        query = query.filter(OperationLog.action == action)
    if target:
        query = query.filter(OperationLog.target == target)

    total, logs = paginate(query.order_by(OperationLog.id.desc()), page, page_size)
    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [OperationLogResponse.model_validate(log) for log in logs]
    })
