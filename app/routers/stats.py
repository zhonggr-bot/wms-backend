from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.utils.response import success
from app.models.product import Product
from app.models.outbound_order import OutboundOrder, OutboundStatus
from app.models.inbound_order import InboundOrder
from app.models.user import User
from app.schemas.product import WarningProductResponse
from app.dependencies import get_current_admin, get_current_user

router = APIRouter(prefix="/api/stats", tags=["数据统计"])

@router.get("/warning")
def get_warning_products(db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    """
    库存预警列表：可用库存（总库存 - 冻结库存）< 预警阈值的商品
    需登录（普通用户也能查，方便知道哪些商品快没了）
    """
    warnings = db.query(Product).filter(
        (Product.total_qty - Product.frozen_qty) < Product.warning_qty
    ).all()
    result = [
        WarningProductResponse(
            product_id=p.id,
            sku=p.sku,
            name=p.name,
            total_qty=p.total_qty,
            frozen_qty=p.frozen_qty,
            available_qty=p.total_qty - p.frozen_qty,
            warning_qty=p.warning_qty,
            shortage=p.warning_qty - (p.total_qty - p.frozen_qty)   # 还差多少才到阈值
        )
        for p in warnings
    ]
    return success(data=result, message=f"共 {len(result)} 个商品库存预警")

@router.get("/overview")
def get_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    """系统概览（仅管理员）"""
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_inbound = db.query(func.count(InboundOrder.id)).scalar() or 0
    total_outbound = db.query(func.count(OutboundOrder.id)).scalar() or 0
    pending_outbound = db.query(func.count(OutboundOrder.id)).filter(
        OutboundOrder.status == OutboundStatus.PENDING
    ).scalar() or 0
    warning_count = db.query(func.count(Product.id)).filter(
        (Product.total_qty - Product.frozen_qty) < Product.warning_qty
    ).scalar() or 0

    return success(data={
        "total_products": total_products,
        "total_users": total_users,
        "total_inbound_orders": total_inbound,
        "total_outbound_orders": total_outbound,
        "pending_outbound": pending_outbound,
        "warning_products": warning_count
    })
