# 棕色尘埃2网页商店签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_8591af9a.py`
- 青龙命令：`python3 scripts/task_8591af9a.py`
- 建议 Cron：`29 9 * * *`
- 发布哈希：`84e0f91dd500a5e99673c2bd11cee7c4d3ac7f7047bffbee6eb90effe666c949`
- 许可证：`MIT`

## 脚本功能

- 对棕色尘埃2网页商店执行每日出席签到
- 执行每周出席签到
- 查询进行中的出席活动并完成活动出席签到
- 支持每行一个 accessToken 的多账号独立处理，任一账号失败时整体非零退出
- 提供完全断网预演、时间轴脱敏日志、账号与任务统计及单行 TASK_SUMMARY
- 按青龙全局开关发送脱敏通知，通知故障不改变业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `BD2_ACCESS_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：登录 https://webshop.browndust2.global/CT/（可用 Google 账号），按 F12 打开开发者工具 → Console，执行 JSON.parse(localStorage.getItem("session-storage")).state.session.accessToken，将返回的 accessToken 写入青龙环境变量。不要把 Token 发给他人或写入公开仓库、日志、通知。
- 填写格式：每个非空行一个账号的 Bearer accessToken；不要用 &、@ 或其他符号分隔账号。行首可带 Bearer 前缀（会自动去掉）。以 # 开头的行忽略。

### 可选参数

### `BD2_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当未设置 BD2_ACCESS_TOKEN 时读取；获取方式与规范变量相同。
- 填写格式：与 BD2_ACCESS_TOKEN 相同。

### `BD2_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要在完全断网条件下检查配置与流程时设置。
- 填写格式：设为 1、true、yes 或 on 启用预演。

### `BD2_SKIP_EVENT`

- 必填：否
- 敏感：否
- 获取或设置：只想执行每日与每周签到、跳过活动出席时设置。
- 填写格式：设为 1、true、yes 或 on 跳过活动出席。

### `BD2_DAILY_ONLY`

- 必填：否
- 敏感：否
- 获取或设置：仅执行每日签到、跳过每周与活动出席时设置。
- 填写格式：设为 1、true、yes 或 on 仅每日签到。

### `BD2_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络状况设置单次 HTTPS 超时；不填写时为 15 秒。
- 填写格式：5 至 120 之间的整数秒。

### `BD2_ACCOUNT_DELAY_SEC`

- 必填：否
- 敏感：否
- 获取或设置：多账号连续执行时的间隔秒数；不填写时为 1 秒。预演模式不等待。
- 填写格式：0 至 600 之间的整数秒。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在 QINGLONG_NOTIFY=auto 时填写要通知的脚本选择器。
- 填写格式：可用逗号、分号、空白或换行分隔；支持 8591af9ab9d3293b、candidate.py、output/candidate.py、bd2_webshop_signin.py、通配符或 *。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙 notify.py 不在默认位置时，填写其所在目录。
- 填写格式：包含 notify.py 的本地目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

BD2_ACCESS_TOKEN（或兼容别名 BD2_TOKEN）每个非空行一个 accessToken；账号之间仅用换行分隔。逐账号独立执行每日/每周/活动出席，任一账号失败时进程整体返回非零退出码。

## 验证与兼容性

SHA-256 `84e0f91dd500a5e99673c2bd11cee7c4d3ac7f7047bffbee6eb90effe666c949`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8591af9ab9d3293b`。

## 副作用与风险

- 向网页商店提交每日出席签到，奖励发送到游戏内邮箱
- 向网页商店提交每周出席签到，奖励发送到游戏内邮箱
- 向网页商店提交活动出席签到并领取当日活动奖励

## 许可证与来源

上游 `XiaoYiWeio/brown-dust-2` / `scripts/signin.py` / `010a7f1f82ea224a70c14700443ba4768b62476b`。
