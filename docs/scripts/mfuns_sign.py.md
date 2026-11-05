# 喵御宅每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/mfuns_sign.py`
- 青龙命令：`python3 scripts/mfuns_sign.py`
- 建议 Cron：`9 9 * * *`
- 发布哈希：`1d60b752e4bac2b15fa4cd55a6d75feeced1509a6c5f01b0f3bff252d97d17d9`
- 许可证：`MIT`

## 脚本功能

- 每日签到：调用喵御宅签到接口，code=1 视为成功，code=0 视为今日已签到
- 签到前通过浏览历史接口校验 Authorization 是否有效
- 失败时最多额外重试 1 次，保留上游重试行为
- 官方响应返回昵称、用户名、显示名称或公开 UID 时原样展示以便核对账号
- 支持按行多账号，独立统计并在任一失败时整体非零退出
- 完全断网预演、时间轴分阶段日志、账号与任务统计，以及单行 TASK_SUMMARY
- 按青龙通知名单与全局开关调用 notify.py 或 sendNotify.js；预演仅生成脱敏摘要

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `NEKO_MFUNS_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：登录 https://www.mfuns.net 后，打开浏览器开发者工具 → Network，刷新页面或发起任意已登录请求，在 Request Headers 中复制 Authorization 字段的完整值（不是 Cookie 请求头整段）。不要公开或上传该值。
- 填写格式：每个非空行一个账号的 Authorization 原值；只按换行分隔账号，不使用 & 或 @；保留令牌内部分隔字符。

### 可选参数

### `NEKO_MFUNS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：自行设置；用于完全断网预演参数检查、凭证校验与签到流程。
- 填写格式：1、true、yes 或 on 开启；默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自行设置需要通知的脚本名单。
- 填写格式：逗号、分号、空白或换行分隔；支持目录编号 bacc70efebb57480、文件名 mfuns_sign.py / candidate.py、scripts 相对路径及文件名通配符；* 全选，显式空值全关；未设置且 QINGLONG_NOTIFY=auto 时默认不推送。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选；指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：本机目录路径；优先尝试可导入的 notify.send，再检查此目录及 /ql/data/scripts、/ql/scripts；随后尝试 sendNotify.js。通知失败不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

NEKO_MFUNS_COOKIE 每个非空行表示一个账号的 Authorization 值；账号逐个独立处理，任一账号失败或配置错误时整体非零退出。

## 验证与兼容性

SHA-256 `1d60b752e4bac2b15fa4cd55a6d75feeced1509a6c5f01b0f3bff252d97d17d9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bacc70efebb57480`。

## 副作用与风险

- 正式模式调用喵御宅每日签到接口，可能写入签到状态并发放签到奖励
- 正式模式在通知策略选中且工具可用时发送脱敏任务结果通知

## 许可证与来源

上游 `Kou-JunHao/Neko_mfuns_login` / `mfuns_sign.py` / `69d939349956d6b1da6b28b25a5e54a4bd39330d`。
