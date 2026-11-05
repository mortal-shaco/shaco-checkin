# STC国芯论坛签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/zqlj_sign.py`
- 青龙命令：`python3 scripts/zqlj_sign.py`
- 建议 Cron：`36 8 * * *`
- 发布哈希：`75f08aebe09c94b3846cb7bf00138d8414c59d79ba411deb76f85999e43c8adb`
- 许可证：`GPL-3.0`

## 脚本功能

- STC 国芯论坛（www.stcaimcu.com）Discuz zqlj_sign 每日打卡
- 识别「点击打卡 / 今日已打卡」链接与官方打卡成功、今日已打卡消息
- 页面返回公开昵称时直接展示以便核对账号
- 多账号按行处理；规范变量 STCAIMCU_COOKIE，兼容上游 STCAIMCU_COOKIES / STCAIMCU_Cookies
- 完全断网预演 STCAIMCU_DRY_RUN、HTTPS 超时、业务成功/已打卡判定
- 脱敏时间轴日志、账号与任务统计、单行 TASK_SUMMARY 与青龙通知

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `STCAIMCU_COOKIE`

- 必填：是
- 敏感：是
- 获取或设置：浏览器登录 https://www.stcaimcu.com 后，打开开发者工具网络面板，刷新页面，复制发往 www.stcaimcu.com 的请求 Cookie 请求头完整值。每个非空行填写一个账号 Cookie。不要把真实 Cookie 写入公开仓库、日志或通知。
- 填写格式：每行一个 Cookie 字符串（内部可用分号分隔键值对）；账号之间只用换行分隔，不使用 & 或 @

### 可选参数

### `STCAIMCU_COOKIES`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游 README 别名：仅当 STCAIMCU_COOKIE 为空时生效，格式与规范变量相同。
- 填写格式：每行一个 Cookie；与 STCAIMCU_COOKIE 二选一

### `STCAIMCU_Cookies`

- 必填：否
- 敏感：是
- 获取或设置：兼容上游脚本变量名：仅当 STCAIMCU_COOKIE 与 STCAIMCU_COOKIES 均为空时生效。
- 填写格式：每行一个 Cookie；与规范变量二选一

### `STCAIMCU_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：离线检查时设置；只校验配置并模拟打卡阶段，不访问网络、不改动签到状态、不真实发送通知。
- 填写格式：1、true、yes、on 开启完全断网预演；默认关闭

### `STCAIMCU_TIMEOUT`

- 必填：否
- 敏感：否
- 获取或设置：可选：单次 HTTPS 请求超时秒数。
- 填写格式：5 到 60 的数字；默认 15

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：可选脚本选择列表；设置后替代默认名单，只为匹配的脚本开启通知。
- 填写格式：用逗号、空格、分号或换行分隔 catalog ID、相对路径、文件名或通配符；* 表示全部，空值表示全部关闭

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录；失败不改变业务退出码。
- 填写格式：目录路径；还会尝试 /ql/data/scripts 与 /ql/scripts

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每行一个已登录 Cookie；账号独立处理，任一账号失败时整体以非零退出码结束

## 验证与兼容性

SHA-256 `75f08aebe09c94b3846cb7bf00138d8414c59d79ba411deb76f85999e43c8adb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/aeb184ef4b033ac4`。

## 副作用与风险

- 向 STC 国芯论坛 zqlj_sign 打卡接口提交每日打卡，改变当日打卡状态并可能累计连续打卡或站点奖励
- 通知已启用且适配器可用时向青龙通知通道发送脱敏任务统计

## 许可证与来源

上游 `klxf/stc-auto-check-in` / `zqlj_sign.py` / `85cdd8b81bbc1e3d9526ff55395cc82d0282c98a`。
