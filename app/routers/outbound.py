from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.pagination import paginate
from app.utils.exceptions import BusinessException
from app.models.product import Product
from app.models.outbound_order import OutboundOrder, OutboundStatus
from app.models.operation_log import OperationLog
from app.models.user import User, Role
from app.schemas.product import OutboundCreate, OutboundApprove, OutboundResponse
from app.dependencies import get_current_user, get_current_admin
from app.constants import LogAction, LogTarget

router = APIRouter(prefix="/api/outbound", tags=["出库管理"])

# ===== 1. 提交出库申请（普通用户）=====

@router.post("")
def create_outbound(data: OutboundCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """
    提交出库申请 → 自动冻结库存
    可用库存 = total_qty - frozen_qty，冻结数量不能超过可用库存
    """
    # 行锁：并发请求在这行上排队，读到的一定是最新可用库存
    product = db.query(Product).filter(Product.id == data.product_id).with_for_update().first()
    if not product:
        raise BusinessException(code=404, message="商品不存在")

    available_qty = product.total_qty - product.frozen_qty
    if data.quantity > available_qty:
        raise BusinessException(
            code=400,
            message=f"可用库存不足，当前可用 {available_qty} 件"
        )

    # 冻结库存
    product.frozen_qty = product.frozen_qty + data.quantity

    # 创建出库单
    order = OutboundOrder(
        product_id=data.product_id,
        quantity=data.quantity,
        applicant_id=current_user.id,
        status=OutboundStatus.PENDING,
        remark=data.remark
    )
    db.add(order)
    db.flush()   # 先拿到自增 id，供日志记录（仍属同一事务，尚未提交）

    # 记录日志
    log = OperationLog(
        user_id=current_user.id,
        action=LogAction.CREATE_OUTBOUND,
        target=LogTarget.OUTBOUND_ORDER,
        target_id=order.id,
        detail=f"提交出库申请 {data.quantity} 件，已冻结"
    )
    db.add(log)

    db.commit()
    db.refresh(order)

    return success(data=OutboundResponse.model_validate(order), message="申请已提交，库存已冻结")

# ===== 2. 管理员审批（通过 / 驳回）=====

@router.post("/{order_id}/approve")
def approve_outbound(
    order_id: int,
    data: OutboundApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """管理员审批出库申请"""
    # 行锁：并发审批同一张单会排队，后到者读到的是已变更的状态
    order = db.query(OutboundOrder).filter(OutboundOrder.id == order_id).with_for_update().first()
    if not order:
        raise BusinessException(code=404, message="出库单不存在")

    # 只有 pending 状态才能审批
    if order.status != OutboundStatus.PENDING:
        raise BusinessException(code=400, message="该申请已处理，不可重复审批")

    # 不能自己审自己的单，否则"申请-审批"两道关就形同虚设
    if order.applicant_id == current_user.id:
        raise BusinessException(code=400, message="不能审批自己提交的申请")

    product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
    if not product:
        raise BusinessException(code=404, message="商品不存在，无法审批")

    if data.approve:
        # ====== 审批通过：扣减 frozen + 扣减 total ======
        if data.reject_reason:
            raise BusinessException(code=400, message="通过时不需要填驳回原因")

        if product.frozen_qty < order.quantity:
            raise BusinessException(code=400, message="冻结库存异常，无法扣减")

        product.frozen_qty = product.frozen_qty - order.quantity
        product.total_qty = product.total_qty - order.quantity

        order.status = OutboundStatus.APPROVED

        log_detail = f"审批通过，出库 {order.quantity} 件，冻结已释放并扣减"

    else:
        # ====== 审批驳回：只释放冻结，不动 total ======
        if not data.reject_reason:
            raise BusinessException(code=400, message="驳回时必须填写驳回原因")

        # 校验冻结量足够，防止扣成负数
        if product.frozen_qty < order.quantity:
            raise BusinessException(code=400, message="冻结库存异常，无法释放")

        product.frozen_qty = product.frozen_qty - order.quantity
        order.status = OutboundStatus.REJECTED
        order.reject_reason = data.reject_reason

        log_detail = f"审批驳回，原因: {data.reject_reason}，冻结已释放"

    order.approver_id = current_user.id
    order.approved_at = datetime.now()

    log = OperationLog(
        user_id=current_user.id,
        action=LogAction.APPROVE_OUTBOUND,
        target=LogTarget.OUTBOUND_ORDER,
        target_id=order_id,
        detail=log_detail
    )
    db.add(log)

    db.commit()
    db.refresh(order)

    status_msg = "出库成功" if data.approve else "已驳回"
    return success(data=OutboundResponse.model_validate(order), message=f"审批完成，{status_msg}")

# ===== 3. 用户自己撤回申请 =====

@router.post("/{order_id}/cancel")
def cancel_outbound(order_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """
    用户撤回自己的申请 → 释放冻结
    只有申请人本人能撤，且只能撤 pending 状态的
    """
    order = db.query(OutboundOrder).filter(OutboundOrder.id == order_id).with_for_update().first()
    if not order:
        raise BusinessException(code=404, message="出库单不存在")

    if order.applicant_id != current_user.id:
        raise BusinessException(code=403, message="只能撤回自己的申请")

    if order.status != OutboundStatus.PENDING:
        raise BusinessException(code=400, message="该申请已处理，不可撤回")

    product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
    if not product:
        raise BusinessException(code=404, message="商品不存在，无法撤回")

    # 释放冻结前先确认冻结量够，避免把 frozen_qty 减成负数
    if product.frozen_qty < order.quantity:
        raise BusinessException(code=400, message="冻结库存异常，无法释放")

    product.frozen_qty = product.frozen_qty - order.quantity

    order.status = OutboundStatus.CANCELLED

    log = OperationLog(
        user_id=current_user.id,
        action=LogAction.CANCEL_OUTBOUND,
        target=LogTarget.OUTBOUND_ORDER,
        target_id=order_id,
        detail=f"用户撤回申请，释放冻结 {order.quantity} 件"
    )
    db.add(log)

    db.commit()
    db.refresh(order)

    return success(data=OutboundResponse.model_validate(order), message="已撤回，冻结已释放")

# ===== 4. 列表查询 =====

@router.get("")
def list_outbounds(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None, description="按状态筛选：pending/approved/rejected/cancelled"),
    product_id: int | None = Query(default=None, description="按商品筛选"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，最大 100"),
    current_user: User = Depends(get_current_user)
):
    """出库单列表（普通用户只看自己的，管理员看全部）"""
    query = db.query(OutboundOrder)
    if current_user.role != Role.ADMIN:
        query = query.filter(OutboundOrder.applicant_id == current_user.id)
    if status:
        try:
            query = query.filter(OutboundOrder.status == OutboundStatus(status))
        except ValueError:
            raise BusinessException(code=400, message=f"无效的状态值: {status}")
    if product_id:
        query = query.filter(OutboundOrder.product_id == product_id)

    total, orders = paginate(query.order_by(OutboundOrder.id.desc()), page, page_size)
    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [OutboundResponse.model_validate(o) for o in orders]
    })

@router.get("/{order_id}")
def get_outbound(order_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """出库单详情"""
    order = db.query(OutboundOrder).filter(OutboundOrder.id == order_id).first()
    if not order:
        raise BusinessException(code=404, message="出库单不存在")
    if current_user.role != Role.ADMIN and order.applicant_id != current_user.id:
        raise BusinessException(code=403, message="只能查看自己的出库单")
    return success(data=OutboundResponse.model_validate(order))
