# 鸿星尔克签到

- 管理状态：`待检查`（与本地脚本管理一致：待检查 / 已检查 / 上架）
- 脚本路径：`scripts/erke.py`
- 青龙命令：`python3 scripts/erke.py`
- 建议 Cron：`12 1 1 1 1`
- 发布哈希：`0bda3124158f35388bacf848b1d9f063bfc1d98a616fd197b441f8f6b0823a89`
- 许可证：`MIT`

## 脚本功能

- 查询积分明细第一页五条，展示累计积分、冻结积分、可用积分和积分记录数
- 会员签到及明确已签到状态识别
- 每行一个账号，保留上游账号字段兼容，逐账号与逐阶段统计
- 展示接口返回的非敏感官方账号身份
- 完全断网预演、阶段耗时日志及单行 TASK_SUMMARY 结构化汇总
- 青龙脱敏通知，通知失败不覆盖业务退出码

## 环境变量与参数

先配置必选参数再运行；缺少任一必选参数时任务会失败。敏感值不得写入脚本、订阅地址或公开日志。

### 必选参数

### `ERKE_ACCOUNTS`

- 必填：是
- 敏感：是
- 获取或设置：登录本人鸿星尔克微信小程序，在本人授权的网络调试中查看 https://hope.demogic.com/gic-wx-app/integral_record.json 或 sign/member_sign.json 的请求体，获取 memberId、enterpriseId、unionid、openid、wxOpenid，依次对应 member_id、enterprise_id、unionid、openid、wx_openid。五项必须来自同一账号；不要分享请求体。原 config/token.json 中 erke.accounts 的每个账号对象可复制为一行 JSON，不需要该文件或原仓库。
- 填写格式：每个非空行为一个 JSON 对象，五项字段均为非空字符串；可选 account_name 和 user_agent，兼容上游字段。account_name 保留输入兼容，日志优先使用官方身份，没有官方身份时用账号序号。JSON 内部文本与标点保留，不使用 & 或 @ 分隔账号。

### 可选参数

### `ERKE_DRY_RUN`

- 必填：否
- 敏感：否
- 获取或设置：在青龙环境变量中设置；首次使用建议设为 1。
- 填写格式：1、true、yes、on 启用完全断网预演；默认 0 正式执行。

### `QINGLONG_NOTIFY`

- 必填：否
- 敏感：否
- 获取或设置：使用青龙已有通知配置；在青龙环境变量中控制通知。
- 填写格式：默认 1；0、false、no、off 关闭。断网预演仅生成通知摘要并记录未投递，不调用可能联网的通知模块。

### `QINGLONG_NOTIFY_DIR`

- 必填：否
- 敏感：否
- 获取或设置：如通知模块不在默认位置，填写本人青龙通知模块所在目录。
- 填写格式：可选目录，含 notify.py 或 sendNotify.js；通知不可用不改变业务退出码。

## 参数获取方法

完整获取说明已写在上方各变量条目中。禁止使用来源不明的第三方提取页，或把凭据粘贴到聊天、Issue 与公开日志。

## 多账号

每个非空行一个账号 JSON，同账号五项凭据组合在同一对象；逐账号、逐阶段独立处理，任一账号或配置失败时整体非零退出。

## 验证与兼容性

SHA-256 `0bda3124158f35388bacf848b1d9f063bfc1d98a616fd197b441f8f6b0823a89`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2eeae7b152108dae`。

## 副作用与风险

- 正式运行提交会员签到，可能增加积分和签到记录

## 许可证与来源

上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/erke/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
