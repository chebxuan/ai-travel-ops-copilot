# 演示运营与通知

运营入口 `/ops`，通过 `scripts/configure_operations.py --target production` 配置本副本账户。独立后端密钥、会话签名和密码哈希只在服务端保存，不提供线上账号，不把密钥放进 `NEXT_PUBLIC_*`。

咨询写入受限账户，运营读写另一受限账户。状态更新需携带版本，旧版本返回 409。原始方案和价格快照保留，状态变化另写审计事件。

飞书默认关闭。需要自行创建的演示群机器人时，在本地私有的 `deploy/.env.production` 设置自己的 `FEISHU_WEBHOOK_URL`、`FEISHU_SIGNING_SECRET` 与 `FEISHU_NOTIFICATIONS_ENABLED=1`，再由运行者执行：

```bash
bash deploy/compose.sh --profile notifications up -d notifications
```

这会产生真实消息，只向自己配置的演示群发送。此仓库不含任何生产 webhook。咨询与任务同事务保存，通知程序异步领取租约并发送/重试；外部回执丢失可能重复，编号用于辨认。咨询接收不代表预订确认。
