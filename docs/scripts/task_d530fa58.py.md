# 爱桌游每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/task_d530fa58.py`
- 青龙命令：`python3 scripts/task_d530fa58.py`
- 建议 Cron：`0 5 * * *`
- 发布哈希：`9640c39dfaaccb99286e49e3f268fdf389ea8e280cb3271f3c543fac285a75d3`
- 许可证：`GPL-3.0`

## 脚本功能

- 使用站点 Cookie 对爱桌游（www.lovezhuoyou.com）执行每日签到。
- 按官方 JSON 的 status / msg 判定签到成功或今日已签到。
- 若响应或用户页提供昵称、用户名或公开 UID，直接显示以便核对账号。
- 支持逐行多账号与单账号 Cookie 别名，完全断网预演、超时控制、时间轴日志与单行 TASK_SUMMARY。
- 通过青龙 notify.py 或 sendNotify.js 发送脱敏任务汇总，遵守全局开关与脚本清单。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `LOVEZHUOYOU_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://www.lovezhuoyou.com/ 后，打开开发者工具 Network，复制任意同站请求的 Cookie 请求头完整值。勿把真实 Cookie 写入仓库或示例。
- 填写格式：每个非空行一个账号的完整 Cookie；以 # 开头的行视为注释。

### 可选参数

### `LOVEZHUOYOU_COOKIE_STR`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游单账号写法：仅当 LOVEZHUOYOU_COOKIE 为空时生效，填写单个 Cookie 字符串。
- 填写格式：单个 Cookie 字符串，不含 Cookie: 前缀。

### `LOVEZHUOYOU_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：自行设置单次 HTTPS 请求超时；默认 15 秒。
- 填写格式：数字秒，范围 5 到 60。

### `LOVEZHUOYOU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：用于首次配置检查与完全断网预演；不代表真实业务成功。
- 填写格式：1、true、yes 或 on 启用；不访问业务接口。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：自行选择需要推送的脚本；设置后替代默认通知清单。
- 填写格式：逗号、分号或空白分隔目录编号、脚本相对路径、文件名或文件名通配符；支持 d530fa5843da0143、scripts/lovezhuoyou_checkin.py；* 选择全部，空值禁用全部。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选：指定已安装青龙通知模块所在目录，否则依次发现可导入的 notify、/ql/data/scripts、/ql/scripts。
- 填写格式：目录路径，包含 notify.py 或 sendNotify.js。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 Cookie；各账号独立执行，任一账号失败时整体非零退出。

## 验证与兼容性

SHA-256 `9640c39dfaaccb99286e49e3f268fdf389ea8e280cb3271f3c543fac285a75d3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d530fa5843da0143`。

## 副作用与风险

- 正式执行时向爱桌游提交每日签到，可能更新账户签到状态或积分。
- 通知启用且助手可用时发送脱敏任务汇总；无网络预演不投递外部通知。

## 许可证与来源

上游 `nix18/LovezhuoyouAutoCheck` / `index.py` / `79899de771327e1976a3f8ab76a457fc2010ef6d`。
