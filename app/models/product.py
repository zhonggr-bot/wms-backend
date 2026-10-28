from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), unique=True, nullable=False)               # 商品编码，唯一（unique 已自带索引）
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))          # 外键：指向分类表
    unit = Column(String(20), default="件")                             # 单位：件/箱/个
    total_qty = Column(Integer, default=0, nullable=False)              # 总库存
    frozen_qty = Column(Integer, default=0, nullable=False)             # 冻结库存
    warning_qty = Column(Integer, default=10)                           # 预警阈值
    description = Column(String(500), default="")
    created_at = Column(DateTime, server_default=func.now())
