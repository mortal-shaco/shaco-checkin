# AbyssWorld每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_ad4c4f3a.js`
- 青龙命令：`node scripts/task_ad4c4f3a.js`
- 建议 Cron：`39 8 * * *`
- 发布哈希：`371bdee1487e1a29cf4f4f5cdd963877edc00a3921d13bd8b65fc6452e0f0b86`
- 许可证：`MIT`

## 脚本功能

- 使用 AbyssWorld Bearer Token 提交每日签到（POST /api/user/checkin）。
- 签到后查询签到结果（GET /api/user/checkin），展示可用的非敏感摘要与官方身份字段。
- 识别签到成功与今日已签到；支持每行一个 Token 多账号，兼容上游 TOKEN 逗号分隔。
- 可选自定义 API 根地址与请求超时。
- 按青龙全局开关与脚本名单发送脱敏通知，通知失败保留业务退出码。
- 完全断网预演：校验 Token 格式、模拟阶段与通知摘要，不发起业务或通知网络请求。
- 提供中文时间轴日志、编号阶段、耗时、逐账号与全局统计，以及唯一单行 TASK_SUMMARY JSON。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ABYSSWORLD_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：登录本人 Abyss World / AbyssWorldHQ 官网或控制台，打开开发者工具 Network，找到发往 ca.abyssworld.games 的请求，复制 Authorization 头中 Bearer 后的 Token。勿使用他人 Token，勿写入公开仓库、日志或通知。
- 填写格式：每个非空行一个账号 Token。可不含 Bearer 前缀（脚本会自动补全）。可选「备注|token」，只在首个竖线处拆分。不使用 & 或 @ 分隔账号。

### 可选参数

### `TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游变量名：仅当未设置 ABYSSWORLD_TOKEN 时读取；获取方式与 ABYSSWORLD_TOKEN 相同。
- 填写格式：每行一个 Token；若整段无换行且含英文逗号，会按上游习惯拆成多账号。

### `ABYSSWORLD_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要断网验证配置时手动设置；正式执行时删除或设为 0。
- 填写格式：1、true、yes、on 表示完全断网预演；其他值或未设置表示正式执行。预演不访问 AbyssWorld、不签到、不投递真实通知。

### `ABYSSWORLD_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整单次 HTTP 超时时间时手动设置。
- 填写格式：1000 至 60000 的整数毫秒；缺省或非法值使用 15000。

### `ABYSSWORLD_BASE_URL`

- 必填：否
- 敏感：否
- 获取或设置：官方 API 根地址变更时手动覆盖；一般可留空。
- 填写格式：HTTPS 根地址，不要末尾斜杠；缺省为 https://ca.abyssworld.games

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙通知名单中填入 ad4c4f3ab8ede7e1、实际脚本文件名或 scripts 相对路径；未设置时默认对本任务发送通知。
- 填写格式：逗号、分号、空白或换行分隔的选择器；支持 * 与 ? 通配；* 表示全部；显式空值关闭全部青龙通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知工具不在默认目录时，填写本机 sendNotify.js 或 notify.py 所在目录。
- 填写格式：本地目录路径。依次尝试指定目录与 /ql/data/scripts、/ql/scripts 下的 sendNotify.js，再尝试 notify.py；通知失败只记录脱敏状态。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

ABYSSWORLD_TOKEN（或兼容 TOKEN）每个非空行一个账号 Token；可选备注仅按第一个竖线分割。账号逐个独立签到并查询结果，任一账号失败则整体非零退出，其余账号继续执行。

## 验证与兼容性

SHA-256 `371bdee1487e1a29cf4f4f5cdd963877edc00a3921d13bd8b65fc6452e0f0b86`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ad4c4f3ab8ede7e1`。

## 副作用与风险

- 正式运行时向 AbyssWorld checkin 接口提交每日签到，可能更新账号签到状态或积分。
- 启用通知且非预演时，通过青龙 notify 发送脱敏账号统计。

## 许可证与来源

上游 `skyMetaverse/AbyssWorldHQ` / `main.js` / `4ae3ae0bdadabee03b6a4e43fdd2093ed2d768bc`。
