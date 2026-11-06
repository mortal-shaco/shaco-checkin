# Follow 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/follow.js`
- 青龙命令：`node scripts/follow.js`
- 建议 Cron：`17 10 * * *`
- 发布哈希：`eac02d3992c7333caf0812155f389f897cfb4f5f2be151900a4a0e39d00cd4f5`
- 许可证：`GPL-3.0-only`

## 脚本功能

- 使用同一账号的 csrfToken 和 Cookie 提交每日签到领取请求
- 逐行多账号独立签到，兼容旧版单账号环境变量
- 固定 HTTPS 接口、15 秒总超时、响应大小限制、HTTP 与数字业务码双重成功校验
- 完全断网预演，不领取、不加载通知渠道，不冒充真实业务成功
- 展示官方返回的昵称、用户名、显示名称或公开 UID，过滤凭据及手机号
- 输出分阶段脱敏日志、逐账号统计、唯一单行 TASK_SUMMARY 汇总，并按选择清单发送青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `FOLLOW_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录 Follow 网页后，在浏览器开发者工具的网络面板手动签到，找到 api.follow.is/wallets/transactions/claim_daily 请求，复制 JSON 正文中的 csrfToken 和请求头 Cookie；两者须属于同一账号，仅存入青龙私有环境变量。
- 填写格式：每个非空行填写 csrfToken|Cookie；只在第一个竖线处分隔，后续 Cookie 内容原样保留；不得包含控制字符。

### 可选参数

### `follow_csrfToken`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧版单账号配置：从同一签到请求的 JSON 正文提取 csrfToken；未设置 FOLLOW_ACCOUNTS 时与 follow_cookie 配套使用。
- 填写格式：单账号 csrfToken，不能换行。

### `follow_cookie`

- 必填：否
- 敏感：是
- 获取或设置：兼容旧版单账号配置：复制同一签到请求的 Cookie 请求头；未设置 FOLLOW_ACCOUNTS 时与 follow_csrfToken 配套使用。
- 填写格式：完整单行 Cookie，不包含请求头名称。

### `FOLLOW_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设为 1；实际签到时设为 0 或不设置。
- 填写格式：1、true、yes、on 启用完全离线预演，不发业务或通知网络请求。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：使用 auto 时，将本任务目录编号、follow/follow.js、follow.js 或实际文件名加入清单；星号选择全部；未设置或空值不选择任务。
- 填写格式：逗号、分号或空白分隔；支持文件名星号通配；设置后替换默认空清单。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙已有 sendNotify.js 所在目录；否则查找 /ql/data/scripts 与 /ql/scripts。
- 填写格式：本地通知模块目录；业务请求不依赖此模块，通知失败保持业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

FOLLOW_ACCOUNTS 每个非空行一个账号，按第一个竖线拆分 csrfToken 与 Cookie；空行忽略，不使用 & 或 @ 拆分账号。组合变量优先，显式空值不回退；旧版两个变量仅兼容单账号。每个账号独立执行，任一失败均非零退出。

## 验证与兼容性

SHA-256 `eac02d3992c7333caf0812155f389f897cfb4f5f2be151900a4a0e39d00cd4f5`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/76f759b6f1d6f730`。

## 副作用与风险

- 实际运行时向 Follow 提交每日签到领取请求，可能增加账号的钱包领取记录及奖励
- 启用通知时通过青龙通知模块发送脱敏任务汇总

## 许可证与来源

上游 `chavyleung/scripts` / `follow/follow.js` / `bfab3c906f3d5d126e9094f15730e025f7f32128`。
