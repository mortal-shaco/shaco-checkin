# Web3Go每日签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/web3go.js`
- 青龙命令：`node scripts/web3go.js`
- 建议 Cron：`48 8 * * *`
- 发布哈希：`62f6d953f25b776c853c0013d3c653f4e3f941e2d3a1ec1c8640dc47578c8f50`
- 许可证：`MIT`

## 脚本功能

- 使用以太坊钱包私钥对 Web3Go/Reiki 发起 SIWE 登录（nonce + challenge），再提交每日签到。
- 查询 /api/profile，展示官方返回的非敏感身份与金叶子等摘要字段（若有）。
- 支持每行一个私钥的多账号；兼容 WEB3GO_PRIVATE_KEYS、WEB3GO_WALLETS。
- 可选 HTTP(S) 代理与请求超时。
- 按青龙全局开关与脚本名单发送脱敏通知，通知失败保留业务退出码。
- 完全断网预演：校验私钥格式、模拟阶段与通知摘要，不发起业务或通知网络请求。
- 提供中文时间轴日志、编号阶段、耗时、逐账号与全局统计，以及唯一单行 TASK_SUMMARY JSON。

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `WEB3GO_PRIVATE_KEY`

- 必填：是
- 敏感：是
- 获取或设置：使用在 https://reiki.web3go.xyz 登录的以太坊钱包私钥（本人保管）。勿使用他人私钥，勿写入公开仓库、日志或通知。
- 填写格式：每个非空行一个钱包私钥；可带或不带 0x 前缀。可选「地址|私钥」，只在首个竖线处拆分并校验地址。不使用 & 或 @ 分隔账号；以 # 开头的行忽略。

### 可选参数

### `WEB3GO_PRIVATE_KEYS`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当未设置 WEB3GO_PRIVATE_KEY 时读取；获取方式与 WEB3GO_PRIVATE_KEY 相同。
- 填写格式：与 WEB3GO_PRIVATE_KEY 相同；每行一个私钥或「地址|私钥」。

### `WEB3GO_WALLETS`

- 必填：否
- 敏感：是
- 获取或设置：兼容别名：仅当 WEB3GO_PRIVATE_KEY 与 WEB3GO_PRIVATE_KEYS 皆为空时读取；对应上游 CSV 多钱包配置。
- 填写格式：与 WEB3GO_PRIVATE_KEY 相同；每行一个私钥或「地址|私钥」。

### `WEB3GO_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：需要断网验证配置时手动设置；正式执行时删除或设为 0。
- 填写格式：1、true、yes、on 表示完全断网预演；其他值或未设置表示正式执行。预演不访问 Web3Go、不签到、不投递真实通知。

### `WEB3GO_TIMEOUT_MS`

- 必填：否
- 敏感：否
- 获取或设置：需要调整单次 HTTP 超时时间时手动设置。
- 填写格式：1000 至 120000 的整数毫秒；缺省或非法值使用 15000。

### `WEB3GO_PROXY`

- 必填：否
- 敏感：否
- 获取或设置：运行环境需要 HTTP(S) 代理访问 reiki.web3go.xyz 时填写；同时需安装 npm 包 https-proxy-agent。
- 填写格式：代理 URL，例如 http://127.0.0.1:7890；未设置则直连。

### `WEB3GO_ENABLE_MINT`

- 必填：否
- 敏感：否
- 获取或设置：上游类库含合约铸造 Pass，但入口未调用。即使设置也不会执行铸造，避免默认可变链上状态与 Gas 消耗。
- 填写格式：1、true、yes、on 仅产生警告日志；维护版仍只执行每日签到。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知总开关；未设置时仅上架脚本默认推送。显式设置后覆盖脚本选择策略。
- 填写格式：留空按上架状态；1、true、yes、on 全部开启；0、false、no、off 全部关闭。

### `QINGLONG_NOTIFY_SCRIPTS`

- 必填：否
- 敏感：否
- 获取或设置：在青龙通知名单中填入 be421593e7049fc0、实际脚本文件名或 scripts 相对路径；未设置时默认对本任务发送通知。
- 填写格式：逗号、分号、空白或换行分隔的选择器；支持 * 与 ? 通配；* 表示全部；显式空值关闭全部青龙通知。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：青龙通知工具不在默认目录时，填写本机 sendNotify.js 或 notify.py 所在目录。
- 填写格式：本地目录路径。依次尝试指定目录与 /ql/data/scripts、/ql/scripts 下的 sendNotify.js，再尝试 notify.py；通知失败只记录脱敏状态。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

WEB3GO_PRIVATE_KEY（或兼容别名 WEB3GO_PRIVATE_KEYS / WEB3GO_WALLETS）每个非空行一个钱包；可选地址前缀仅按第一个竖线分割。账号逐个独立登录与签到，任一账号失败则整体非零退出，其余账号继续执行。

## 验证与兼容性

SHA-256 `62f6d953f25b776c853c0013d3c653f4e3f941e2d3a1ec1c8640dc47578c8f50`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/be421593e7049fc0`。

## 副作用与风险

- 正式运行时向 reiki.web3go.xyz 提交每日签到，可能更新账号签到状态或奖励。
- 启用通知且非预演时，通过青龙 notify 发送脱敏账号统计。

## 许可证与来源

上游 `shuail0/web3go-chekin` / `src/web3go/web3go.js` / `01afe7cb7a8d9718d6bd2cffa4ca6f79c73014f6`。
