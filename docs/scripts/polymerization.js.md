# 每日任务聚合

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/polymerization.js`
- 青龙命令：`node scripts/polymerization.js`
- 建议 Cron：`41 9 * * *`
- 发布哈希：`e0dea1d0cf3efb6059b80521197d274c875e4ffa81f3060ce696257de67fde23`
- 许可证：`MIT`

## 脚本功能

- 有道云笔记刷新会话、同步、签到、查询本次空间奖励；广告奖励通过 ad_count 显式开启
- 阿里云盘刷新访问凭据、每日签到、领取当日奖励并显示累计天数
- 百度网盘会员签到、每日答题、会员等级及成长值查询
- Bilibili 登录验证、直播和漫画签到、当天经验及钱包查询；保留关注用户视频到分区视频的选取回退链；投币、观看上报、分享、会员权益领取及银瓜子兑换均显式开启
- V2EX 每日登录奖励、当日账目、余额与连续签到天数查询
- AcFun 支持 Cookie 或手机号密码登录、签到、等级和香蕉查询；显式选择点赞并撤销、投香蕉、发布弹幕
- 恩山论坛签到及恩山币、积分、连续天数查询
- 飞牛社区打卡并解析我的打卡动态
- 百度贴吧分页获取关注列表、逐吧签名签到，保留分页与数量保护及分类统计
- 什么值得买签名签到及奖励查询；仅显式提供活动编号时执行活动抽奖
- 爱奇艺会员等级、今日成长、总成长、升级差值及到期查询；显式开启赠送抽奖次数、白金抽奖、等级权益、每日摇奖和聚合抽奖
- 全民 K 歌六入口核心签到奖励及鲜花增量查询；显式开启四路抽奖、音乐卡择优领奖和 VIP 每日奖励
- 百度搜索资源平台从公开 HTTPS 纯文本列表读取站点 URL 并限次提交官方 API
- 每行独立任务账号、完全断网预演、失败非零退出、超时与业务核验、脱敏分阶段日志、单条结构化总结、青龙通知
- 弹幕文案优先请求 HTTPS 一言，保留作者与来源署名；网络错误、HTTP 错误、超时、响应超限、无效 JSON、缺少正文或长度超限均回退本地文案；预演不请求文案服务

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `DAILY_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：在本人账号登录后，通过浏览器开发者工具的网络面板或本人设备的 HTTPS 抓包读取对应请求；不要将凭据发给他人。从原 daily 表迁移 A 列任务标识及 B 列凭据；每行只放一个任务账号。YOUDAO：note.youdao.com 登录请求 Cookie；ALIYUN：阿里云盘 auth.aliyundrive.com 刷新请求中的 refresh_token；BAIDUWP：pan.baidu.com 会员请求 Cookie；BILIBILI：www.bilibili.com 登录 Cookie，可选写操作需要 bili_jct；V2EX：www.v2ex.com 登录 Cookie；ACFUN：www.acfun.cn 登录 Cookie，或本人手机号 phone 与密码 password；ENSHAN：www.right.com.cn/forum 登录 Cookie；FNNASCLUB：club.fnnas.com 登录 Cookie；TIEBA：tieba.baidu.com 登录 Cookie，必须含 BDUSS；SMZDM：本人 App user-api.smzdm.com 请求 Cookie；IQIYI：本人爱奇艺登录 Cookie，必须含 P00001，聚合抽奖需 P00003；KGQQ：本人全民 K 歌 node.kg.qq.com 请求 Cookie，必须含 uid；BAIDU：百度搜索资源平台普通收录 API 页面取得含 site、token 的官方 HTTPS 提交地址，另自行提供公开 HTTPS 纯文本 URL 列表地址。
- 填写格式：每个非空行格式为 任务标识|凭据；只在第一个 | 分割，后续内容完整保留，不按 & 或 @ 分账号。任务标识为 YOUDAO、ALIYUN、BAIDUWP、BILIBILI、V2EX、ACFUN、ENSHAN、FNNASCLUB、TIEBA、SMZDM、IQIYI、KGQQ、BAIDU。除 ALIYUN 裸 refresh_token 外其余账号接受裸 Cookie；BAIDU 必须为 JSON 对象 {"data_url":"公开 HTTPS 列表地址","submit_url":"官方 HTTPS 提交地址"}。各任务兼容原 JSON 凭据对象，Cookie 字段为 cookie；ACFUN 兼容 {"phone":"本人手机号","password":"本人密码"}；ALIYUN 兼容 refresh_token 字段。不要输入说明文字作为真实凭据。

