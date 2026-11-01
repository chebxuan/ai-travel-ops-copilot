# 当前架构与代码导航

当前旅客流程：目录 → 选项 → 英文逐日预览 → 服务端销售估算 → 签名快照 → 咨询与提醒事务 → 人工运营跟进。独立偏好表单只留资，不生成定制路线。

| 实现位置 | 职责 |
|---|---|
| `frontend/app`、`frontend/components` | 首页、产品预览、独立咨询、运营查询与状态页面 |
| `frontend/app/api`、`frontend/lib/server` | 同源代理、Origin 校验、服务端密钥与会话 |
| `backend/app/main.py`、`routers/travel.py` | 应用装配、API Key、v3 接口 |
| `services/travel_catalog.py`、`cost_scope.py`、`sales_pricing.py` | 产品查找、分支互斥、计费范围、成本与销售价格投影 |
| `services/enquiry_tokens.py`、`journey_enquiries.py` | 两小时 HMAC 签名、提交复核、幂等与提交后回执 |
| `routers/operations.py` | 独立运营签名认证、查询、状态乐观并发控制 |
| `services/enquiry_notifications.py` | 事务任务队列、租约、发送重试及旧回执保护 |
| `storage/`、`storage/migrations/` | PostgreSQL 读取、维护、导入及不可改写的已应用迁移 |
| `deploy/compose.yaml` | 数据、应用、边缘网络及可选通知出网网络 |

数据库角色分开：目录 `travel_app`、咨询 `travel_intake`、运营 `travel_ops`、提醒 `travel_notifier`、维护 `travel_owner`。业务请求不持有维护账户。快照读取采用可重复读，报价提交时再次核算，保留旧展示金额与当前复核结果。旧版本状态更新返回 409，状态历史与原始客户快照分开保存。

数据库模式下 PostgreSQL 是主数据，CSV 只是首次导入来源和文件模式演示基线；不长期双写。成本改价新增版本并审计，不能改历史报价来匹配新金额。数据库不可用返回 503，不回退过期文件报价。

本副本保留当前代码和规则拓扑，但价格、商业叙述和图片已经替换，不能用来还原生产数据。未配置数据库时表单拒绝写入；前端不会显示虚假成功。飞书提醒可能因外部回执丢失而重复，不宣称严格一次送达。

当前是单实例、单运营账户系统，没有高可用或吞吐量验证。没有 LLM、RAG、自动规划 Agent、订单、支付或自动邮件。
