# Rousi 签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/rousi_checkin.js`
- 青龙命令：`node scripts/rousi_checkin.js`
- 建议 Cron：`42 0 * * *`
- 发布哈希：`3e3691671ccef16a6aa0cfea6b9d0324678e7fb25912caf04219efadc091b5c6`
- 许可证：`MIT`

## 脚本功能

- 每天执行普通签到，并依据服务端今日日期识别已签到状态以避免重复提交
- 读取并展示站点自定义名称的积分余额、连续签到天数和累计签到天数
- 读取并展示分享率、当前魔力值以及累计上传和下载量
- 签到成功后展示本次奖励、连续签到奖励和当前连续签到天数
- 兼容 Token、Bearer 前缀、Cookie、小写变量和编号变量，并支持逐行多账号
- 可选通过 HTTPS 发送 PushPlus 汇总通知，并兼容原有渠道参数
- 在成功、部分失败、失败、配置错误和预演后生成脱敏总结，并按青龙全局开关尝试通知
- 提供完全断网预演、分阶段时间轴日志、账号统计、任务统计和单行 TASK_SUMMARY 记录

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ROUSI_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：登录 Rousi 后打开浏览器开发者工具，在网络面板选择站内 API 请求，复制 Authorization 请求头中 Bearer 后面的值；也兼容保留 Bearer 前缀。小写变量和编号变量 ROUSI_TOKEN_1 至 ROUSI_TOKEN_20 仅用于旧配置兼容。
- 填写格式：每个非空行一个账号的 Token，不得使用 &、空格或其他符号分隔账号。

### 可选参数

### `ROUSI_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：仅在无法使用 Token 时，从已登录 Rousi 的站内 API 请求头复制完整 Cookie；小写变量和编号变量 ROUSI_COOKIE_1 至 ROUSI_COOKIE_20 仅用于旧配置兼容。
- 填写格式：每个非空行一个账号的完整 Cookie；Cookie 内的 & 会原样保留。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：在 PushPlus 控制台创建推送令牌；不需要额外通知时不要设置。
- 填写格式：单个 PushPlus 令牌；兼容旧变量 pushplus_token。

### `PUSHPLUS_TYPE`

- 必填：否
- 敏感：否
- 获取或设置：按 PushPlus 已开通的通知渠道填写；未设置时使用普通推送。
- 填写格式：可填写 pushplusvip、wxgo、qywxgo、email、feishu、dingtalk 或 bark。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：由青龙全局通知策略设置，用于限定需要发送通知的脚本。
- 填写格式：可使用 catalogId、scripts/rousi_checkin.js、rousi_checkin.js、文件名通配符或 *；多个选择器使用逗号、分号、空白或换行分隔，空值表示全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知脚本不在标准目录时，填写包含 notify.py 或 sendNotify.js 的目录。
- 填写格式：本机绝对目录路径。

### `ROUSI_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：仅在预演或烟雾测试时设置，正式运行时删除或设为 0。
- 填写格式：1、true、yes 或 on 表示启用完全断网预演。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

ROUSI_TOKEN 或 ROUSI_COOKIE 每个非空行表示一个账号；同一账号只需选择一种认证方式。脚本逐个独立处理账号，任一账号失败时整体以非零状态退出。

## 验证与兼容性

SHA-256 `3e3691671ccef16a6aa0cfea6b9d0324678e7fb25912caf04219efadc091b5c6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3c5c6df4d8a81a7f`。

## 副作用与风险

- 正式运行且账号当天未签到时提交普通签到，更新签到记录并领取服务端积分奖励
- 正式运行且通知开启时，向青龙已配置的通知渠道发送脱敏任务总结
- 正式运行且配置 PushPlus 时，向该通知渠道发送脱敏任务总结

## 许可证与来源

上游 `373065025/rousi-checkin` / `rousi_checkin.js` / `627ec698dc9d35f69f44e479366a7c31dd46489c`。
