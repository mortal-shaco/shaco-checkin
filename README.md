# shaco-checkin

通用签到类青龙脚本发布仓库。这里只包含通过来源、许可证、静态检查、真实沙箱验证和人工副作用验收的版本。

## 青龙面板安装

进入青龙面板 → 订阅管理 → 新建订阅，按下方“订阅配置”填写，开启“自动添加任务”和“自动删除任务”，再手工运行一次订阅。青龙会根据每个脚本顶部的 `name:` / `cron:` 元数据自动创建业务任务和“本仓库依赖安装”任务；首次订阅后先运行一次依赖安装任务。也可以在脚本管理中按原路径上传单个脚本，再按“定时任务”表创建任务。

## 订阅配置

```text
名称：mortal-shaco 通用签到
类型：公开仓库
地址：https://github.com/mortal-shaco/shaco-checkin.git
分支：main
定时类型：crontab
定时规则：17 4 * * *
白名单：^scripts/.*\.(js|py|sh)$
黑名单：(^|/)(tests?|docs?|validation|shared|__pycache__)(/|$)|(^|/)(README|CHANGELOG|LICENSE)(\.|$)|(^|/)[._]
```

## 建议订阅周期

建议每天北京时间 04:17 同步：`17 4 * * *`。订阅更新与业务任务执行是两套 Cron；业务时间见下方任务表。

## 黑白名单设置

采用固定的目录级规则，不再逐个枚举脚本：白名单只同步 `scripts/` 下的 `js`、`py`、`sh` 文件，因此以后新增业务脚本无需修改订阅。黑名单进一步排除文档、测试、脱敏验证材料、`shared/` 公共组件、缓存、隐藏文件和下划线开头的辅助文件。非任务组件必须放入 `shared/`，不得放在 `scripts/`；`scripts/` 中的任务必须带青龙可识别的 `name:` / `cron:` 元数据。若面板显示“文件后缀”，填写 `js py sh`。

## 定时任务

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron |
| --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `31 8 * * *` |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `55 9 * * *` |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 脚本功能

- `scripts/aliyunpan_checkin.py`：执行阿里云盘每日会员签到并明确验证接口结果；按换行多账号独立处理并汇总退出状态；提供完全断网且结果确定的预演模拟；检测刷新令牌轮换并可选安全写入本地文件。
- `scripts/baiduwangpan_checkin.py`：每日百度网盘会员签到，明确验证积分或已完成状态；获取并提交每日会员成长问题答案；读取并报告脱敏用户名、会员等级、成长值和会员类型；逐行多账号独立处理与结构化 JSON 汇总；完全断网的配置预演；成功、部分失败、失败、配置错误和预演状态的青龙脱敏汇总通知。
- `scripts/cfmoto_checkin.py`：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。
- `scripts/kuaishou_reward_status.py`：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。
- `scripts/smzdm_checkin.js`：校验账号的 sk 与 sess 配套凭据；执行什么值得买每日签到并识别今日已签到状态；查询签到奖励与连续签到状态；满足条件时领取连续签到额外奖励；查询并显示接口可取得的账号身份、等级、金币和碎银概览；统计当月经验变动；支持逐行多账号独立处理与失败汇总；提供完全断网的离线预演；输出时间轴日志、兼容结果记录和单行 TASK_SUMMARY JSON；按青龙通知策略发送脱敏汇总。
- `scripts/tieba_checkin.py`：验证百度贴吧登录状态并获取签到所需的 TBS；显示登录接口可取得的账号昵称、用户名或公开 UID，方便核对账号；读取账号关注的贴吧列表并识别当日已签到项目；为尚未签到的关注贴吧执行每日签到；支持每行一个账号的多账号独立处理和统一脱敏通知；提供完全断网、不会产生账号副作用的配置预演；输出逐阶段时间轴、账号统计和单行结构化任务汇总。
- `scripts/tsthb_checkin.py`：从官方活动列表查询当前签到活动，优先每日签到入口；校验账号并展示官方返回的非敏感身份，隐藏手机号；每日签到并展示奖励名称或积分；每行一个账号，账号独立执行与失败汇总；可配置的随机延迟及倒计时，保留每天 09:55 调度；完整断网预演、分阶段日志、任务统计及单行结构化汇总；青龙脱敏通知及全局开关，通知失败保留业务退出码；每次 HTTP 请求设置 20 秒整体等待时限，覆盖域名解析和慢速响应；签到不自动重试。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

