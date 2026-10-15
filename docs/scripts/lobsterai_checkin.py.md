# LobsterAI 每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/lobsterai_checkin.py`
- 青龙命令：`python3 scripts/lobsterai_checkin.py`
- 建议 Cron：`27 0 * * *`
- 发布哈希：`9f9e673a05a1c5fa0f6e06d568761f84c5b1d04b1bf313c28b9235fa32892a12`
- 许可证：`MIT`

## 脚本功能

- 每天签到：查询活动、查询状态、幂等提交和独立复核；明确已签到时不重复提交。
- 显示积分、连续签到和活动领取天数。
- 自动查询官方客户端版本，一次运行内共用版本；失败保留上游兜底版本，支持 --version 覆盖。
- AT 临近到期时通过 RT 自动续期，以私密原子缓存支持滚动续期。
- 换行多账号和 --only UID 筛选；环境变量优先，可用 --auths 显式指定本人 JSON 凭据目录。
- 保留 --base HTTPS 地址覆盖；凭据请求拒绝重定向。
- 完全离线预演，不访问业务、版本、推送接口，不读写续期缓存。
- 青龙通知和可选 PushPlus 微信推送；所有结果生成脱敏总结，通知失败不影响业务退出码。
- 输出时间轴、编号阶段、账号及任务统计，并输出一个 TASK_SUMMARY JSON 汇总。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LOBSTERAI_TOKEN`

- 必填：是
- 敏感：是
- 获取或设置：登录官方门户 https://lobsterai.youdao.com/portal#/login，在本人浏览器开发者工具 Network 中复制 Authorization 的 Bearer 后的 accessToken；refreshToken 从本人登录响应或 Application 本地存储获取。UID 从本人账号资料获取，也可由 AT 的 JWT sub 自动识别。仅在青龙私密变量中保存。
- 填写格式：每个非空行一个账号：uid:AT:RT、uid:AT 或纯 AT。RT 可为空；同一账号字段使用英文冒号，逐个仅按首个冒号拆分并保留后续 RT 文本。不使用 @ 或 & 分隔账号。

### 可选参数

### `LOBSTERAI_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：自行设置为 1 开启完全离线预演；默认 0。
- 填写格式：1、true、yes、on 开启，其他值关闭。

### `LOBSTERAI_REFRESH_STORE`

- 必填：否
- 敏感：否
- 获取或设置：可自行指定缓存文件位置；默认脚本目录 lb_refresh_tokens.json。目录需已存在且可写，缓存含敏感凭据，请勿上传仓库。
- 填写格式：本机文件路径；文件使用 0600 权限原子保存。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知默认启用；自行设置 0 关闭青龙和 PushPlus 通知。预演仅生成通知摘要，不发送。
- 填写格式：默认 1；0、false、no、off 禁用。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可指定青龙平台 notify.py 所在目录；默认检测脚本目录、/ql/data/scripts、/ql/scripts 和 Python 模块路径。通知失败不改变业务退出码。
- 填写格式：可信本机通知模块目录。

### `PUSHPLUS_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选：在本人 PushPlus 管理页获取推送令牌，添加到青龙私密变量；保留上游微信推送功能。
- 填写格式：单个推送令牌，不是账号凭据。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

一个非空行对应一个账号，使用 LOBSTERAI_TOKEN 合并 UID、AT、RT；支持 uid:AT:RT、uid:AT 和纯 AT。每个账号独立执行，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `9f9e673a05a1c5fa0f6e06d568761f84c5b1d04b1bf313c28b9235fa32892a12`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3328423575cf7143`。

## 副作用与风险

- 向官方接口提交每日签到，领取活动积分。
- RT 自动续期会轮换账号令牌，并在本地写入私密续期缓存。
- 正式模式按配置发送脱敏青龙通知及可选 PushPlus 微信推送。

## 许可证与来源

上游 `L0NE-6/LobsterAI-AutoCheckin` / `lobsterai_checkin.py` / `4e4c291a2f616ef865e18a1c8026939754bfc712`。
