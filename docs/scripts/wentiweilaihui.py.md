# 华润通文体未来荟签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/wentiweilaihui.py`
- 青龙命令：`python3 scripts/wentiweilaihui.py`
- 建议 Cron：`1 1 1 1 1`
- 发布哈希：`f91a3a6a1873b350c695cc5466ff224a18d90d01e59e013c5a319dfc55facc24`
- 许可证：`MIT`

## 脚本功能

- 查询签到记录及今日签到状态
- 今日已签到时跳过重复签到，否则执行每日签到
- 查询并展示当前会员积分
- 官方响应提供昵称、用户名、显示名称或公开 UID 时展示非敏感账号身份
- 逐行多账号独立处理，兼容裸 JWT、完整 Wechat 登录令牌及原账号对象字段
- 完全断网预演和逐阶段脱敏日志、账号与子任务统计、单行结构化总结
- 正式执行后通过青龙通知发送脱敏总结，通知不可用不改变业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WENTIWEILAIHUI_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：微信打开文体未来荟小程序并登录本人账号，使用本人授权的抓包工具读取 wlhmobile.crland.com.cn 请求头 Authorization 中的 Wechat 登录令牌。保留完整令牌，不向他人发送；过期时重新登录获取。会员积分查询需要令牌载荷含 openid。
- 填写格式：每个非空行一个账号，可填裸 JWT 或完整 Wechat JWT；也可每行一个 JSON 对象，字段 token 必填，account_name、mobile、user_agent 可选，沿用上游字段名。JSON 不跨行；手机号兼容输入不发送不输出，账号名称不作为官方身份。不得用 &、@ 分隔账号。

### 可选参数

### `WENTIWEILAIHUI_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量手动设置，测试时使用 1。
- 填写格式：1 开启完全离线预演；0、false、no、off 关闭，默认 0。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙全局通知开关，默认启用。配置青龙 notify.py 或 sendNotify.js 的推送渠道。
- 填写格式：0、false、no、off 禁用，其余值启用；预演仅模拟通知，保证完全断网。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：仅在通知模块位于自定义目录时填写，默认发现可导入 notify 或青龙标准目录。
- 填写格式：包含 notify.py 或 sendNotify.js 的本地目录，不用于业务接口或凭据配置；JavaScript 通知仅在已有 Node.js 时可用。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号，独立执行签到及积分查询。JSON 对象将配套字段放在同一行，完整保存令牌及 User-Agent。任一账号或子任务失败整体非零退出。

## 验证与兼容性

SHA-256 `f91a3a6a1873b350c695cc5466ff224a18d90d01e59e013c5a319dfc55facc24`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/afa2f50b7baa69db`。

## 副作用与风险

- 未签到时执行文体未来荟每日签到，可能增加积分
- 正式模式启用通知时发送脱敏任务总结

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/wentiweilaihui/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
