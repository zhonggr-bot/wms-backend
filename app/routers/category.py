from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.exceptions import BusinessException
from app.models.category import Category
from app.models.product import Product
from app.models.operation_log import OperationLog
from app.constants import LogAction, LogTarget
from app.schemas.product import CategoryCreate, CategoryResponse
from app.dependencies import get_current_admin, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/categories", tags=["商品分类"])

# ===== 只有管理员能增删改，普通用户能查 =====

@router.post("")
def create_category(data: CategoryCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_admin)):
    """创建分类（管理员）"""
    existing = db.query(Category).filter(Category.name == data.name).first()
    if existing:
        raise BusinessException(code=400, message="分类名已存在")
    cat = Category(name=data.name, description=data.description)
    db.add(cat)
    db.flush()   # 先拿到自增 id，供日志记录

    db.add(OperationLog(
        user_id=current_user.id,
        action=LogAction.CREATE_CATEGORY,
        target=LogTarget.CATEGORY,
        target_id=cat.id,
        detail=f"创建分类 {cat.name}"
    ))

    try:
        db.commit()
    except IntegrityError:
        # 并发撞唯一索引：回滚并返回业务错误
        db.rollback()
        raise BusinessException(code=400, message="分类名已存在")
    db.refresh(cat)
    return success(data=CategoryResponse.model_validate(cat), message="创建成功")

@router.get("")
def list_categories(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """分类列表（需登录）"""
    cats = db.query(Category).order_by(Category.id.desc()).all()
    return success(data=[CategoryResponse.model_validate(c) for c in cats])

@router.get("/{cat_id}")
def get_category(cat_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """单个分类详情（需登录）"""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise BusinessException(code=404, message="分类不存在")
    return success(data=CategoryResponse.model_validate(cat))

@router.put("/{cat_id}")
def update_category(cat_id: int, data: CategoryCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_admin)):
    """更新分类（管理员）"""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise BusinessException(code=404, message="分类不存在")

    # 改名也要查重，但要把自己排除掉（改成自己原来的名字是允许的）
    duplicate = db.query(Category).filter(
        Category.name == data.name, Category.id != cat_id
    ).first()
    if duplicate:
        raise BusinessException(code=400, message="分类名已存在")

    cat.name = data.name
    cat.description = data.description

    db.add(OperationLog(
        user_id=current_user.id,
        action=LogAction.UPDATE_CATEGORY,
        target=LogTarget.CATEGORY,
        target_id=cat.id,
        detail=f"更新分类 {cat.name}"
    ))

    db.commit()
    return success(data=CategoryResponse.model_validate(cat), message="更新成功")

@router.delete("/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_admin)):
    """删除分类（管理员）"""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise BusinessException(code=404, message="分类不存在")

    # 分类下还有商品时不能删，否则商品的外键会指向一个不存在的分类
    product_count = db.query(func.count(Product.id)).filter(
        Product.category_id == cat_id
    ).scalar() or 0
    if product_count:
        raise BusinessException(code=400, message=f"该分类下还有 {product_count} 个商品，无法删除")

    db.add(OperationLog(
        user_id=current_user.id,
        action=LogAction.DELETE_CATEGORY,
        target=LogTarget.CATEGORY,
        target_id=cat.id,
        detail=f"删除分类 {cat.name}"
    ))
    db.delete(cat)
    db.commit()
    return success(message="删除成功")
