# 文体未来荟签到与积分查询

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/comeonbabyy1_qiandao_jiaob_wentiweilaihui.py`
- 青龙命令：`python3 scripts/comeonbabyy1_qiandao_jiaob_wentiweilaihui.py`
- 建议 Cron：`47 9 * * *`
- 发布哈希：`d4b95831e5878aac09e2e4ac28a2f23050a60155c84f85db2007395867e4c3ad`
- 许可证：`MIT`

## 脚本功能

- 每日文体未来荟签到，保留上游请求体、请求头和项目标识
- 查询万象星总积分、可用积分和冻结积分
- 逐行多账号独立执行，支持原账号字段的逐行 JSON 与账号专属用户代理
- 官方返回公开昵称、用户名、显示名或公开 UID 时直接展示，抑制手机号及凭据
- 两阶段严格业务核验、请求超时、禁止携带凭据重定向、不自动重试签到
- 完全断网预演及参数校验
- 按账号和阶段输出带时间戳的日志、耗时与统计，追加唯一 TASK_SUMMARY JSON 汇总
- 遵循青龙全局通知开关及脚本名单，通知不可用时保留业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WTWLH_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在微信文体未来荟小程序登录本人账号，通过本人授权的网络调试记录获取 wtmp.crland.com.cn 请求中的 token 请求头，以及 /promotion/app/sign/signin 请求体 data.mobile；不要复制整段请求或 Cookie。原 config/token.json 中 accounts 的 token、mobile 可逐行迁移；过期后重新登录获取。
- 填写格式：每个非空行一个账号：手机号|token，仅按第一个竖线分隔，后续 token 原样保留；不使用 & 或 @ 分账号。也支持每行一个 JSON 对象，必填 mobile、token，可选 account_name、user_agent。手机号为中国大陆十一位手机号。

### 可选参数

### `WTWLH_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：可从同一小程序授权请求的 User-Agent 请求头获取；不设置时沿用上游默认值。JSON 账号内 user_agent 优先。
- 填写格式：单行有效 HTTP 请求头字符串

### `WTWLH_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：设为 1 开启断网预演；正式执行设为 0 或不设置。
- 填写格式：1、true、yes、on 开启；预演仅校验配置，不请求业务接口，不调用通知模块，也不验证业务成功

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在自动模式列出需要通知的脚本；显式空值禁用全部。
- 填写格式：逗号、分号、空白或换行分隔；支持目录中的精确编号、来源相对路径、实际文件名及文件名通配符；* 选择全部

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写已有青龙通知模块所在目录，不负责下载或安装。默认尝试 import notify.send、/ql/data/scripts 和 /ql/scripts 下的 notify.py 或 sendNotify.js。
- 填写格式：本地目录路径；仅使用已有模块，模块缺失或通知失败保留业务退出码

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，配套手机号与 token 合并存放，仅按第一个竖线分隔；也支持逐行 JSON 兼容原账号字段。各账号独立执行，任一账号配置或业务失败则整体非零退出。

## 验证与兼容性

SHA-256 `d4b95831e5878aac09e2e4ac28a2f23050a60155c84f85db2007395867e4c3ad`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/34d1495efaa008cc`。

## 副作用与风险

- 向文体未来荟提交每日签到，可能发放服务端规则决定的积分
- 按通知开关和脚本名单调用已有青龙通知模块发送脱敏汇总；断网预演不发送

## 许可证与来源

上游 `comeonbabyy1/qiandao-jiaob` / `script/huaruntong/wentiweilaihui/main.py` / `ce494881ab17ef23b5b9de9df30ea60567b3865c`。