### 必选参数（优先配置）

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="1"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_REFRESH_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个刷新令牌，空行会被忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDU_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_COOKIE</code></td><td>是</td><td>格式：ticket=&lt;value&gt; 或裸 ticket；多账号每行一个；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_COOKIE</code></td><td>是</td><td>格式：每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 &amp; 或 @ 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_ACCOUNT</code></td><td>是</td><td>格式：每个账号一行，格式为 sk|完整Cookie；只在第一个竖线处分隔，因此 Cookie 后续内容会完整保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tieba_checkin.py</code></td><td><code>TIEBA_COOKIE</code></td><td>是</td><td>格式：每个账号占一个非空行；单行填写 BDUSS 值，或填写形如 BDUSS=&lt;值&gt;; STOKEN=&lt;值&gt; 的完整 Cookie。同一账号的 Cookie 字段保留在同一行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tsthb_checkin.py</code></td><td><code>tsthbck</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 &amp; 或 @ 分隔账号，字段内部字符保持原样。；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

### 可选参数

不需要自定义行为时可以不配置；有默认值的参数会自动使用默认值。

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="6"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_DRIVE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes 或 on 表示启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_MAX_DELAY_SECONDS</code></td><td>否</td><td>格式：非负整数秒数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_PERSIST_ROTATED_TOKENS</code></td><td>否</td><td>格式：1、true、yes 或 on 表示启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_TOKEN_OUTPUT_FILE</code></td><td>否</td><td>格式：本地绝对文件路径；文件以 0600 权限原子替换，每行一个令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDUWANGPAN_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BAIDUWANGPAN_DELAY_MAX</code></td><td>否</td><td>格式：非负整数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：1/0 或常见布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_ACTIVITY_COUNT</code></td><td>否</td><td>默认 3；范围 0-3；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_ACTION_DELAY</code></td><td>否</td><td>默认 2；范围 0-30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_POST_CONTENTS</code></td><td>否</td><td>格式：多条内容用换行或 | 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_RANDOM_DELAY_MAX</code></td><td>否</td><td>默认 0；范围 0-3600；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_USER_AGENT</code></td><td>否</td><td>多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_DRY_RUN</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_USER_AGENT_APP</code></td><td>否</td><td>格式：完整的手机客户端 User-Agent 字符串。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes 或 on 表示启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：设置为 0、false、no 或 off 可关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 sendNotify.js 的绝对目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/tieba_checkin.py</code></td><td><code>TIE_BA_COOKIE</code></td><td>是</td><td>格式：每个账号占一个非空行；单行填写 BDUSS 值或包含 BDUSS 的完整 Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DRY_RUN</code></td><td>否</td><td>格式：启用值为 1、true、yes 或 on，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_VERBOSE</code></td><td>否</td><td>格式：启用值为 1、true、yes 或 on，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DELAY_MS</code></td><td>否</td><td>格式：整数毫秒，脚本会限制在 500 至 10000 之间，默认 1200。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no 或 off 表示关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，目录内应包含 notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/tsthb_checkin.py</code></td><td><code>TSTHB_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示启用。预演不执行等待、HTTP 或通知模块，仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：忽略大小写，只有 true 启用随机延迟，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数，单位秒；随机延迟开启时在 0 至该值之间随机选择并显示倒计时。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；不会下载安装通知组件。；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