### 可选参数

### `DAILY_OPTIONS`

- 必填：否
- 敏感：否
- 获取或设置：自行选择；可选行为和凭据分开配置。保留原凭据 JSON 内同名选项作为兼容输入，优先于此变量。
- 填写格式：JSON 对象，键为任务标识，值为选项对象；不得包含凭据。YOUDAO：ad_count 默认 0，范围 0–3；BILIBILI：watch/share/vip_reward/silver2coin 默认 false，coin_num 默认 0、范围 0–5，coin_type=1 优先关注用户视频，否则分区视频；ACFUN：like/banana 默认 false，danmu_text 非空时开启弹幕；TIEBA：max_pages 默认 3、范围 1–5，max_forums 默认 20、范围 1–50；SMZDM：activity_id 非空才抽指定活动；IQIYI：rewards 默认 false，shake_limit 默认 10、范围 1–10；KGQQ：extended 默认 false，music_rounds 默认 4、范围 0–16；BAIDU：max_retries 或 times，总请求限制 1–5 次。V2EX 原 proxy 未实现，设置时报告配置错误，不静默忽略。

### `DAILY_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置为 1；预演仅验证配置，不证明业务成功。
- 填写格式：1 开启完全断网预演，其余值正式执行

### `DAILY_LOCAL_TEXT`

- 必填：否
- 敏感：否
- 获取或设置：自行填写公开弹幕的本地备用文本；未设置时使用兼容 danmu_text 或内置中文文本。
- 填写格式：可公开的纯文本，不含凭据；压缩空白后最多 280 字，超限使用内置文本

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自行设置通知脚本选择；显式开启总开关优先。
- 填写格式：逗号、分号或空白分隔；支持目录路径、文件名、* 通配符和目录编号 356ce64d45cd5e6e；空值关闭全部，未设置采用本任务默认名单

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：填写青龙 sendNotify.js 所在目录；未设置时自动检查 /ql/data/scripts 与 /ql/scripts。
- 填写格式：本机通知模块目录；通知不可用或超时不改变业务退出码

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个任务账号，任务标识与配套凭据只在首个 | 分隔；按行独立执行，同一服务可重复多行，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `e0dea1d0cf3efb6059b80521197d274c875e4ffa81f3060ce696257de67fde23`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/356ce64d45cd5e6e`。

## 副作用与风险

- 所选任务的每日签到、打卡、同步、领取奖励或登录刷新会话
- 显式开启有道广告奖励
- 显式开启 Bilibili 投币并点赞、观看历史上报、分享、领取权益、消耗银瓜子兑换硬币
- 显式开启 AcFun 点赞后撤销、消耗香蕉、公开发布弹幕
- 贴吧逐吧签到
- 显式开启什么值得买活动抽奖
- 显式开启爱奇艺抽奖、赠次数及权益领取
- 全民 K 歌领取核心奖励；显式开启抽奖、音乐卡及 VIP 领奖
- 选择 BAIDU 时提交站点 URL
- 正式执行通知开启时调用青龙通知渠道发送脱敏总结

## 许可证与来源

上游 `poboll/wps_script` / `polymerization/daily.js` / `609153c199ba3ca661f02dd943d74f1dea6863b4`。
