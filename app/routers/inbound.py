from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.pagination import paginate
from app.utils.exceptions import BusinessException
from app.models.product import Product
from app.models.inbound_order import InboundOrder
from app.models.operation_log import OperationLog
from app.models.user import User, Role
from app.schemas.product import InboundCreate, InboundResponse
from app.dependencies import get_current_user
from app.constants import LogAction, LogTarget

router = APIRouter(prefix="/api/inbound", tags=["入库管理"])

@router.post("")
def create_inbound(data: InboundCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """创建入库单（普通用户就能操作，创建即生效，自动增加库存）"""
    # 1. 检查商品是否存在（行锁：并发入库时排队累加）
    product = db.query(Product).filter(Product.id == data.product_id).with_for_update().first()
    if not product:
        raise BusinessException(code=404, message="商品不存在")

    # 2. 更新商品总库存
    old_qty = product.total_qty
    product.total_qty = product.total_qty + data.quantity

    # 3. 创建入库单记录
    order = InboundOrder(
        product_id=data.product_id,
        quantity=data.quantity,
        operator_id=current_user.id,
        remark=data.remark
    )
    db.add(order)

    # 4. 记录操作日志
    log = OperationLog(
        user_id=current_user.id,
        action=LogAction.CREATE_INBOUND,
        target=LogTarget.PRODUCT,
        target_id=data.product_id,
        detail=f"入库 {data.quantity} 件，库存从 {old_qty} 变为 {product.total_qty}"
    )
    db.add(log)

    db.commit()
    db.refresh(order)

    return success(data=InboundResponse.model_validate(order), message="入库成功")

@router.get("")
def list_inbounds(
    db: Session = Depends(get_db),
    product_id: int | None = Query(default=None, description="按商品筛选"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，最大 100"),
    current_user: User = Depends(get_current_user)
):
    """入库单列表（普通用户只看自己操作的，管理员看全部）"""
    query = db.query(InboundOrder)
    if current_user.role != Role.ADMIN:
        query = query.filter(InboundOrder.operator_id == current_user.id)
    if product_id:
        query = query.filter(InboundOrder.product_id == product_id)
    total, orders = paginate(query.order_by(InboundOrder.id.desc()), page, page_size)
    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [InboundResponse.model_validate(o) for o in orders]
    })

@router.get("/{order_id}")
def get_inbound(order_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """入库单详情"""
    order = db.query(InboundOrder).filter(InboundOrder.id == order_id).first()
    if not order:
        raise BusinessException(code=404, message="入库单不存在")
    if current_user.role != Role.ADMIN and order.operator_id != current_user.id:
        raise BusinessException(code=403, message="只能查看自己的入库单")
    return success(data=InboundResponse.model_validate(order))
