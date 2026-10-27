# KukuAI 每日积分

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/kuku_daily.py`
- 青龙命令：`python3 scripts/kuku_daily.py`
- 建议 Cron：`0 8 * * *`
- 发布哈希：`f4ab9950449cdbd18ba8379ee8c0308fbbe5a7033fc8968186e70eb023696568`
- 许可证：`MIT`

## 脚本功能

- 查询每日积分面板，并显示官方返回的非敏感昵称、用户名、显示名称或公开 UID；隐藏手机号和凭据。
- 依次领取每日登录 LOGIN 与对话任务 CHAT 奖励；各任务失败独立记录，重复领取仅在明确 SUCCESS 且奖励为零时记为已完成。
- 支持每行一个账号、旧凭据变量、Cookie 请求头和多种 JSON 格式，以及 --only 序号选择账号。
- 优先使用手动配置的产品 STOKEN，缺少时使用同账号 BDUSS、PTOKEN，通过官方接口纯算法换发；只在本次运行内存中使用。
- 支持 HTTP/HTTPS 代理；业务请求具有超时、大小限制、重定向阻断、HTTP 状态和业务状态检查。
- 提供完全断网预演、带时间戳的编号阶段日志、逐账号统计及兼容的单行 TASK_SUMMARY 结构化汇总。
- 成功、部分失败、失败、参数错误及预演均生成脱敏通知摘要，遵守全局开关与通知名单，经青龙 Python 或 JavaScript 通知模块发送；预演仅展示摘要。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `KUKU_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录官方库库 AI，在官方业务请求中复制同账号的 BDUSS Cookie 和 genflowpro 产品作用域 STOKEN。也可从已登录百度的浏览器开发者工具「应用/存储→Cookie」或官方请求 Cookie 中取得同账号 BDUSS、PTOKEN，用于脚本通过官方 HTTPS 接口换发。网页通行证 STOKEN 不等于产品 STOKEN；失效时需重新获取。勿使用第三方凭据服务或在日志分享凭据。
- 填写格式：每个非空行一个账号：产品STOKEN|完整Cookie。只在第一个 | 处分割，后续 Cookie 内容保留；Cookie 支持请求头、单行编辑器 JSON、含 cookies/cookie 的对象、键值对象。无产品 STOKEN 时保留开头 |，Cookie 必须含同账号 BDUSS 和 PTOKEN；有 STOKEN 时 Cookie 至少含完整 BDUSS。不用 &、@ 分隔账号。

### 可选参数

### `KUKU_TOKENS`

- 必填：否
- 敏感：是
- 获取或设置：兼容原脚本的多账号输入，所需凭据从同一账号官方 Cookie 和业务请求取得，建议迁移到 KUKU_ACCOUNTS。
- 填写格式：仅当 KUKU_ACCOUNTS 为空时使用；每行 备注|BDUSS|PTOKEN[|STOKEN]，第四段可省略或留空以换发。备注不作为官方身份显示。禁止使用 & 或 @ 分隔账号。

### `KUKU_COOKIES`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号输入，在官方库库 AI 登录后从开发者工具复制完整 Cookie 或 Cookie 编辑器导出内容。BDUSS、PTOKEN 与 KUKU_STOKEN 必须属于同一账号。
- 填写格式：仅当 KUKU_ACCOUNTS、KUKU_TOKENS 均为空时使用；一个账号的 Cookie 请求头、编辑器 JSON 或键值对象。至少含 BDUSS；未配置 KUKU_STOKEN 时另需 PTOKEN。

### `KUKU_STOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容单账号输入，从官方 kuku.baidu.com 业务请求中取得 genflowpro 产品作用域 STOKEN。无该令牌可留空并在 KUKU_COOKIES 配置 BDUSS、PTOKEN 以自动换发。
- 填写格式：仅与 KUKU_COOKIES 配套使用的同账号产品 STOKEN 字符串，不包含 STOKEN= 前缀。配置后优先使用，失效不会自动覆盖。

### `KUKU_PROXY`

- 必填：否
- 敏感：是
- 获取或设置：可选，从自己的可信代理服务配置中取得；未设置时业务请求直连，不继承系统代理。
- 填写格式：有效的 http:// 或 https:// 代理地址；标准库模式不支持 SOCKS。代理用于官方换发和每日积分请求，不传给通知子进程。

### `KUKU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：本地或青龙测试时设置为 1，正式领取时删除或设置为 0。
- 填写格式：1 启用完全断网预演；0/false/no/off 或空值关闭。预演不验证凭据有效性，不换发、不领取、不导入通知模块。

### `KUKU_NO_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：兼容原脚本的通知关闭开关。
- 填写格式：1 强制关闭本脚本通知；其他值由全局通知策略决定。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：需要选择通知脚本时设置，当前目录 ID 为 224698e8fa0ac8f6，规范文件名为 kuku_daily.py。
- 填写格式：支持目录 ID、脚本相对路径、文件名和文件名通配符；逗号、分号或空白分隔，* 表示全部。设置后替换默认名单；显式空值关闭全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知文件不在标准位置时，填写自己可信的通知模块目录；无需下载或安装引导程序。
- 填写格式：包含 notify.py 或 sendNotify.js 的本地目录。依次尝试 import notify.send、指定目录及 /ql/data/scripts、/ql/scripts 中的 Python 通知模块，再尝试同目录 JavaScript 模块。JavaScript 通知仅在已有 Node.js 时可用，不影响业务独立运行。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，同账号凭据集中在 KUKU_ACCOUNTS，以第一个 | 分隔 STOKEN 和 Cookie；各账号、各奖励独立处理，任一账号失败则整体非零退出。支持 --only 序号，只核验所选账号。

## 验证与兼容性

SHA-256 `f4ab9950449cdbd18ba8379ee8c0308fbbe5a7033fc8968186e70eb023696568`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/224698e8fa0ac8f6`。

## 副作用与风险

- 正式运行领取每日登录 LOGIN 和对话任务 CHAT 奖励，可能增加账号积分；不会实际发送聊天或发布内容。
- 未提供产品 STOKEN 时向百度官方认证接口换发当前账号的 genflowpro 会话令牌；不保存本地令牌缓存。
- 通知被选中且非预演时，向青龙配置的通知渠道发送脱敏统计摘要。

## 许可证与来源

上游 `L0NE-6/KukuAI-Daily` / `kuku_daily.py` / `6912419c6b29365bb7b3172cc3c18bf7b763812d`。
