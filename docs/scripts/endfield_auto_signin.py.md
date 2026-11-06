# 终末地签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/endfield_auto_signin.py`
- 青龙命令：`python3 scripts/endfield_auto_signin.py`
- 建议 Cron：`35 8 * * *`
- 发布哈希：`0e68c8f3eb71f1db9e32845add887f364de976a663dac2f4c3b2cbd74709d095`
- 许可证：`MIT`

## 脚本功能

- 使用鹰角通行证 Token 登录国服森空岛并为终末地绑定角色每日签到
- 使用国际服 Token 登录 Skport 并为终末地绑定角色每日签到
- 遍历全部终末地绑定角色，展示官方昵称、公开 UID、渠道与奖励名称数量
- 区分签到成功与今日已签到，任一角色或账号失败时进程非零退出
- 支持完全断网预演、请求超时、时间轴日志、脱敏通知与单行 TASK_SUMMARY

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ENDFIELD_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：国服：登录 https://user.hypergryph.com/ 后访问 https://web-api.hypergryph.com/account/info/hg ，取响应 data.content 作为 Token。国际服：登录鹰角国际账号后，从本人已登录客户端或网页的授权请求中获取对应 Token。仅写入青龙环境变量，不要分享或提交到公开仓库。
- 填写格式：每个非空行一个账号：region|token。region 为 cn/skland/国服 或 global/skport/国际服；仅在第一个竖线处分割，后续原文保留为 Token。空行与 # 注释行忽略。

### 可选参数

### `SKYLAND_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入：国服鹰角网络账号 Token，获取方式同 ENDFIELD_ACCOUNTS 国服说明；可与规范变量合并使用。
- 填写格式：每个非空行一个完整 Token；不要使用分号、& 或 @ 分隔账号。

### `SKPORT_TOKEN`

- 必填：否
- 敏感：是
- 获取或设置：可选兼容输入：国际服 Skport 账号 Token，获取方式同 ENDFIELD_ACCOUNTS 国际服说明；可与规范变量合并使用。
- 填写格式：每个非空行一个完整 Token；不要使用分号、& 或 @ 分隔账号。

### `ENDFIELD_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：按网络情况设置单次 HTTPS 请求超时；留空使用 20 秒。
- 填写格式：5 至 60 之间的秒数

### `ENDFIELD_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要验证配置与签名路径但禁止联网时启用；预演不访问业务接口，也不声明真实签到成功。
- 填写格式：布尔值，默认 0；1、true、yes、on 开启完全断网预演

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、分号、空白或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选填写已有青龙 notify.py 或 sendNotify.js 所在目录；未填写时尝试导入 notify 和青龙标准脚本目录。
- 填写格式：已有通知模块所在目录路径

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

ENDFIELD_ACCOUNTS 每个非空行一个账号（region|token）；可选 SKYLAND_TOKEN / SKPORT_TOKEN 各自每行一个 Token。账号与角色独立处理，任一账号失败时进程非零退出。

## 验证与兼容性

SHA-256 `0e68c8f3eb71f1db9e32845add887f364de976a663dac2f4c3b2cbd74709d095`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/225069c5a03aea03`。

## 副作用与风险

- 为国服或国际服终末地绑定角色写入每日签到记录并领取签到奖励
- 正式执行且通知开启时向青龙通知组件发送脱敏任务总结

## 许可证与来源

上游 `Andrewww1228/Python-Endfield-Auto-Sign-In-with-Github` / `Endfield_auto_signin.py` / `ee4f48341e6e896f257076f4cd6a79d8f0d2bb74`。
