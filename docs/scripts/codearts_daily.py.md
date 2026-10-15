# CodeArts 每日福利领取

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/codearts_daily.py`
- 青龙命令：`python3 scripts/codearts_daily.py`
- 建议 Cron：`52 1 * * *`
- 发布哈希：`d3e0054c92eb5b29dc45941cc17a17c808a5a3285cd816c099ac43c7d2578c17`
- 许可证：`MIT`

## 脚本功能

- 读取和只读预览福利活动（--preview 不续期、不写台账）
- 领取 USER_LOGIN 信用积分与一次性 NEW_USER_REGISTER 注册礼
- 领取、确认后同源回读，仅 CONFIRMED/CONSUMED 且不可再领取算到账
- 华为云 SDK-HMAC-SHA256 签名和临时凭据自动续期
- 持久化幂等台账、北京时间每日六次及十分钟间隔限制，--force 显式绕过
- --only 按原始账号序号选择、多账号独立执行和失败退出
- 青龙通知总开关、原有备用推送渠道、脱敏日志及单行任务总结
- 完全断网预演，不读写状态、不发送通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `CODEARTS_CREDENTIALS`

- 必填：是
- 敏感：是
- 获取或设置：在官方 CodeArts 客户端登录后，从自己的登录会话或 HTTPS 登录响应取得临时 access_key_id、secret_access_key、security_token。可选续期材料必须来自同一次授权：refresh_token、PKCE code_verifier、P-256 DPoP 私钥。不要使用其他产品的永久 AK/SK，也不要公开分享凭据；无需外部工具或仓库。
- 填写格式：每个非空行一个账号：单行 JSON（上述字段，可含 expiration、domain_id、user_name、oauth_context.pkce_pair.code_verifier、oauth_context.dpop_key_pair.private_key_jwk），或 AK|SK|STS；仅前两个 | 分隔字段，后续文本保留。兼容 accessKeyId/secretAccessKey/securityToken 和 ak/sk/sts 别名。

### 可选参数

### `CODEARTS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：自行设置为 1 启用完全断网预演，不读写状态，不发送通知，不验证真实业务。
- 填写格式：1、true、yes、on 启用，其余关闭

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关，默认 1。
- 填写格式：0、false、no、off 关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选：指定青龙已有 notify.py 所在目录；否则自动发现标准路径。
- 填写格式：目录路径

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：从 PushPlus 个人设置取得推送令牌；作为原有备用推送渠道，不输出配置。
- 填写格式：单个渠道配置值；地址必须为 HTTPS

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：从自己的 Bark 客户端取得 HTTPS 推送地址；作为原有备用推送渠道，不输出配置。
- 填写格式：单个渠道配置值；地址必须为 HTTPS

### `WECOM_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从企业微信群机器人设置取得 HTTPS 地址或机器人密钥；作为原有备用推送渠道，不输出配置。
- 填写格式：单个渠道配置值；地址必须为 HTTPS

### `DINGTALK_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：从钉钉群自定义机器人设置取得 HTTPS 地址；作为原有备用推送渠道，不输出配置。
- 填写格式：单个渠道配置值；地址必须为 HTTPS

### `DINGTALK_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：从同一钉钉机器人取得可选加签密钥；作为原有备用推送渠道，不输出配置。
- 填写格式：单个渠道配置值；地址必须为 HTTPS

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，JSON 必须为单行；不按 & 或 @ 拆分账号。账号独立执行，无效账号计失败，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `d3e0054c92eb5b29dc45941cc17a17c808a5a3285cd816c099ac43c7d2578c17`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b896028c3fdcd52d`。

## 副作用与风险

- 领取福利积分与新人奖励
- 确认福利到账
- 使用可选续期材料刷新登录凭据
- 写入私有凭据缓存和领取幂等台账
- 发送脱敏通知（预演只模拟）

## 许可证与来源

上游 `L0NE-6/CodeArts-Daily` / `codearts_daily.py` / `c337a9340877cdf7afef0a679f3d020d28183140`。
