# Synthetic demo data

所有金额为固定演示算法生成，非原始成本、市场价格或供应商报价。产品介绍重新编写，图片采用原创 SVG 占位图。只在隔离演示环境使用。

`products/product_library.csv` → `scripts/normalize_product_library.py` → `products.normalized.json` → `scripts/export_frontend_products.py` → 前端白名单内容。

`products/services/mashes/` 是合成服务成本，`cost_scope.json` 维护演示分支和服务范围。数据库模式下以 PostgreSQL 为主，不长期与文件双写。详见 `docs/publication.md`。