- `scripts/aliyunpan_checkin.py`：ALIYUN_REFRESH_TOKEN 每个非空行填写一个账号；忽略空行并独立处理各账号。。
- `scripts/baiduwangpan_checkin.py`：BAIDU_COOKIE 中每个非空行是一个独立账号；依次处理，任一账号失败时进程整体非零退出。。
- `scripts/cfmoto_checkin.py`：CFMOTO_COOKIE 每行一个账号。
- `scripts/kuaishou_reward_status.py`：KUAISHOU_COOKIE 每个非空行对应一个账号；任一账号失败时任务整体非零退出。
- `scripts/smzdm_checkin.js`：SMZDM_ACCOUNT 每个非空行表示一个账号；各账号独立处理，任一账号失败时进程以非零状态退出。。
- `scripts/tieba_checkin.py`：每个非空行表示一个账号；同一账号的全部 Cookie 字段必须写在同一行，脚本不会使用 &、@ 等字符拆分账号。账号逐个独立处理，任一账号失败都会使进程以非零状态退出。。
- `scripts/tsthb_checkin.py`：每个非空行一个账号，按顺序独立执行；任一账号失败则整体非零退出。。

## 参数获取方法

### 必选参数获取（重点）

#### `ALIYUN_REFRESH_TOKEN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：登录阿里云盘网页版，从本人已认证会话的浏览器存储中复制 refresh_token；切勿分享。
- 填写格式：`每个非空行填写一个刷新令牌，空行会被忽略。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDU_COOKIE`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：登录 https://pan.baidu.com/ 后打开浏览器开发者工具的 Network 面板，刷新页面，选择一个 pan.baidu.com 请求，复制 Request Headers 中完整的 Cookie 值。
- 填写格式：`每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CFMOTO_COOKIE`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：使用本人测试账号在 CFMOTO App 执行一次相关请求，从本人控制的本地网络调试记录中复制 Cookie 请求头里的 ticket；如 App 阻止调试，不要绕过安全机制。
- 填写格式：`ticket=<value> 或裸 ticket；多账号每行一个`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUAISHOU_COOKIE`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：在本人已登录的快手或快手极速版中打开“积分换好礼”页面，从本人控制的本地网络调试记录里找到 accelerate/info 请求，复制 Cookie 请求头；至少保留 kuaishou.api_st。不要绕过证书固定或使用第三方提取网站。
- 填写格式：`每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 & 或 @ 分隔`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_ACCOUNT`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：登录什么值得买手机客户端后，通过本人设备上的 HTTPS 调试工具查看签到请求，取得表单字段 sk，并从同一请求的 Cookie 中取得包含 sess 的完整 Cookie；按 sk|Cookie 组合为一行。请勿向他人发送这些值。
- 填写格式：`每个账号一行，格式为 sk|完整Cookie；只在第一个竖线处分隔，因此 Cookie 后续内容会完整保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：在浏览器登录百度贴吧后，从 tieba.baidu.com 的请求 Cookie 中复制 BDUSS；可只填写 BDUSS 的值，也可填写包含 BDUSS 的完整 Cookie。请仅在自己的青龙环境中保存。
- 填写格式：`每个账号占一个非空行；单行填写 BDUSS 值，或填写形如 BDUSS=<值>; STOKEN=<值> 的完整 Cookie。同一账号的 Cookie 字段保留在同一行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `tsthbck`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：在微信塔斯汀小程序登录，用本人授权的抓包工具查看 sss-web.tastientech.com 请求头中的 user-token；仅复制该字段值，过期后重新获取。
- 填写格式：`每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 & 或 @ 分隔账号，字段内部字符保持原样。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。


### 可选参数说明

#### `ALIYUN_DRIVE_DRY_RUN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；设为 1 可在不联网、不等待、不签到且不保存凭据的情况下模拟所有账号。
- 填写格式：`1、true、yes 或 on 表示启用。`

#### `ALIYUN_MAX_DELAY_SECONDS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；设置正式执行前的最大随机等待时间，默认 0。
- 填写格式：`非负整数秒数。`

#### `ALIYUN_PERSIST_ROTATED_TOKENS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；仅在需要把轮换后的刷新令牌写入文件时明确设为 1，默认关闭。
- 填写格式：`1、true、yes 或 on 表示启用。`

