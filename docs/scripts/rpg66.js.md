# 橙光每日任务

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/rpg66.js`
- 青龙命令：`node scripts/rpg66.js`
- 建议 Cron：`20 10 * * *`
- 发布哈希：`a34f798e363d2f43c1f619c9ea0de4afaafc5c8036dc076798cebe8edc299c08`
- 许可证：`MIT`

## 脚本功能

- 每日签到与鲜橙余额查询
- 盘点日常、每周、限时、成长任务及手动任务提示
- 领取已完成的橙树奖励与旧版活跃奖励
- 显式开启阅读时长上报，取消内置作品目标
- 显式开启频道页与分享页浏览计时，并核验任务进度
- 显式开启狗橙推荐切换、推荐收藏与指定作品收藏
- 显式开启动态点赞、作品分享、悬赏回帖、角色告白与公开收藏夹创建
- 送花须开启任务并单独明确许可和目标，可能消耗真实鲜花
- 回帖优先一言并保留作者与来源署名，各类获取失败均回退本地文本
- 逐账号脱敏日志、分阶段统计、结构化任务汇总、可选青龙通知与完全断网预演

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `RPG66_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录橙光官方客户端，仅在本人授权抓包的请求中取得 uid、token；需要签名接口时一并取得 skey。凭据失效后重新登录获取，不向第三方提供。作品 ID 从官方作品页获取。
- 填写格式：每个非空行一个 JSON 对象，必填 uid（数字字符串）、token（非空字符串）；可选 skey，以及原有 gameid、readGameId/read_gameid、flowerTarget/flower_target、confessionGameId/confession_gameid、allowSendFlowers/allow_send_flowers/sendFlowers（布尔值）。不使用符号分隔账号，JSON 字符串保留凭据中的分隔符。

### 可选参数

### `RPG66_TASKS`

- 必填：否
- 敏感：否
- 获取或设置：自行选择需要执行的任务；互动、公开内容、上报和消费须显式开启。送花还须账号对象中的送花许可为 true。
- 填写格式：逗号分隔任务名；默认 balance,sign,claim-tree,claim-old。可选 runtime,browse-channel,browse-share,dog-next,dog-favorite,like,favorite,share,flowers,reply,confession,collections。favorite/share 需要 gameid；runtime 需要 readGameId/read_gameid/gameid；flowers/confession 需要对应目标 ID 或 gameid。

### `RPG66_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线验证时设为 1。
- 填写格式：1 表示完全断网预演，其余值正式执行。

### `RPG66_LOCAL_TEXT`

- 必填：否
- 敏感：否
- 获取或设置：可自行设置回帖本地兜底文本；请勿填写个人资料或凭据。
- 填写格式：归并空白后不超过 280 个字符；无效时使用内置中文文本。一言优先，预演不调用一言。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：选择需要通知的脚本；设置后替换默认选择。
- 填写格式：逗号、分号或空白分隔，可用目录编号、scripts/rpg66.js、rpg66.js、candidate.js 或文件名星号通配符；* 全选，空值全部关闭。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填已有青龙 sendNotify.js 所在目录；否则自动查找 /ql/data/scripts 与 /ql/scripts。
- 填写格式：通知模块目录，不作为业务运行依赖；缺失或投递失败保留业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON；独立处理全部账号，任一账号失败则整体非零退出。兼容原调用方在进程中注入 config.rpg66 对象，不依赖私有文件。

## 验证与兼容性

SHA-256 `a34f798e363d2f43c1f619c9ea0de4afaafc5c8036dc076798cebe8edc299c08`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/38acc6660ed7ac1b`。

## 副作用与风险

- 每日签到并领取签到奖励
- 领取已完成的橙树及旧版活跃奖励
- 按显式开关上报阅读时长、浏览计时及推荐切换，改变任务进度
- 按显式开关收藏作品、点赞动态、分享作品、发表悬赏回帖、角色告白及创建公开收藏夹
- 双重显式开启后向目标作品赠送并消耗真实鲜花
- 选中通知时通过青龙通知渠道发送脱敏统计

## 许可证与来源

上游 `Wenmoux/checkbox` / `scripts/rpg66.js` / `a22d8650ae69224c18c4856afdf9fbdf8622c54f`。
