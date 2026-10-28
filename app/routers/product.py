from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.pagination import paginate
from app.utils.exceptions import BusinessException
from app.models.product import Product
from app.models.category import Category
from app.models.inbound_order import InboundOrder
from app.models.outbound_order import OutboundOrder
from app.models.operation_log import OperationLog
from app.constants import LogAction, LogTarget
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.dependencies import get_current_admin, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/products", tags=["商品管理"])

# ===== 分类管理 =====

@router.post("")
def create_product(data: ProductCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_admin)):
    """创建商品（管理员）"""
    # 1. 检查 SKU 是否重复
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise BusinessException(code=400, message="商品编码已存在")

    # 2. 检查分类是否存在
    if data.category_id:
        cat = db.query(Category).filter(Category.id == data.category_id).first()
        if not cat:
            raise BusinessException(code=404, message="分类不存在")

    product = Product(
        sku=data.sku, name=data.name, category_id=data.category_id,
        unit=data.unit, total_qty=data.total_qty,
        frozen_qty=0, warning_qty=data.warning_qty,
        description=data.description
    )
    db.add(product)
    db.flush()   # 先拿到自增 id，供日志记录（仍属同一事务，尚未提交）

    db.add(OperationLog(
        user_id=current_user.id,
        action=LogAction.CREATE_PRODUCT,
        target=LogTarget.PRODUCT,
        target_id=product.id,
        detail=f"创建商品 {product.sku} {product.name}，初始库存 {product.total_qty}"
    ))

    try:
        db.commit()
    except IntegrityError:
        # 并发撞唯一索引：回滚并返回业务错误
        db.rollback()
        raise BusinessException(code=400, message="商品编码已存在")
    db.refresh(product)

    return success(data=ProductResponse.model_validate(product), message="创建成功")

@router.get("")
def list_products(
    db: Session = Depends(get_db),
    keyword: str | None = Query(default=None, description="按商品名/编码搜索"),
    category_id: int | None = Query(default=None, description="按分类筛选"),
    only_warning: bool = Query(default=False, description="只看库存预警的"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数，最大 100"),
    current_user: User = Depends(get_current_user)
):
    """商品列表（需登录，支持搜索/筛选）"""
    query = db.query(Product)

    if keyword:
        query = query.filter(
            (Product.name.contains(keyword)) | (Product.sku.contains(keyword))
        )
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if only_warning:
        # 口径：可用库存 = 总库存 - 冻结库存（被订单冻结的货已承诺出去，不能再算可售）
        query = query.filter((Product.total_qty - Product.frozen_qty) < Product.warning_qty)

    total, products = paginate(query.order_by(Product.id.desc()), page, page_size)
    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ProductResponse.model_validate(p) for p in products]
    })

@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """商品详情（需登录）"""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise BusinessException(code=404, message="商品不存在")
    return success(data=ProductResponse.model_validate(p))

@router.put("/{product_id}")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_admin)):
    """更新商品（管理员）"""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise BusinessException(code=404, message="商品不存在")

    # 逐个字段判断要不要更新（None 表示不改）
    update_data = data.model_dump(exclude_unset=True)

    # 只有 category_id 允许显式置空；其余字段传 null 一律视为"不修改"
    # （这些列要么 NOT NULL，要么响应模型不接受 null，直接写进去会 500 或留下脏数据）
    for key in ("name", "unit", "warning_qty", "description"):
        if update_data.get(key) is None:
            update_data.pop(key, None)

    # 如果改了分类，新分类必须存在（显式传 null 表示清空分类，允许）
    new_category_id = update_data.get("category_id")
    if new_category_id is not None:
        cat = db.query(Category).filter(Category.id == new_category_id).first()
        if not cat:
            raise BusinessException(code=404, message="分类不存在")

    for key, value in update_data.items():
        setattr(p, key, value)

    if update_data:
        db.add(OperationLog(
            user_id=current_user.id,
            action=LogAction.UPDATE_PRODUCT,
            target=LogTarget.PRODUCT,
            target_id=p.id,
            detail=f"更新商品 {p.sku}，修改字段: {', '.join(update_data.keys())}"
        ))

    db.commit()
    db.refresh(p)
    return success(data=ProductResponse.model_validate(p), message="更新成功")

@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_admin)):
    """删除商品（管理员）"""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise BusinessException(code=404, message="商品不存在")

    # 有出入库记录的商品不能删：历史单据指向它，待审批单还冻结着它的库存
    inbound_count = db.query(func.count(InboundOrder.id)).filter(
        InboundOrder.product_id == product_id
    ).scalar() or 0
    outbound_count = db.query(func.count(OutboundOrder.id)).filter(
        OutboundOrder.product_id == product_id
    ).scalar() or 0
    if inbound_count or outbound_count:
        raise BusinessException(
            code=400,
            message=f"该商品已有 {inbound_count} 条入库、{outbound_count} 条出库记录，无法删除"
        )

    db.add(OperationLog(
        user_id=current_user.id,
        action=LogAction.DELETE_PRODUCT,
        target=LogTarget.PRODUCT,
        target_id=p.id,
        detail=f"删除商品 {p.sku} {p.name}"
    ))
    db.delete(p)
    db.commit()
    return success(message="删除成功")
