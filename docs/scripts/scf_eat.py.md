# eatASMR每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/scf_eat.py`
- 青龙命令：`python3 scripts/scf_eat.py`
- 建议 Cron：`37 8 * * *`
- 发布哈希：`8a39580364d90df3f9e194846d2beee37dffa377babc0154c77901f239334514`
- 许可证：`GPL-3.0`

## 脚本功能

- eatASMR 每日任务签到
- 已签到状态识别
- 公开昵称展示以便核对账号
- 多账号独立处理与脱敏汇总通知
- 断网预演配置验证

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `EATASMR_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：登录 https://eatasmr.com 后打开浏览器开发者工具 → Network，刷新签到页 https://eatasmr.com/tasks/attendance，选择同站请求，复制 Request Headers 中完整的 cookie 值（不含 Cookie: 前缀）。请勿分享或写入公开仓库。
- 填写格式：每个非空行一个账号 Cookie；可用 备注|Cookie，仅按第一个 | 分割；Cookie 内的 &、@、; 保持原样

### 可选参数

### `EAT_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名；仅当 EATASMR_COOKIE 为空时读取
- 填写格式：与 EATASMR_COOKIE 相同

### `EATASMR_COOKIES`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名；仅当 EATASMR_COOKIE 与 EAT_COOKIE 均为空时读取
- 填写格式：与 EATASMR_COOKIE 相同

### `EATASMR_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要完全断网预演时手动设置为 1
- 填写格式：1/true/yes/on 启用

### `EATASMR_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：自定义单次 HTTPS 请求超时
- 填写格式：5..60 数字秒，默认 15

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要按脚本白名单启用通知时设置；空值表示全部禁用
- 填写格式：catalog-id、脚本路径、文件名或 glob，可用逗号/分号/空白/换行分隔；* 表示全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当青龙通知脚本不在默认路径时，设为 notify.py 或 sendNotify.js 所在目录
- 填写格式：本地目录绝对路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

EATASMR_COOKIE 中每个非空行是一个独立账号；可选 备注|Cookie；逐账号执行，任一账号失败时进程整体非零退出

## 验证与兼容性

SHA-256 `8a39580364d90df3f9e194846d2beee37dffa377babc0154c77901f239334514`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e2ef382ec73c4e6d`。

## 副作用与风险

- 成功请求会在 eatasmr.com 记录当日签到
- 启用青龙通知时会向已配置的通知渠道发送脱敏任务汇总

## 许可证与来源

上游 `trojblue/TSDM-coin-farmer` / `dist/SCF_eat.py` / `f2d93d01564a09ee996ee6a673c572f8743c6cd6`。