#### `ALIYUN_TOKEN_OUTPUT_FILE`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：启用令牌持久化时，填写位于现有目录内的令牌文件绝对路径。
- 填写格式：`本地绝对文件路径；文件以 0600 权限原子替换，每行一个令牌。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `BAIDUWANGPAN_DRY_RUN`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：设为 1 可仅验证配置，不访问网络且不改变账号状态。
- 填写格式：`1/true/yes/on 启用`

#### `BAIDUWANGPAN_DELAY_MAX`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：可选的账号间最大随机等待秒数，默认 0（不等待）。
- 填写格式：`非负整数`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：青龙全局通知开关，默认启用；设为 0、false、no 或 off 可禁用。
- 填写格式：`1/0 或常见布尔值`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：如青龙 notify.py 不在标准位置，可设为其所在目录。
- 填写格式：`包含 notify.py 的目录路径`

#### `CFMOTO_ACTIVITY_COUNT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置互动任务轮数，设为 0 可只签到。
- 默认值：`3`

#### `CFMOTO_ACTION_DELAY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置每个积分动作之间的等待秒数。
- 默认值：`2`

#### `CFMOTO_POST_CONTENTS`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅在随机文案接口不可用时，作为自定义本地兜底文案。
- 填写格式：`多条内容用换行或 | 分隔`

#### `CFMOTO_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置任务启动前的最大随机等待秒数。
- 默认值：`0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；默认通过青龙通知组件推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `CFMOTO_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；设为 0 可关闭 notify.py 通知。
- 默认值：`1`

#### `CFMOTO_USER_AGENT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：通常无需设置；仅默认 User-Agent 失效时，从同一 CFMOTO App 请求头复制。

#### `CFMOTO_DRY_RUN`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅预演时手工设为 1。
- 默认值：`0`

#### `KUAISHOU_DRY_RUN`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；预演时手工设置为 1，正式查询时删除或设为 0。
- 填写格式：`1/true/yes/on 开启断网预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `SMZDM_USER_AGENT_APP`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：可从本人设备的什么值得买客户端请求头中取得；通常无需配置。
- 填写格式：`完整的手机客户端 User-Agent 字符串。`

#### `SMZDM_DRY_RUN`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：设置为 1 可启用完全离线预演。
- 填写格式：`1、true、yes 或 on 表示启用。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：青龙全局通知开关；默认启用。
- 填写格式：`设置为 0、false、no 或 off 可关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：仅当 sendNotify.js 不在青龙标准目录时，填写其所在目录。
- 填写格式：`包含 sendNotify.js 的绝对目录路径。`

#### `TIE_BA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：旧版兼容变量，获取方法与 TIEBA_COOKIE 相同；仅当未设置 TIEBA_COOKIE 时读取。
- 填写格式：`每个账号占一个非空行；单行填写 BDUSS 值或包含 BDUSS 的完整 Cookie。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_DRY_RUN`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；设为 1 可进行完全断网的配置预演。
- 填写格式：`启用值为 1、true、yes 或 on，不区分大小写。`

#### `TIEBA_VERBOSE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；按需设为 1，可在正式执行时显示贴吧名称和脱敏错误详情。
- 填写格式：`启用值为 1、true、yes 或 on，不区分大小写。`

#### `TIEBA_DELAY_MS`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；用于调整连续签到请求之间的固定间隔。
- 填写格式：`整数毫秒，脚本会限制在 500 至 10000 之间，默认 1200。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；青龙通知默认开启，设为 0 可关闭。
- 填写格式：`0、false、no 或 off 表示关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：仅在青龙通知脚本不位于标准目录时填写 notify.py 所在目录。
- 填写格式：`本机目录路径，目录内应包含 notify.py。`

#### `TSTHB_DRY_RUN`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置为 1 启用完全断网预演；默认 0。
- 填写格式：`1、true、yes、on 表示启用。预演不执行等待、HTTP 或通知模块，仅展示通知摘要。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置；保留维护版默认 true。限时验证和需要立即执行时设置 false。
- 填写格式：`忽略大小写，只有 true 启用随机延迟，其他值关闭。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置随机等待上限；保留维护版默认 3600 秒。
- 填写格式：`非负整数，单位秒；随机延迟开启时在 0 至该值之间随机选择并显示倒计时。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置青龙通知开关；默认 1。通知不可用不影响业务退出码。
- 填写格式：`0、false、no、off 关闭，忽略大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：可选，填写已有青龙 notify.py 所在目录；未配置时尝试导入 notify，并查找 /ql/data/scripts 和 /ql/scripts。签到本身不依赖通知文件。
- 填写格式：`可选目录路径；不会下载安装通知组件。`


