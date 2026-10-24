# shaco-checkin

通用签到类青龙脚本发布仓库。脚本经来源、许可证和基础检查后自动发布；真实账号人工核验后标记为已检查或上架。公开说明与本地「脚本管理」使用同一套状态：`上架` / `已检查` / `待检查`。

当前公开脚本 **218** 个：上架 **3** · 已检查 **0** · 待检查 **215**。  
本页保留上架/已检查全表与待检查预览；全部脚本请用 [脚本目录索引](docs/catalog/README.md)（字母 / 分类）浏览，详单在 [`docs/scripts/`](docs/scripts/)。
待检查脚本尚未验证真实账号业务，基础核验通过不代表业务成功。

## 脚本状态总览

| 管理状态 | 数量 | 含义 |
| --- | --- | --- |
| 上架 | 3 | 维护者确认保留的当前版本 |
| 已检查 | 0 | 必填参数齐备且已有当前版本本地运行记录，尚未点击上架 |
| 待检查 | 215 | 已发布，但尚未完成当前版本的参数配置与本地运行核验 |

### 上架脚本

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `5 0 * * *` | 上架 | [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)（`docs/scripts/cfmoto_checkin.py.md`） |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `22 8,14,20 * * *` | 上架 | [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)（`docs/scripts/kuaishou_reward_status.py.md`） |
| 摩托范每日签到 | `scripts/sudojia_moto.js` | `node scripts/sudojia_moto.js` | `26 0 * * *` | 上架 | [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)（`docs/scripts/sudojia_moto.js.md`） |

### 已检查脚本

_当前无此类脚本。_

### 待检查脚本

以下脚本可订阅，但维护者尚未完成人工核验；使用前请自行确认参数与风险。本页仅预览前 8 条。

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 139云盘云朵任务 | `scripts/139_yunduo.py` | `python3 scripts/139_yunduo.py` | `11 0 * * *` | 待检查 | [139_yunduo.py.md](docs/scripts/139_yunduo.py.md)（`docs/scripts/139_yunduo.py.md`） |
| 2cycd 论坛自动签到 | `scripts/2cycd.py` | `python3 scripts/2cycd.py` | `0 0 * * *` | 待检查 | [2cycd.py.md](docs/scripts/2cycd.py.md)（`docs/scripts/2cycd.py.md`） |
| 2cycdx自动签到 | `scripts/2cycdx.py` | `python3 scripts/2cycdx.py` | `45 0 * * *` | 待检查 | [2cycdx.py.md](docs/scripts/2cycdx.py.md)（`docs/scripts/2cycdx.py.md`） |
| 51CTO博客每日签到 | `scripts/51cto_sign.js` | `node scripts/51cto_sign.js` | `17 2 * * *` | 待检查 | [51cto_sign.js.md](docs/scripts/51cto_sign.js.md)（`docs/scripts/51cto_sign.js.md`） |
| 吾爱破解每日签到 | `scripts/52pojie.js` | `node scripts/52pojie.js` | `8 0 * * *` | 待检查 | [52pojie.js.md](docs/scripts/52pojie.js.md)（`docs/scripts/52pojie.js.md`） |
| 69云签到 | `scripts/69yun_checkin.py` | `python3 scripts/69yun_checkin.py` | `20 0 * * *` | 待检查 | [69yun_checkin.py.md](docs/scripts/69yun_checkin.py.md)（`docs/scripts/69yun_checkin.py.md`） |
| 华润通999答题 | `scripts/999.py` | `python3 scripts/999.py` | `49 1 1 1 1` | 待检查 | [999.py.md](docs/scripts/999.py.md)（`docs/scripts/999.py.md`） |
| AcFun每日任务 | `scripts/acfun.py` | `python3 scripts/acfun.py` | `9 0 * * *` | 待检查 | [acfun.py.md](docs/scripts/acfun.py.md)（`docs/scripts/acfun.py.md`） |

其余 **207** 个待检查脚本请打开 [脚本目录索引](docs/catalog/README.md)，按字母或分类查看全部。

## 青龙面板安装

进入青龙面板 → 订阅管理 → 新建订阅，按下方“订阅配置”填写，开启“自动添加任务”和“自动删除任务”，再手工运行一次订阅。青龙会根据每个脚本顶部的 `name:` / `cron:` 元数据自动创建业务任务和“本仓库依赖安装”任务；首次订阅后先运行一次依赖安装任务。也可以在脚本管理中按原路径上传单个脚本，再按“定时任务”表创建任务。

## 订阅配置

```text
名称：mortal-shaco 通用签到
类型：公开仓库
地址：https://github.com/mortal-shaco/shaco-checkin.git
分支：main
定时类型：crontab
定时规则：17 4 * * *
白名单：^scripts/.*\.(js|py|sh)$
黑名单：(^|/)(tests?|docs?|validation|shared|__pycache__)(/|$)|(^|/)(README|CHANGELOG|LICENSE)(\.|$)|(^|/)[._]
```

