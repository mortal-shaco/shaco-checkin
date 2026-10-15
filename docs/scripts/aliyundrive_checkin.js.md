# 阿里云盘每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/aliyundrive_checkin.js`
- 青龙命令：`node scripts/aliyundrive_checkin.js`
- 建议 Cron：`55 1 * * *`
- 发布哈希：`fee8a691a59047cf508700e812eea33b121d73673ecdeaff276de5c0bf0d7e8d`
- 许可证：`GPL-3.0`

## 脚本功能

- 通过刷新令牌获取访问令牌并展示官方返回的昵称、用户名或公开用户标识
- 每日签到并展示本月累计签到天数
- 领取当日奖励并识别已领取状态
- 查询并展示本月签到日历
- 展示当日签到奖励和任务奖励概览
- 每行一个账号，独立执行并汇总失败
- 完全断网预演，模拟通知并明确未验证真实业务
- 青龙脱敏通知及可选 HTTPS PushPlus 推送，支持全局关闭
- 分阶段时间轴日志、逐账号统计和单行 TASK_SUMMARY 结构化汇总

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `refreshToken`

- 必填：是
- 敏感：是
- 获取或设置：登录阿里云盘网页版 https://www.aliyundrive.com/，在浏览器开发者工具控制台读取 JSON.parse(localStorage.token).refresh_token，复制到青龙私密环境变量；不要公开或写入日志。
- 填写格式：每个非空行填写一个账号的 refresh_token；仅按换行分隔，不支持 & 或 @ 分隔账号。

### 可选参数

### `ALIYUNDRIVE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：1 表示完全断网预演，其他值或未设置表示正式执行。

### `ALIYUN_PUSH_PLUS`

- 必填：否
- 敏感：是
- 获取或设置：从 PushPlus 官网账户获取推送令牌，存入青龙私密环境变量。
- 填写格式：单个 PushPlus 推送令牌；未设置时只使用青龙通知。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：默认 1；0、false、no、off 关闭全部通知，大小写不敏感。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：如默认青龙路径未找到通知模块，填写本机青龙 sendNotify.js 所在目录。业务执行不依赖此目录。
- 填写格式：可选通知模块目录；默认依次查找 /ql/data/scripts、/ql/scripts 和候选脚本所在目录。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

refreshToken 每个非空行一个账号；账号顺序独立执行，任一账号失败则进程非零退出。

## 验证与兼容性

SHA-256 `fee8a691a59047cf508700e812eea33b121d73673ecdeaff276de5c0bf0d7e8d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bd7e90cbb255e115`。

## 副作用与风险

- 刷新账号访问令牌
- 执行每日签到
- 领取当日签到奖励
- 向青龙通知渠道和可选 PushPlus 渠道发送脱敏任务总结（预演不发送）

## 许可证与来源

上游 `huwangkeji/aliyundrive_checkin` / `aliyundrive_checkin.js` / `267ee025840c5b55dce5b5e1e365fb52ac500fce`。