## 验证与兼容性

- `scripts/aliyunpan_checkin.py`：SHA-256 `4b1884c921accb1fe4555d1eca158f6ab1acbea919d95c32e0fa1d92df7a3c00`；live 业务成功证据位于 `projects/checkin/validation/9c6fa7a75879fa8b`。
- `scripts/baiduwangpan_checkin.py`：SHA-256 `e9c658f4544427bd94ab4da74a724038d1f849c8b9665464ded6e8a1c4dd2c18`；live 业务成功证据位于 `projects/checkin/validation/d9230b69d9462c7c`。
- `scripts/cfmoto_checkin.py`：SHA-256 `15ecc5e482af800b18360374359667392176fe88ab77c7950509da115f09f07a`；live 业务成功证据位于 `projects/checkin/validation/0ba7bb41fd4c339c`。
- `scripts/kuaishou_reward_status.py`：SHA-256 `b727e90b3326ec58b00281be13ad27879cb75be0af9a9c5c0a93fe3fbd8aa305`；live 业务成功证据位于 `projects/checkin/validation/ks_cleanroom_v1`。
- `scripts/smzdm_checkin.js`：SHA-256 `f63ce76cdd5c9e61e5316ec4282a9d9bde130dac10bded05bb3b175ac2a1879f`；live 业务成功证据位于 `projects/checkin/validation/621df252c315f2d1`。
- `scripts/tieba_checkin.py`：SHA-256 `c19c152b7240df266352493f048f0580710c5c2d1f7c2a62a52922025064d912`；live 业务成功证据位于 `projects/checkin/validation/e608052390d250da`。
- `scripts/tsthb_checkin.py`：SHA-256 `f1f423f22e8134fb3080600f07293746eeb4d05783ec1778f489174dc1166d4c`；live 业务成功证据位于 `projects/checkin/validation/82616d06df4e5f53`。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。

## 副作用与风险

- `scripts/aliyunpan_checkin.py`：正式执行时为每个账号完成阿里云盘会员签到；正式执行时刷新账号访问令牌，并可能轮换刷新令牌；明确启用持久化时，将当前刷新令牌原子写入配置的本地文件。
- `scripts/baiduwangpan_checkin.py`：为每个已配置的百度网盘账号执行每日会员签到；为每个已配置的百度网盘账号提交每日会员问题答案；在通知开启且青龙通知模块可用时发送一条脱敏任务汇总通知。
- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容；最多产生三次公开评论、三次点赞和三次分享任务记录；发帖和评论前访问第三方一言接口获取公开随机文本，不发送春风动力账号凭据。
- `scripts/kuaishou_reward_status.py`：。
- `scripts/smzdm_checkin.js`：在什么值得买账号上执行每日签到并改变当日签到状态；满足条件时领取连续签到额外奖励并改变账号奖励状态。
- `scripts/tieba_checkin.py`：正式执行时向百度贴吧提交签到请求，改变对应贴吧的当日签到状态；通知开启且青龙通知组件可用时发送脱敏任务汇总。
- `scripts/tsthb_checkin.py`：向官方签到接口提交每日签到，可能获得积分或奖励；正式运行且通知开启时，通过已有青龙通知模块发送脱敏结果。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/aliyunpan_checkin.py`：上游 `agluo/ql-script-hub` / `aliyunpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/baiduwangpan_checkin.py`：上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。
- `scripts/smzdm_checkin.js`：上游 `ump45nose/smzdm-checkin-ql` / `checkin.js` / `6b9eaced964c348efb46d2c13a45ab5c66caaea8`。
- `scripts/tieba_checkin.py`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_tieba.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/tsthb_checkin.py`：上游 `agluo/ql-script-hub` / `tsthb_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
