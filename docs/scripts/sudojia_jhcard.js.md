# 江淮卡友

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/sudojia_jhcard.js`
- 青龙命令：`node scripts/sudojia_jhcard.js`
- 建议 Cron：`7 0 * * *`
- 发布哈希：`090c2c6b35bbc7cee71b916d1fe1ba5f4fa779a3b29a3da523ba56454465554b`
- 许可证：`GPL-3.0`

## 脚本功能

- 登录并展示官方返回的账号姓名，不展示手机号或凭据
- 每日签到
- 查询连续签到天数
- 查询当前积分
- 显式开启后执行五次随机帖子评论
- 公开评论优先使用一言文案及作者、出处署名，失败时采用本地文案
- 每行一个账号、独立处理、失败非零退出
- 完全断网预演、脱敏通知、时间轴日志及结构化汇总

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `JHCARD_BODY`

- 必填：是
- 敏感：是
- 获取或设置：在江淮卡友 APP 登录时抓取 http://jacwxmp.starnetah.com:18280/v2driver/v2/login 的原始请求体，保留所有字段；失效后重新抓取。服务原接口使用明文 HTTP。
- 填写格式：每个非空行一个完整 JSON，必需 phone、password、sendMessageKey、deviceType、appType、sign；行末可追加 #true 开启五次公开评论，#false 或省略均关闭。JSON 内的分隔字符原样保留，不使用 & 分隔账号。

### 可选参数

### `JHCARD_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：1 开启，其余值正式运行

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知全局开关，默认开启；预演只展示脱敏通知，不联网投递。
- 填写格式：0、false、no、off 关闭，忽略大小写

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；默认查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：本地目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，登录 JSON 与该账号的可选评论开关放在同一行；账号独立执行，任一失败整体非零退出。

## 验证与兼容性

SHA-256 `090c2c6b35bbc7cee71b916d1fe1ba5f4fa779a3b29a3da523ba56454465554b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0dc8d7553d45c649`。

## 副作用与风险

- 签到并领取服务端发放的积分
- 仅在账号显式追加 #true 时发表五次公开评论

## 许可证与来源

上游 `sudojia/AutoTaskScript` / `src/client/sudojia_jhcard.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
