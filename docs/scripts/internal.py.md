# 智慧树共享课每日习惯分

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/internal.py`
- 青龙命令：`python3 scripts/internal.py`
- 建议 Cron：`20 7 * * *`
- 发布哈希：`c15be24ec4fa6c77c770dc1a84150c96342244be4de0d96c8e65575445db21aa`
- 许可证：`MIT`

## 脚本功能

- 按前端节奏分批上报共享课学习时长，用于获取每日习惯分
- 读取课程与视频列表并选择视频进行学习时长累计
- 校验 Cookie 登录态与 recruitAndCourseId 课程参数
- 支持自定义每日分钟数、单批秒数与假定倍速
- 本地状态记录今日已完成，可强制再跑
- 多账号独立处理，任一账号失败时整体非零退出
- 完全断网预演、脱敏时间轴日志、机器可读汇总和青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ZHS_HABIT_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录智慧树共享课学习页后，在开发者工具网络面板任选 studyservice-api.zhihuishu.com 请求，复制请求头 Cookie 完整值（需含 jt-cas、CASLOGC 等）。recruitAndCourseId 取自学习页 URL 参数。同仓库登录脚本仅用于本机扫码取 Cookie，不能在青龙里交互扫码。Cookie 约 24 小时过期后需重新获取。不要把 Cookie 发给他人或写入公开仓库。
- 填写格式：每行一个账号：Cookie|recruitAndCourseId，或 备注|Cookie|recruitAndCourseId；账号之间仅用换行分隔，不使用 & 或 @

### 可选参数

### `ZHS_HABIT_COOKIE`

- 必填：否
- 敏感：是
- 获取或设置：单账号兼容别名：未配置 ZHS_HABIT_ACCOUNTS 时，与 ZHS_HABIT_RAC 一起填写。已配置 ZHS_HABIT_ACCOUNTS 时忽略本变量。
- 填写格式：完整 Cookie 字符串，需含 jt-cas 与 CASLOGC

### `ZHS_HABIT_RAC`

- 必填：否
- 敏感：否
- 获取或设置：单账号兼容别名：与 ZHS_HABIT_COOKIE 配套填写共享课 recruitAndCourseId。
- 填写格式：学习页 URL 中的 recruitAndCourseId 参数值，不是占位符

### `ZHS_HABIT_REMARK`

- 必填：否
- 敏感：否
- 获取或设置：可选：单账号模式下的显示备注名，便于日志核对。
- 填写格式：任意短文本

### `ZHS_HABIT_MINUTES`

- 必填：否
- 敏感：否
- 获取或设置：可选：每日目标学习分钟数，默认 25（对齐上游前端习惯分目标）。
- 填写格式：1 到 180 之间的数字

### `ZHS_HABIT_CHUNK`

- 必填：否
- 敏感：否
- 获取或设置：可选：单批上报秒数，默认 540。
- 填写格式：60 到 1800 之间的数字

### `ZHS_HABIT_SPEED`

- 必填：否
- 敏感：否
- 获取或设置：可选：假定播放倍速，影响 watchPoint 采样密度，默认 1.8。
- 填写格式：0.5 到 3 之间的数字

### `ZHS_HABIT_FORCE`

- 必填：否
- 敏感：否
- 获取或设置：可选：设为 1 时忽略本地「今日已完成」状态并强制再跑一次。
- 填写格式：1、true、yes、on 表示强制

### `ZHS_HABIT_STATE_FILE`

- 必填：否
- 敏感：否
- 获取或设置：可选：指定每日完成状态文件路径；留空使用脚本目录下 zhihuishu_habit_state.json。
- 填写格式：可写文件的绝对或相对路径

### `ZHS_HABIT_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选：单次接口请求超时秒数，默认 25。
- 填写格式：5 到 120 之间的数字

### `ZHS_HABIT_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：可选：设为 1 进入完全断网预演，校验配置与计划步骤但不发起任何网络请求。
- 填写格式：1、true、yes、on 表示开启预演

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录。
- 填写格式：目录路径；失败后继续尝试 /ql/data/scripts 与 /ql/scripts；通知失败不改变业务退出码

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个账号，行内用竖线分隔：Cookie|recruitAndCourseId，或 备注|Cookie|recruitAndCourseId；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `c15be24ec4fa6c77c770dc1a84150c96342244be4de0d96c8e65575445db21aa`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/887bba5f8efd3762`。

## 副作用与风险

- 实时模式会向智慧树学习接口上报学习时长，可能改变账号学习进度与每日习惯分
- 会写入本地状态文件记录当日完成情况
- 启用通知且发现青龙通知组件时，会发送脱敏任务结果通知

## 许可证与来源

上游 `eplayn/zhihuishu-toolkit` / `internal/_共享课_每日习惯分.py` / `a74a636431530c0843a0f6ba369de36b794a1ccd`。
