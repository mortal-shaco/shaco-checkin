# GLaDOS每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/glados.py`
- 青龙命令：`python3 scripts/glados.py`
- 建议 Cron：`58 0 * * *`
- 发布哈希：`b20e8538714d8bf3adde3900c3938ead36d25aee8cebc9071262c076bb344533`
- 许可证：`Apache-2.0`

## 脚本功能

- 每日签到与重复签到业务识别
- 官方账号身份原样展示与剩余天数查询
- 可选积分余额与连续签到天数查询，兼容历史余额与签到响应补充统计
- 显式选择 rocks 或 cloud 同产品接口，保留默认配置且不自动跨域
- 换行多账号与旧 Cookie、会话签名配对变量兼容
- 请求超时、可选重试、代理及浏览器标识配置
- 完整断网预演、分阶段脱敏日志、账号与任务统计及单行结构化汇总
- 青龙通知开关、任务选择、Python 到 JavaScript 通知发现链及可选飞书签名通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `GR_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：在对应 GLaDOS 网站登录，打开浏览器开发者工具的网络面板，查看自己的 /api/user/status 或 /api/user/checkin 请求，复制完整 Cookie 请求头；不要复制响应正文，不要分享给他人。
- 填写格式：每个非空行一个账号的完整 Cookie，保留分号、等号、& 和 @；同一账号的会话与签名在同一行，不使用其他字符分割账号。

### 可选参数

### `GLADOS_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：在对应 GLaDOS 网站登录，打开浏览器开发者工具的网络面板，查看自己的 /api/user/status 或 /api/user/checkin 请求，复制完整 Cookie 请求头；不要复制响应正文，不要分享给他人。这是兼容变量，优先使用 GR_COOKIE。
- 填写格式：与 GR_COOKIE 相同；仅 GR_COOKIE 没有非空行时读取。

### `GLADOS_GLD_SESS`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：从同一账号 Cookie 中取得 gld:sess，建议与签名合并到 GR_COOKIE。
- 填写格式：每行一个会话值，保留后续等号；与 GLADOS_GLD_SESS_SIG 非空行逐行配对。

### `GLADOS_GLD_SESS_SIG`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：从同一账号 Cookie 中取得 gld:sess.sig，必须与对应会话来自同次登录。
- 填写格式：每行一个签名；仅完整 Cookie 未配置时启用配对输入。

### `GLADOS_KOA_SESS`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：从同一账号 Cookie 中取得 koa:sess，建议与签名合并到 GR_COOKIE。
- 填写格式：每行一个会话值；与 GLADOS_KOA_SESS_SIG 非空行逐行配对；优先读取 gld 配对变量。

### `GLADOS_KOA_SESS_SIG`

- 必填：否
- 敏感：是
- 获取或设置：兼容输入：从同一账号 Cookie 中取得 koa:sess.sig，必须与对应会话来自同次登录。
- 填写格式：每行一个签名；不得用 & 或 @ 分割账号。

### `GLADOS_SITE`

- 必填：否
- 敏感：否
- 获取或设置：根据取得 Cookie 的网站显式选择；没有线上验证证明需要更换规范脚本默认域名，不自动跨域回退。
- 填写格式：rocks 或 cloud；默认 rocks 对应 https://glados.rocks 和请求体 token=glados.one；cloud 对应 https://glados.cloud 和 token=glados.cloud。

### `GLADOS_POINTS`

- 必填：否
- 敏感：否
- 获取或设置：需要额外查询积分和连续签到天数时开启；cloud 来源有同功能接口证据，rocks 接口尚未联网验证。
- 填写格式：1 开启、0 关闭；cloud 默认 1，rocks 默认 0；开启后查询失败将使该账号失败，不能以签到统计冒充查询成功。

### `GLADOS_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置，无需获取凭据。
- 填写格式：1 至 60 的有限数字，单位秒，默认 15。

### `GLADOS_RETRIES`

- 必填：否
- 敏感：否
- 获取或设置：按需启用参考来源的签到重试；默认不增加规范脚本的请求次数。
- 填写格式：0 至 5 的整数，默认 0；登录失效、设备不匹配、拒绝访问和重定向不重试。

### `GLADOS_USER_AGENT`

- 必填：否
- 敏感：否
- 获取或设置：可从同一次浏览器请求头复制 User-Agent；无需配置即可使用内置值。
- 填写格式：单行浏览器标识，不得包含控制字符。

### `CHECKIN_PROXY_URL`

- 必填：否
- 敏感：是
- 获取或设置：需要代理时从自己的代理服务取得地址，禁止写入脚本或日志。
- 填写格式：带端口的 http:// 或 https:// 代理地址，支持代理认证；不配置时沿用标准运行环境代理。

### `GLADOS_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：本地测试时设为 1，不调用业务接口、随机文本服务或通知器。
- 填写格式：1、true、yes、on 开启；默认关闭。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：按青龙希望接收通知的任务设置；未设置时本规范任务默认入选。
- 填写格式：逗号、分号或空白分隔的目录编号、脚本相对路径、文件名或文件名通配符；支持 2d633fe3129937b6、scripts/glados.py、glados.py；* 表示全部，空值表示全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙已有的 notify.py 或 sendNotify.js 目录；不需要安装其他应用，未配置时自动发现。
- 填写格式：可选通知目录；顺序为 import notify.send、此目录及 /ql/data/scripts、/ql/scripts 的 notify.py，再尝试这些目录的 sendNotify.js；每次发送限时 30 秒。

### `FEISHU_WEBHOOK`

- 必填：否
- 敏感：是
- 获取或设置：可选：在飞书或 Lark 群添加自定义机器人，从机器人配置复制 webhook；不配置则只使用青龙通知。
- 填写格式：官方 https://open.feishu.cn/open-apis/bot/v2/hook/ 或 https://open.larksuite.com/open-apis/bot/v2/hook/ 地址；遵守 QINGLONG_NOTIFY 和任务选择规则。

### `FEISHU_SECRET`

- 必填：否
- 敏感：是
- 获取或设置：可选：从同一个飞书自定义机器人的签名校验配置取得；机器人未开启签名时留空。
- 填写格式：单行签名密钥，仅用于飞书请求签名，绝不写入通知内容或日志。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，优先读取 GR_COOKIE，其次 GLADOS_COOKIE，最后兼容成对会话变量；同一账号 Cookie 中的会话、签名及其他值完整放在同一行；按首个等号识别字段，后续等号及 &、@ 均保留。每个账号独立处理，任一账号失败则整体非零退出。

## 验证与兼容性

SHA-256 `b20e8538714d8bf3adde3900c3938ead36d25aee8cebc9071262c076bb344533`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2d633fe3129937b6`。

## 副作用与风险

- 执行 GLaDOS 签到，可能按平台规则增加积分或账户可用天数
- 非预演模式下按通知配置向青龙通知渠道和已配置的飞书机器人发送脱敏摘要

## 许可证与来源

上游 `hennessey-v/GlaDOS_Checkin_ql` / `checkin.py` / `d858874736fc8d80f24ebcd17721fd1f924252db`。
