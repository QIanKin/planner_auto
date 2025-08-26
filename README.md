## Planner-Feishu-Gemini (Multi-User, No-Server)

多用户计划→Gemini→飞书机器人定时推送。完全运行在 GitHub Actions，无服务器、支持时区与签名校验、产出 JSON 并落盘。

### 特性
- 多用户：`data/users.csv` 一行一人，独立时区/Webhook/签名
- 无服务器：通过 GitHub Actions `*/15` 定时触发，窗口命中 07:00 ±7 分钟
- 安全：API Key 在 Secrets，飞书签名按用户在 `users.csv` 的 `feishu_secret` 配置
- 健壮：优先严格 JSON，解析失败自动降级纯文本
- 可观测：JSON 写入 `data/agendas/YYYY-MM-DD/{public_id}.json`；发送日志 `data/deliveries.csv`

### 快速开始
1. 复制本仓库结构到你的新仓库
2. 填写 `data/users.csv` 与 `data/plans/*.md`（示例已提供）
3. 仓库 Settings → Secrets and variables → Actions：添加 `GOOGLE_API_KEY`（必填）
4. Actions 页面手动 Run Workflow 验证；或暂时把 `app/timewin.py` 的 `in_push_window` 改为恒 `True` 以立即验证
5. 等到用户本地时区的 07:00，自动推送

### 依赖
见 `requirements.txt`。

### 注意事项
- Gemini 配额需足够；文本长度控制在 800 字以内
- 开启飞书签名时，请在 `data/users.csv` 为该用户设置 `feishu_secret`
- 仓库为 UTF-8 编码；Windows 下注意换行

### 扩展方向
- 增加企业微信/邮件通道
- 多时间档推送（上午/下午）
- 从飞书多维表/表格读取计划
- 失败重试与指数退避、Sentry 观测

### 测试清单
1. `users.csv` 中 `active=false` 不推送；`active=true` 才推送
2. 删除/留空 webhook → 发送失败并记录到 `data/deliveries.csv`
3. JSON 模式成功：生成 `data/agendas/YYYY-MM-DD/{public_id}.json` 且消息按 JSON 渲染
4. JSON 解析失败：降级文本模式仍能推送
5. 时区改为 `Asia/Tokyo`：确认东京 07:00 窗口触发
6. 修改计划文件时间戳：以最新修改的文件为准
