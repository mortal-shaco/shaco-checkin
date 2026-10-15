# 大潮App签到阅读

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/dachao.py`
- 青龙命令：`python3 scripts/dachao.py`
- 建议 Cron：`22 10,14,18 * * *`
- 发布哈希：`c32ca074fd97eac903444e3ffb4c4e4e9fe6d0f446c68b686ab276fe9c07a302`
- 许可证：`MIT`

## 脚本功能

- 账号密码登录及官方昵称展示
- 动态发现签到和阅读活动
- 签到及已签到状态判断
- 阅读任务、实际等待及阅读时长上报
- 阅读滑块验证码三种算法求偏移并重试
- 显式开启签到抽奖和阅读抽奖
- 显式开启现金红包兑换及无效兑换码短暂重试
- 多账号隔离、失败闭合及单行结构化汇总
- 青龙通知与完全断网配置预演

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `DACHAO_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：使用本人账号在大潮App登录时抓取 HTTPS 请求。passport.tmuyun.com/web/oauth/credential_auth 表单提供 phone_number、password（填到 password_encrypted）、client_id；请求头提供 User-Agent（填到 user_agent）及可选 Cookie。vapp 登录请求头提供 tenant_id 和登录前 session_id；默认 tenant_id=94、client_id=10048。不要填明文密码，不要分享抓包文件。兑换 member 仅在本人微信领取红包请求中取得，与登录 member 不同。
- 填写格式：每个非空行是一个完整 JSON 对象，不用 & 或 @ 分隔账号。必填字段 phone_number、password_encrypted、user_agent；兼容 password、user_agent_vapp、user_agent_aihoge。可选字段 account_name、tenant_id、client_id、session_id、passport_cookies、vapp_cookies、aihoge_cookies（兼容 cookies）、passport_signature_salt、aihoge_signature_salt、sign_lottery_id、redeem_member（兼容 withdraw_member）、redeem_cookies、redeem_user_agent。Cookie 和 member 保留原字符串（JSON 内引号须转义）。forum_session_id、forum_cookies、forum_tenant_id 兼容读取但原主任务没有论坛动作。

### 可选参数

### `DACHAO_MODE`

- 必填：否
- 敏感：否
- 获取或设置：自行选择需要运行的任务；也可使用 --mode 参数。
- 填写格式：all（默认签到和阅读）、sign（签到）、read（阅读）

### `DACHAO_MAX_ARTICLES`

- 必填：否
- 敏感：否
- 获取或设置：自行设置单次阅读上限；兼容 --max-articles。
- 填写格式：1 至 100 的整数，默认 6

### `DACHAO_LOTTERY`

- 必填：否
- 敏感：否
- 获取或设置：确认允许使用活动抽奖次数后开启。签到抽奖需在账号 JSON 中填本人活动页面的 sign_lottery_id；阅读抽奖编号由官方阅读列表获取。
- 填写格式：默认 0；1 开启签到和阅读抽奖

### `DACHAO_REDEEM`

- 必填：否
- 敏感：否
- 获取或设置：确认允许兑换现金红包后开启，同时填写账号 JSON 内的 redeem_member；仅抽到现金红包时使用。
- 填写格式：默认 0；1 开启兑换，需同时开启抽奖

### `DACHAO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：验证配置时设为 1；无需安装业务依赖即可运行预演。
- 填写格式：1 为完全断网预演；默认 0 为实际执行

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知全局开关。实际执行时尝试 notify.send 或青龙 notify.py；缺失、失败或超过20秒只记录通知失败，保留业务退出码。
- 填写格式：默认 1；0、false、no、off 关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：通知模块不在标准青龙目录时填写 notify.py 所在目录。
- 填写格式：可选目录路径，仅用于青龙通知；业务运行不依赖私有文件

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON 对象，配套凭据置于同一对象，独立校验和执行；任何账号配置或业务失败时整体非零退出。

## 验证与兼容性

SHA-256 `c32ca074fd97eac903444e3ffb4c4e4e9fe6d0f446c68b686ab276fe9c07a302`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7b77205efaf0158a`。

## 副作用与风险

- 签到改变签到记录及活动积分
- 完成阅读任务并上报阅读时长
- 开启抽奖后消耗活动抽奖次数并获得奖励
- 开启兑换后领取现金红包

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/dachao/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
