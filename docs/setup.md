# 公开副本的运行与验证

## 文件模式：浏览和估算

先按 README 安装 Python 和前端依赖。复制根目录 `.env.example` 为 `.env`，在本地将 `API_KEY` 改为随机值。复制 `frontend/.env.example` 为 `frontend/.env.local`，将 `BACKEND_API_KEY` 设置为相同值。不要使用线上密钥。

后端（仓库根目录）：

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端（另一个终端）：

```bash
cd frontend
npm run dev
```

打开 `http://localhost:3000`，从首页目的地卡片进入选择器。直接打开 `/plan` 是独立咨询表单。数据库未配置时表单会返回不可用；不会存到 JSON、发送邮件或联系线上运营。

## 完整存储：隔离的演示数据库

建议使用本仓库 Compose 和新的数据卷，避免连接现有数据库。在仓库根目录生成本副本的配置：

```bash
.venv/bin/python deploy/configure.py --site http://localhost
.venv/bin/python scripts/configure_operations.py --target production
bash deploy/compose.sh up -d --build
```

“production”是配置文件的命名，不表示会连接线上。这里的 `.env.production` 仅在本副本中生成；脚本随机生成数据库和 API 密码，交互设置新的运营账户。默认飞书关闭。Compose 的 `migrate` 初始化空库、应用迁移、导入演示目录并分配角色，已有维护数据不会被覆盖导入。

打开 `http://localhost`，可测试虚构咨询与 `/ops`。若本机 80/443 已被占用，先配置 `HTTP_PORT`、`HTTPS_PORT` 及与实际访问地址一致的 `SITE_ADDRESS`、`SITE_ORIGIN`；保持 Origin 一致。无需上传到 AWS 即可读代码和运行测试。

实际发布时将 site 设为自己的域名，使用新凭据并按需配置 HTTPS 与备份。不复制本项目生产配置，不连接线上业务库。飞书可选配置见 [运营说明](operations-guide.md)。

## 校验

```bash
.venv/bin/python -B scripts/verify_project.py
.venv/bin/python -B scripts/check_public_release.py
.venv/bin/python -B scripts/database.py audit
cd frontend
npm run lint
npm run test:origin
npm run test:enquiry-id
npm run test:ops
npm run build
```

默认项目检查显式使用文件模式，不启动服务、不调用模型或飞书。`database.py audit` 只检查导入来源的引用与结构。数据库测试必须使用独立测试库并显式设置 `RUN_DATABASE_TESTS=1`；不要用生产数据满足断言。本次公开副本没有启动服务或数据库，也没有重新进行线上验收。

合成数据派生文件可用 `scripts/normalize_product_library.py` 和 `scripts/export_frontend_products.py` 重新生成。
