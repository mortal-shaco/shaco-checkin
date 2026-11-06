# WorkBuddy 每日签到与成长中心

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/get_token.py`
- 青龙命令：`python3 scripts/get_token.py`
- 建议 Cron：`51 0,4,8,12,16,20 * * *`
- 发布哈希：`e7442b7b4c533d02ef790c245aaafe3cd8fa2e0162245d97618c34cc25403b76`
- 许可证：`MIT`

## 脚本功能

- 每日签到、状态查询、已签到及活动未开启识别
- 成长中心旅行礼物、接取任务、领取任务奖励和三档连登兑换
- 能量、连登、旅行状态展示及实物中奖收件提醒
- 独立开关控制派遣、按服务端日历补登、抽奖、能量开 Buddy
- 兼容上游命令名称；离线凭据诊断、按行多账号及断网预演
- 阶段脱敏日志、结构化业务结果、单行任务汇总及青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WORKBUDDY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录自己的 WorkBuddy，在开发者工具网络面板查看官方签到请求：Authorization 去掉 Bearer 前缀填入 auth.accessToken，X-User-Id 填入 account.uid；如有租户和域请求头，分别填入 account.enterpriseId、auth.domain。加密字段不能直接使用。
- 填写格式：每个非空行一个 JSON 对象；必填 auth.accessToken、account.uid；可选 account.enterpriseId、auth.domain；auth.endpoint 仅允许 https://copilot.tencent.com

### 可选参数

### `WB_ACCESS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容关联工具的令牌变量，从自己登录后的官方请求取得；规范变量为空时使用。
- 填写格式：每行一个令牌，不含 Bearer 前缀

### `WORKBUDDY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙设置预演开关；业务与通知均不联网。
- 填写格式：1 开启，默认关闭

### `WORKBUDDY_ACTION`

- 必填：否
- 敏感：否
- 获取或设置：在青龙设置任务动作，命令行参数优先。
- 填写格式：auto 默认；兼容 silent、silent-poll、silent-growth、growth、status、claim、all、doctor

### `WORKBUDDY_BUDGET_SECONDS`

- 必填：否
- 敏感：否
- 获取或设置：按每账号执行时限配置。
- 填写格式：正数秒；普通任务默认 420，上限 540；轮询默认 180，上限 240

### `WORKBUDDY_DEPART`

- 必填：否
- 敏感：否
- 获取或设置：确认接受自动派遣旅行后自行开启。
- 填写格式：1 开启，默认 0 关闭

### `WORKBUDDY_MAKEUP`

- 必填：否
- 敏感：否
- 获取或设置：确认接受消耗补登卡，每轮最多一天后自行开启。
- 填写格式：1 开启，默认 0 关闭

### `WORKBUDDY_LOTTERY`

- 必填：否
- 敏感：否
- 获取或设置：确认接受消耗抽奖机会，每轮一次后自行开启。
- 填写格式：1 开启，默认 0 关闭

### `WORKBUDDY_BUDDY_OPEN`

- 必填：否
- 敏感：否
- 获取或设置：确认接受消耗能量开 Buddy后自行开启。
- 填写格式：1 开启，默认 0 关闭

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：设置需通知的脚本选择列表；未设置时本任务默认启用。
- 填写格式：逗号、分号或空白分隔来源标识、相对路径、文件名或通配符；空值禁用，* 全选

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，指定青龙 notify.py 或 sendNotify.js 所在目录；同时支持标准青龙脚本目录及 notify 模块。
- 填写格式：本机通知模块目录

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号会话 JSON，同账号配套凭据合并在对象中；兼容令牌别名同样每行一个账号。独立执行，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `e7442b7b4c533d02ef790c245aaafe3cd8fa2e0162245d97618c34cc25403b76`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/51413af773dd1c9a`。

## 副作用与风险

- 领取签到积分
- 领取旅行礼物、接取任务、领取任务及连登兑换奖励
- 显式开启后派遣旅行、使用补登卡、消耗抽奖机会及能量
- 通知开启时发送脱敏结果

## 许可证与来源

上游 `firlsy/ql_scripts-AI_auto_sign` / `get_token/signin.py` / `820b611ad874f8282a23d90b621afd68e66d0960`。
