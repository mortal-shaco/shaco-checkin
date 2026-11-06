# 智谱清言每日领分与余额

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/content.js`
- 青龙命令：`node scripts/content.js`
- 建议 Cron：`37 9 * * *`
- 发布哈希：`39eae8fc5e20fefb8bc9bd0309e1b76a2f49a2e897e041ba34b2e6e36ddf1c2b`
- 许可证：`MIT`

## 脚本功能

- 领取智谱清言每日积分，明确识别成功与今日已领取
- 查询官方账号身份及积分余额，领取后再次核对余额
- 每行一个账号独立运行，失败账号不阻断其他账号，任一失败整体非零退出
- 显式开启后支持 401 令牌续期，兼容原值与 Bearer 认证并重新尝试原请求
- 可选择仅查询余额，提供完全断网预演、脱敏分阶段日志、结构化汇总及青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ZHIPU_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：本人登录智谱清言 https://chatglm.cn 后，在浏览器开发者工具 Network 查看 /chatglm/user-api/user/info 请求；复制 Authorization 去掉 Bearer 前缀作为 access，复制 X-Device-Id 作为 device_id。同一账号可选 refresh 来自本站 Cookie chatglm_refresh_token。仅填入青龙私密变量，不分享令牌或截图。
- 填写格式：每个非空行一个 JSON 对象，包含字符串 access、device_id，可选字符串 refresh；账号之间只用换行。device_id 为 32 位十六进制；若 access 的 JWT 携带绑定设备标识则优先使用绑定值。

### 可选参数

### `ZHIPU_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：按需要选择任务；默认每日领分并查询余额，只查询时设 balance。
- 填写格式：checkin,balance（默认）；checkin；balance。checkin 始终包含领取前身份核验和领取后余额核对。

### `ZHIPU_ALLOW_REFRESH`

- 必填：否
- 敏感：否
- 获取或设置：仅在理解令牌轮换影响且已提供同账号 refresh 时开启。续期令牌只保存在本轮内存，后续运行需从本人登录态重新获取，不打印或导出新令牌。
- 填写格式：1 开启；0 默认关闭；也支持 true/yes/on 与 false/no/off。

### `ZHIPU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：无网络配置预演设为 1；不调用业务接口、文案提供方或通知接口，不宣称真实领分成功。
- 填写格式：1 开启；0 默认关闭；也支持 true/yes/on 与 false/no/off。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：auto 模式下可替换默认通知列表，支持目录路径、文件名、文件名通配符和目录条目标识。
- 填写格式：逗号、分号或空白分隔，支持 *；空值禁用全部。本任务标识 293d29f23c4b62a2，文件名 candidate.js。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：自定义青龙通知模块所在目录；不设置时查找 /ql/data/scripts/sendNotify.js、/ql/scripts/sendNotify.js。
- 填写格式：包含 sendNotify.js 的本地目录路径。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个账号 JSON 对象，将同账号 access、device_id 和可选 refresh 合并；忽略空行，不使用 & 或 @ 分隔。每个账号独立执行，任一账号失败则整体非零退出。

## 验证与兼容性

SHA-256 `39eae8fc5e20fefb8bc9bd0309e1b76a2f49a2e897e041ba34b2e6e36ddf1c2b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/293d29f23c4b62a2`。

## 副作用与风险

- 正式领分时增加账号每日积分（今日已领取则不重复增加）
- 显式开启续期时可能轮换账号访问令牌和刷新令牌
- 通知开启时向青龙配置的通知渠道发送脱敏任务摘要

## 许可证与来源

上游 `apmengzi/zhipu-switch` / `edge-ext/content.js` / `0509211ce6af7196367099f9386d919d11a16b3a`。
