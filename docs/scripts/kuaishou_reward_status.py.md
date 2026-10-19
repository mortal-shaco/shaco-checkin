# 快手奖励任务

- 管理状态：`上架`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/kuaishou_reward_status.py`
- 青龙命令：`python3 scripts/kuaishou_reward_status.py`
- 建议 Cron：`22 8,14,20 * * *`
- 发布哈希：`c689f2a14014bfe2374054469b4564608b5db69b981f10cabbca842321f24f63`
- 许可证：`MIT`

## 脚本功能

- 只读查询快手收益与任务状态
- 按白名单输出非敏感状态字段
- 换行多账号独立执行并汇总

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `KUAISHOU_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：在本人已登录的快手或快手极速版中打开“积分换好礼”页面，从本人控制的本地网络调试记录里找到 accelerate/info 请求，复制 Cookie 请求头；至少保留 kuaishou.api_st。不要绕过证书固定或使用第三方提取网站。
- 填写格式：每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 & 或 @ 分隔

### 可选参数

### `KUAISHOU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：无需获取；预演时手工设置为 1，正式查询时删除或设为 0。
- 填写格式：1/true/yes/on 开启断网预演

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。
- 默认值：`1`

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：本地目录路径

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认上架列表，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、scripts/相对路径、文件名或文件名通配符；* 表示全部，空值表示全部关闭。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

KUAISHOU_COOKIE 每个非空行对应一个账号；任一账号失败时任务整体非零退出

## 验证与兼容性

SHA-256 `c689f2a14014bfe2374054469b4564608b5db69b981f10cabbca842321f24f63`；live 业务成功证据位于 `projects/checkin/validation/ks_cleanroom_v1`。

## 副作用与风险

- 无额外已记录副作用。

## 许可证与来源

洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。
