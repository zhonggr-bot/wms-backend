from pydantic import BaseModel, ConfigDict, Field, computed_field
from datetime import datetime

# ===== 分类 =====

class CategoryCreate(BaseModel):
    """创建分类"""
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)

class CategoryResponse(BaseModel):
    """分类响应"""
    id: int
    name: str
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== 商品 =====

class ProductCreate(BaseModel):
    """创建商品"""
    sku: str = Field(..., min_length=1, max_length=50, description="商品编码")
    name: str = Field(..., min_length=1, max_length=100)
    category_id: int = Field(..., description="分类ID")
    unit: str = Field(default="件", max_length=20)
    total_qty: int = Field(default=0, ge=0, description="初始库存")
    warning_qty: int = Field(default=10, ge=0, description="预警阈值")
    description: str = Field(default="", max_length=500)

class ProductUpdate(BaseModel):
    """更新商品（所有字段可选）"""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: int | None = Field(default=None)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    warning_qty: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=500)

class ProductResponse(BaseModel):
    """商品响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category_id: int | None
    unit: str
    total_qty: int
    frozen_qty: int
    warning_qty: int
    description: str
    created_at: datetime

    @computed_field
    @property
    def available_qty(self) -> int:
        """可用库存 = 总库存 - 冻结库存（序列化时自动计算）"""
        return self.total_qty - self.frozen_qty


class WarningProductResponse(BaseModel):
    """库存预警条目"""
    product_id: int
    sku: str
    name: str
    total_qty: int
    frozen_qty: int
    available_qty: int
    warning_qty: int
    shortage: int


# ===== 入库单 =====

class InboundCreate(BaseModel):
    """创建入库单"""
    product_id: int = Field(..., description="商品ID")
    quantity: int = Field(..., gt=0, description="入库数量（必须大于0）")
    remark: str = Field(default="", max_length=500)

class InboundResponse(BaseModel):
    """入库单响应"""
    id: int
    product_id: int
    quantity: int
    operator_id: int
    remark: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== 出库单 =====

class OutboundCreate(BaseModel):
    """创建出库申请"""
    product_id: int = Field(..., description="商品ID")
    quantity: int = Field(..., gt=0, description="申请数量")
    remark: str = Field(default="", max_length=500)

class OutboundApprove(BaseModel):
    """管理员审批"""
    approve: bool = Field(..., description="True=通过, False=驳回")
    reject_reason: str = Field(default="", max_length=500, description="驳回原因（驳回时必填）")

class OutboundResponse(BaseModel):
    """出库单响应"""
    id: int
    product_id: int
    quantity: int
    applicant_id: int
    approver_id: int | None
    status: str
    reject_reason: str
    remark: str
    approved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
