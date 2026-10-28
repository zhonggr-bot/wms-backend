"""
一键初始化脚本：创建默认管理员账号 + 示例分类 + 示例商品
用法：python scripts/seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Base, engine
from app.models.user import User, Role
from app.models.category import Category
from app.models.product import Product
from app.utils.password_utils import hash_password


def seed():
    created = []   # 记录本次真正新建了什么，供最后统一打印

    with SessionLocal() as db:
        # ========== 1. 确保所有表存在 ==========
        Base.metadata.create_all(bind=engine)
        print("数据库表已就绪")

        # ========== 2. 创建管理员账号（如果不存在）==========
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            db.add(User(username="admin", password=hash_password("123456"), role=Role.ADMIN))
            created.append("管理员账号 admin / 123456")
        else:
            print("管理员账号已存在，跳过")

        # ========== 3. 创建一个普通用户 ==========
        user = db.query(User).filter(User.username == "user01").first()
        if not user:
            db.add(User(username="user01", password=hash_password("123456"), role=Role.USER))
            created.append("普通用户 user01 / 123456")
        else:
            print("普通用户已存在，跳过")

        # ========== 4. 创建示例分类 ==========
        categories_data = [
            ("办公用品", "日常办公耗材"),
            ("电子产品", "电子设备及配件"),
            ("生产物料", "生产线原材料"),
        ]
        cat_objects = {}
        for name, desc in categories_data:
            cat = db.query(Category).filter(Category.name == name).first()
            if not cat:
                cat = Category(name=name, description=desc)
                db.add(cat)
                db.flush()   # 拿到自增 id（事务内执行，尚未提交）
                created.append(f"分类 {name}")
            cat_objects[name] = cat

        # ========== 5. 创建示例商品 ==========
        products_data = [
            ("A4纸", "PAPER-A4-001", "办公用品", "包", 200, 20),
            ("中性笔", "PEN-BLACK-002", "办公用品", "盒", 150, 30),
            ("机械键盘", "KB-MECH-003", "电子产品", "个", 50, 10),
            ("无线鼠标", "MOUSE-WL-004", "电子产品", "个", 80, 15),
            ("U盘32G", "USB-32G-005", "电子产品", "个", 30, 10),
            ("螺丝M4", "SCREW-M4-006", "生产物料", "箱", 5000, 500),
        ]
        for name, sku, cat_name, unit, qty, warning in products_data:
            existing = db.query(Product).filter(Product.sku == sku).first()
            if not existing:
                db.add(Product(
                    sku=sku,
                    name=name,
                    category_id=cat_objects[cat_name].id,
                    unit=unit,
                    total_qty=qty,
                    frozen_qty=0,
                    warning_qty=warning
                ))
                created.append(f"商品 {name}（库存 {qty}）")

        # ========== 6. 全部成功后统一提交 ==========
        db.commit()

    # ========== 7. 提交成功后再打印结果，避免回滚时误报成功 ==========
    print("\n初始化完成")
    if created:
        for item in created:
            print(f"  已创建: {item}")
    else:
        print("  所有初始数据均已存在，未做任何变更")
    print("管理员账号: admin / 123456")
    print("普通用户:   user01 / 123456")


if __name__ == "__main__":
    seed()
