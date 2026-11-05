# Tabbit 国内版每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/tabbit_cn_daily.py`
- 青龙命令：`python3 scripts/tabbit_cn_daily.py`
- 建议 Cron：`18 9 * * *`
- 发布哈希：`d5991e68e17b3021873e53b1cfb4ed481fee3d16abe7c2153d07e742b5e52fd1`
- 许可证：`MIT`

## 脚本功能

- 国内站 web.tabbit.com 每日签到状态查询与领取，覆盖 daily_sign_in 场景，保留已签到与活动未开启的中性成功判定。
- 签到前查询额度用量百分比；额度失败时按上游契约回退 0.00% 继续领取。
- 支持 --query 仅查询状态与额度、--only N 单账号、--no-notify 关闭推送。
- 多账号换行配置，兼容 Cookie、备注|凭据、token|uid 与 JSON；展示公开 UID 便于核对。
- 完全断网预演、请求超时与响应大小限制、阶段时间轴日志与单行 TASK_SUMMARY。
- 青龙 notify.py / sendNotify.js 通知及 PushPlus、Bark、企业微信兼容渠道，遵守全局开关与脚本清单。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `TABBIT_CN_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：仅使用国内站 https://web.tabbit.com 本人账号。登录后打开浏览器开发者工具，从 Cookie 复制 token（JWT，约 7 天有效）与 user_id；国际站 web.tabbit.ai 凭据不可互换。不要把令牌粘贴到日志或通知。
- 填写格式：每个非空行一个账号。推荐整行 Cookie（须含 token=，建议含 user_id=），或 备注|Cookie/JWT整段（只在第一个 | 分割）。兼容 备注|token|uid、备注|token|uid|client_version，以及单行 JSON 对象 / JSON 数组。不以 &、@ 或 && 分隔账号。

### 可选参数

### `TABBIT_UNLOCK_PRO`

- 必填：否
- 敏感：否
- 获取或设置：仅当需要按上游方式生成“默认浏览器/Pro”类 unique-uuid 指纹时显式开启；默认关闭，避免不安全的默认伪装。
- 填写格式：1/true/yes/on 开启；0/false/no/off 或不设置表示关闭。也可在账号 JSON 中设置 unlock_pro。

### `TABBIT_CLIENT_VERSION`

- 必填：否
- 敏感：否
- 获取或设置：可选：与本人客户端版本对齐时填写；默认使用维护脚本内置版本号。
- 填写格式：例如 1.17.16(10117016)；也可在账号行或 JSON 中覆盖。

### `TABBIT_CN_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：用于首次配置检查与完全断网预演；不代表真实签到成功。
- 填写格式：1、true、yes 或 on 启用；不访问业务接口与通知服务。

### `TABBIT_CN_NO_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：需要关闭本脚本全部推送时设置；也可传入 --no-notify。
- 填写格式：1/true/yes/on 关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自行选择需要推送的脚本；设置后替代默认通知清单。
- 填写格式：逗号、分号或空白分隔目录编号、脚本相对路径、文件名或通配符；支持 138727873cd50b7e、tabbit_cn_daily.py；* 选择全部，空值禁用全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选：指定已安装青龙通知模块所在目录，否则依次发现可导入的 notify 与 /ql/data/scripts、/ql/scripts。
- 填写格式：包含 notify.py 或 sendNotify.js 的本地目录路径。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容渠道：登录 PushPlus 后在个人页面复制自己的推送令牌。
- 填写格式：仅填写令牌；受统一通知开关控制。

### `BARK_URL`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容渠道：从自己的 Bark 客户端复制推送地址。
- 填写格式：完整 HTTPS 推送基础地址；受统一通知开关控制。

### `WECOM_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容渠道：在自己管理的企业微信群机器人设置中复制 Webhook。
- 填写格式：完整 HTTPS Webhook，或仅机器人 key；受统一通知开关控制。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个国内版账号，账号之间只用换行分隔。同一账号的 token/Cookie 与 user_id 写在同一行或同一 JSON 对象；备注与凭据只在第一个 | 处分割。各账号独立执行，任一账号失败时进程非零退出；--only N 按配置顺序选择账号。

## 验证与兼容性

SHA-256 `d5991e68e17b3021873e53b1cfb4ed481fee3d16abe7c2153d07e742b5e52fd1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/138727873cd50b7e`。

## 副作用与风险

- 正式执行时对未签到账号发起每日签到领取，可能发放用量奖励。
- 启用通知时通过青龙及已配置兼容渠道发送脱敏任务汇总；无网络预演不发送、不访问业务接口。

## 许可证与来源

上游 `L0NE-6/Tabbit-Daily` / `tabbit_cn_daily.py` / `acbd1dff786ced03f470ae513d427b539d3477db`。