## 建议订阅周期

建议每天北京时间 04:17 同步：`17 4 * * *`。订阅更新与业务任务执行是两套 Cron；业务时间见下方任务表。

## 黑白名单设置

采用固定的目录级规则，不再逐个枚举脚本：白名单只同步 `scripts/` 下的 `js`、`py`、`sh` 文件，因此以后新增业务脚本无需修改订阅。黑名单进一步排除文档、测试、脱敏验证材料、`shared/` 公共组件、缓存、隐藏文件和下划线开头的辅助文件。非任务组件必须放入 `shared/`，不得放在 `scripts/`；`scripts/` 中的任务必须带青龙可识别的 `name:` / `cron:` 元数据。若面板显示“文件后缀”，填写 `js py sh`。`docs/` 仅供阅读，不会进入青龙任务同步。

## 通知策略

默认仅“上架”脚本调用青龙通知渠道；“已检查”和“待检查”脚本照常执行业务，但不推送消息。通知内容保持脱敏，通知失败不改变业务退出码。

- `QINGLONG_NOTIFY_SCRIPTS`：可选的脚本选择列表，设置后替代默认上架列表。用逗号、分号、空格或换行分隔 catalog ID、`scripts/` 相对路径、文件名或通配符；例如 `kuaishou_reward_status.py,scripts/tieba_*.py`，`*` 表示全部，空值表示全部关闭。
- `QINGLONG_NOTIFY=1`：强制全部脚本开启通知；`QINGLONG_NOTIFY=0`：强制全部关闭。显式总开关优先于脚本选择列表。

## 定时任务

业务 Cron 已错峰排布，尽量避免整点扎堆。依赖安装任务固定每周一 04:23。

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron | 管理状态 | 详单 |
| --- | --- | --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` | 维护任务 | — |

完整业务任务时间表见 [`docs/catalog/schedule.md`](docs/catalog/schedule.md)；也可按字母/分类从 [脚本目录索引](docs/catalog/README.md) 进入。

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 脚本功能

完整功能列表写在各脚本详单。本页仅摘要上架/已检查脚本；其余请通过目录索引打开详单。

- `scripts/cfmoto_checkin.py`（上架）：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。完整说明见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/kuaishou_reward_status.py`（上架）：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。完整说明见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/sudojia_moto.js`（上架）：查询账号信息并显示官方昵称，刷新当前运行中的会话凭据；提交每日签到，严格根据签到接口数字业务码 0 确认成功；按明确要求暂停签到状态查询及二次核验；查询当前能量。完整说明见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

### 必选参数（优先配置）

各脚本必选变量名称如下；格式、默认值与示例见对应详单。

- `scripts/cfmoto_checkin.py`：必选 `CFMOTO_COOKIE`；详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/kuaishou_reward_status.py`：必选 `KUAISHOU_COOKIE`；详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/sudojia_moto.js`：必选 `MOTO_TOKEN`；详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。

### 可选参数

可选变量同样写在各脚本详单中，不需要自定义行为时可先不配置。

## 参数获取方法

每个脚本的参数获取步骤写在对应详单的「环境变量与参数」中。待检查脚本请先打开 [脚本目录索引](docs/catalog/README.md) 定位后再配置。

## 验证与兼容性

- `scripts/cfmoto_checkin.py`（上架）：SHA-256 `d45204f3a633d6ef06813b9a637ed6add21ba382be8788f439062dce1e00cce6`；含 live 业务证据。详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/kuaishou_reward_status.py`（上架）：SHA-256 `c689f2a14014bfe2374054469b4564608b5db69b981f10cabbca842321f24f63`；含 live 业务证据。详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/sudojia_moto.js`（上架）：SHA-256 `d51fe6ba62db0760730c65268b698ce67296d2dad96fe22e2048c2652359c14c`；基础核验通过，业务待检查。详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。`待检查` 不代表业务失败，只表示维护者尚未完成当前版本人工核验。

## 副作用与风险

- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容。完整说明见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/kuaishou_reward_status.py`：见详单。完整说明见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/sudojia_moto.js`：正式运行提交每日签到，可能获得能量奖励；不自动重试提交；正式运行时通过青龙通知模块发送脱敏任务摘要（可关闭）。完整说明见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。 详见 [cfmoto_checkin.py.md](docs/scripts/cfmoto_checkin.py.md)。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。 详见 [kuaishou_reward_status.py.md](docs/scripts/kuaishou_reward_status.py.md)。
- `scripts/sudojia_moto.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_moto.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。 详见 [sudojia_moto.js.md](docs/scripts/sudojia_moto.js.md)。
