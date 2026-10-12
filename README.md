# shaco-checkin

通用签到类青龙脚本发布仓库。脚本经来源、许可证和基础检查后发布；真实账号检查和人工保留、下架在发布后进行。各脚本验证状态见下文。

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

采用固定的目录级规则，不再逐个枚举脚本：白名单只同步 `scripts/` 下的 `js`、`py`、`sh` 文件，因此以后新增业务脚本无需修改订阅。黑名单进一步排除文档、测试、脱敏验证材料、`shared/` 公共组件、缓存、隐藏文件和下划线开头的辅助文件。非任务组件必须放入 `shared/`，不得放在 `scripts/`；`scripts/` 中的任务必须带青龙可识别的 `name:` / `cron:` 元数据。若面板显示“文件后缀”，填写 `js py sh`。

## 定时任务

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron |
| --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` |
| 艾特校园圈 | `scripts/atxyq.py` | `python3 scripts/atxyq.py` | `9 10,23 * * *` |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` |
| 百事乐元抽奖 | `scripts/bsly_draw.py` | `python3 scripts/bsly_draw.py` | `0 9 * * *` |
| 霸王茶姬签到 | `scripts/bwcj.py` | `python3 scripts/bwcj.py` | `0 9,18 * * *` |
| 成都地铁签到 | `scripts/cdrail.py` | `python3 scripts/cdrail.py` | `0 9 * * *` |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` |
| DDNSTO七天免费续费 | `scripts/ddnsto.py` | `python3 scripts/ddnsto.py` | `30 9 * * *` |
| 杜蕾斯会员中心 | `scripts/durex.py` | `python3 scripts/durex.py` | `9 9 * * *` |
| ikuuu 签到 | `scripts/ikuuu_checkin.py` | `python3 scripts/ikuuu_checkin.py` | `0 21 * * *` |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` |
| Wallhaven最新壁纸下载 | `scripts/main.py` | `python3 scripts/main.py` | `0 8 * * *` |
| NGA 论坛签到 | `scripts/nga_checkin.py` | `python3 scripts/nga_checkin.py` | `1 17 * * *` |
| NodeSeek 论坛签到 | `scripts/nodeseek_checkin.py` | `python3 scripts/nodeseek_checkin.py` | `23 14 * * *` |
| PassNAT 签到 | `scripts/passnat_checkin.py` | `python3 scripts/passnat_checkin.py` | `18 0 * * *` |
| 夸克网盘每日签到 | `scripts/quark_signin.py` | `python3 scripts/quark_signin.py` | `13 18 * * *` |
| 顺丰速运签到 | `scripts/sfsu_checkin.py` | `python3 scripts/sfsu_checkin.py` | `9 15 * * *` |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `31 8 * * *` |
| 33台词每日签到 | `scripts/sudojia_33agilestudio.js` | `node scripts/sudojia_33agilestudio.js` | `1 11 * * *` |
| 所有女生会员签到 | `scripts/sudojia_allgirls.js` | `node scripts/sudojia_allgirls.js` | `19 16 * * *` |
| 安慕希每日签到 | `scripts/sudojia_amx.js` | `node scripts/sudojia_amx.js` | `33 14 * * *` |
| 香蕉视频每日任务 | `scripts/sudojia_bananavideo.js` | `node scripts/sudojia_bananavideo.js` | `10 1 * * *` |
| 贝因美每日签到 | `scripts/sudojia_beiyinmei.js` | `node scripts/sudojia_beiyinmei.js` | `19 11 * * *` |
| 植物星球 | `scripts/sudojia_botanystar.js` | `node scripts/sudojia_botanystar.js` | `32 13 * * *` |
| 霸王茶姬每日签到与积分提醒 | `scripts/sudojia_bwtea.js` | `node scripts/sudojia_bwtea.js` | `22 11 * * *` |
| 七彩虹商城 | `scripts/sudojia_colorful_mall.js` | `node scripts/sudojia_colorful_mall.js` | `14 12 * * *` |
| 飞蚂蚁旧衣回收 | `scripts/sudojia_flyant.js` | `node scripts/sudojia_flyant.js` | `0 6 * * *` |
| 飞牛私有云签到 | `scripts/sudojia_fnnas.js` | `node scripts/sudojia_fnnas.js` | `10 0 * * *` |
| 厚工坊签到与任务 | `scripts/sudojia_hgf.js` | `node scripts/sudojia_hgf.js` | `33 5 * * *` |
| 海澜之家-游戏 | `scripts/sudojia_hlzj_game.js` | `node scripts/sudojia_hlzj_game.js` | `39 8,15,20 * * *` |
| 媓钻护肤品 | `scripts/sudojia_hzhfp.js` | `node scripts/sudojia_hzhfp.js` | `29 11 * * *` |
| 玩拍由我俱乐部 | `scripts/sudojia_instax.js` | `node scripts/sudojia_instax.js` | `41 9 * * *` |
| 江淮卡友 | `scripts/sudojia_jhcard.js` | `node scripts/sudojia_jhcard.js` | `55 5 * * *` |
| 多娇江山 | `scripts/sudojia_jiangshan.js` | `node scripts/sudojia_jiangshan.js` | `26 9 * * *` |
| 金典有机生活+ | `scripts/sudojia_jindian.js` | `node scripts/sudojia_jindian.js` | `56 7 * * *` |
| 嘉立创每日签到 | `scripts/sudojia_jlc.js` | `node scripts/sudojia_jlc.js` | `30 6 * * *` |
| 嘉立创硬件开源平台 | `scripts/sudojia_jlc_yj.js` | `node scripts/sudojia_jlc_yj.js` | `44 5 * * *` |
| 稀土掘金每日签到 | `scripts/sudojia_juejin.js` | `node scripts/sudojia_juejin.js` | `5 10 * * *` |
| 植白说官方商城 | `scripts/sudojia_kozbs.js` | `node scripts/sudojia_kozbs.js` | `18 9 * * *` |
| 开天工作室 | `scripts/sudojia_ktgzs.js` | `node scripts/sudojia_ktgzs.js` | `33 9 * * *` |
| 顾家家居签到 | `scripts/sudojia_kukahome.js` | `node scripts/sudojia_kukahome.js` | `5 10 * * *` |
| 库街区每日签到 | `scripts/sudojia_kuro.js` | `node scripts/sudojia_kuro.js` | `22 8 * * *` |
| 老板电器服务微商城 | `scripts/sudojia_laoban.js` | `node scripts/sudojia_laoban.js` | `15 9 * * *` |
| 龙湖天街 | `scripts/sudojia_longfor.js` | `node scripts/sudojia_longfor.js` | `39 8 * * *` |
| 欣都龙城每日签到 | `scripts/sudojia_mallcoo.js` | `node scripts/sudojia_mallcoo.js` | `48 10 * * *` |
| 馬伍旺饮料厂 | `scripts/sudojia_mawuwang.js` | `node scripts/sudojia_mawuwang.js` | `48 6 * * *` |
| 美的会员 | `scripts/sudojia_midea.js` | `node scripts/sudojia_midea.js` | `33 11 * * *` |
| 摩托范每日签到 | `scripts/sudojia_moto.js` | `node scripts/sudojia_moto.js` | `33 3 * * *` |
| 蜜雪冰城每日签到 | `scripts/sudojia_mxbc.js` | `node scripts/sudojia_mxbc.js` | `28 10 * * *` |
| 奈雪点单 | `scripts/sudojia_naixue.js` | `node scripts/sudojia_naixue.js` | `36 9 * * *` |
| 雀巢会员 | `scripts/sudojia_nestle.js` | `node scripts/sudojia_nestle.js` | `28 8 * * *` |
| 南方航空 | `scripts/sudojia_nfhk.js` | `node scripts/sudojia_nfhk.js` | `49 11 * * *` |
| OPPO商城每日签到与任务领奖 | `scripts/sudojia_opposhop.js` | `node scripts/sudojia_opposhop.js` | `25 12 * * *` |
| 胖哥俩肉蟹煲 | `scripts/sudojia_pangge.js` | `node scripts/sudojia_pangge.js` | `19 6 * * *` |
| 爷爷不泡茶 | `scripts/sudojia_paotea.js` | `node scripts/sudojia_paotea.js` | `30 9 * * *` |
| 上海杨浦 | `scripts/sudojia_shmedia.js` | `node scripts/sudojia_shmedia.js` | `33 7 * * *` |
| 水费易签到 | `scripts/sudojia_shuifei.js` | `node scripts/sudojia_shuifei.js` | `3 9 * * *` |
| SSPANEL面板签到 | `scripts/sudojia_sspanel.js` | `node scripts/sudojia_sspanel.js` | `35 9 * * *` |
| 星妈优选 | `scripts/sudojia_starmom.js` | `node scripts/sudojia_starmom.js` | `39 2 * * *` |
| 特步会员中心 | `scripts/sudojia_tebu.js` | `node scripts/sudojia_tebu.js` | `26 10 * * *` |
| TILTA影像城 | `scripts/sudojia_tilta.js` | `node scripts/sudojia_tilta.js` | `5 10 * * *` |
| 图虫每日签到 | `scripts/sudojia_tuchong.js` | `node scripts/sudojia_tuchong.js` | `38 5 * * *` |
| V2EX每日签到 | `scripts/sudojia_v2ex.js` | `node scripts/sudojia_v2ex.js` | `0 9 * * *` |
| 薇诺娜专柜商城 | `scripts/sudojia_wnna.js` | `node scripts/sudojia_wnna.js` | `39 9 * * *` |
| 新湖南每日签到 | `scripts/sudojia_xhn.js` | `node scripts/sudojia_xhn.js` | `51 4 * * *` |
| 享玩游戏APP | `scripts/sudojia_xiangwan.js` | `node scripts/sudojia_xiangwan.js` | `33 0 * * *` |
| 小米社区-小程序 | `scripts/sudojia_xiaomi_community.js` | `node scripts/sudojia_xiaomi_community.js` | `48 9 * * *` |
| 心喜签到 | `scripts/sudojia_xinxi.js` | `node scripts/sudojia_xinxi.js` | `43 12 * * *` |
| 兴攀农场 | `scripts/sudojia_xpfarm.js` | `node scripts/sudojia_xpfarm.js` | `50 11,18 * * *` |
| 智能电视签到 | `scripts/sudojia_znds.js` | `node scripts/sudojia_znds.js` | `5 11 * * *` |
| 甄稀冰淇淋每日签到 | `scripts/sudojia_zxice.js` | `node scripts/sudojia_zxice.js` | `22 15 * * *` |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `55 9 * * *` |
| 天翼云盘签到 | `scripts/ty_netdisk_checkin.py` | `python3 scripts/ty_netdisk_checkin.py` | `1 16 * * *` |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 脚本功能

- `scripts/aliyunpan_checkin.py`：执行阿里云盘每日会员签到并明确验证接口结果；按换行多账号独立处理并汇总退出状态；提供完全断网且结果确定的预演模拟；检测刷新令牌轮换并可选安全写入本地文件。
- `scripts/atxyq.py`：查询并直接展示官方昵称，查询学校启用状态与积分任务列表。；每日签到，核验连续天数与获得积分。；领取普通任务奖励，保持上游排除新用户奖励、集赞有奖、发布任务和邀请有奖。；查询当前可用积分。；显式开启最多两篇校园文章的点赞与取消点赞。；显式发布动态，优先一言正文及作者来源署名，所有声明失败情形回退本地文本；可登记本人已有图片。；显式查询并清理本人最近十篇列表内帖子，删除后重新查询核验。；使用本地明确指定的目标执行助力点赞或邀请绑定，不读取远程默认助力配置。；逐行多账号、失败隔离、完全断网预演、脱敏通知、编号阶段日志与唯一 TASK_SUMMARY 汇总。。
- `scripts/baiduwangpan_checkin.py`：每日百度网盘会员签到，明确验证积分或已完成状态；获取并提交每日会员成长问题答案；读取并报告脱敏用户名、会员等级、成长值和会员类型；逐行多账号独立处理与结构化 JSON 汇总；完全断网的配置预演；成功、部分失败、失败、配置错误和预演状态的青龙脱敏汇总通知。
- `scripts/bsly_draw.py`：百事乐元账号抽奖，显式开启后可按设置的上限连续执行；展示脱敏后的奖品名称和提示，并展示接口返回的非敏感官方账号身份；兼容原 bsly 变量及 token、User-Agent、账号备注字段，支持每行一个账号；完全断网预演、配置校验、账号独立处理和失败非零退出；分阶段日志、每账号和全任务统计、单行 TASK_SUMMARY 结构化摘要；实跑所有结果调用可用的青龙公共通知模块发送脱敏摘要；预演仅本地模拟通知。
- `scripts/bwcj.py`：读取并展示官方非秘密账号身份，禁止输出手机号和凭据。；读取积分流水获取签到用户 ID，支持同账号手动补充用户 ID 并核验一致性。；查询新版签到天数，使用上游签名算法执行新版签到并核验业务状态和奖励明细。；显式开启旧版签到后查询旧版活动及连续天数并执行旧版签到。；保留每天 9 点和 18 点定时及 bwcjCookie 变量名，换行多账号独立执行。；完全断网预演、脱敏分阶段日志、账号及任务统计、唯一 TASK_SUMMARY 结构化记录。；青龙通知发送脱敏总结，支持全局开关，通知失败不改变业务退出码。。
- `scripts/cdrail.py`：每日签到与积分增量展示；基于明确业务码确认签到成功或今日已签到；每行一个账号，支持 JSON、查询字符串及自定义请求头；签到前随机等待、账号间间隔及超时控制；完全断网预演、青龙脱敏通知及单行结构化汇总；展示接口返回的非敏感昵称、用户名、显示名或公开账号标识。
- `scripts/cfmoto_checkin.py`：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。
- `scripts/ddnsto.py`：申请 product_id=2 七天免费套餐并查询订单；把新套餐绑定到指定路由器；重新读取官方套餐并确认到期时间延长后才报告续费成功；识别本周免费套餐申请次数限制；只有现有套餐尚未过期才视为已完成；显示北京时间到期时间；官方返回非敏感昵称或用户名时原样显示；保留每天 09:30 的上游计划和 ddns_cookie、ddns_userid 单账号兼容参数；多账号按行独立执行，失败账号不阻断其他账号；任一失败整体非零退出；无网络预演、青龙脱敏汇总通知和带时间戳的分阶段日志；输出唯一 TASK_SUMMARY 单行 JSON 汇总。
- `scripts/durex.py`：查询并直接显示官方昵称与当前积分；每日签到；显式开启活动分享记录上报（不发布文本）；显式开启活动抽奖并验证奖品结果；每行一个账号、独立执行与失败退出；完全断网预演及本地通知预览；青龙脱敏通知、时间轴日志、账号统计与单行结构化汇总。
- `scripts/ikuuu_checkin.py`：使用邮箱和密码登录 ikuuu；执行每日签到并识别今日已签到；从成功消息中报告流量奖励；按每行一个邮箱|密码账号处理并输出脱敏结构化汇总；可选随机错峰执行；按青龙通知策略发送汇总；完全断网的配置预演。
- `scripts/kuaishou_reward_status.py`：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。
- `scripts/main.py`：抓取 Wallhaven 最新列表，默认保留第 1 至 5 页。；按上游 thumb-info 中的六位壁纸编号及 PNG 标记下载 JPG 或 PNG 原图。；按当天日期归档壁纸，校验图片格式；已有有效图片跳过，跨页重复去重。；支持显式设置保存目录和抓取页数；请求设定超时、响应类型与大小限制。；各页面及图片独立处理，任何失败使整体非零退出。；完全断网预演、分阶段时间轴日志与单行 TASK_SUMMARY 汇总。；通过青龙 notify.py 发送脱敏任务总结；支持全局通知开关，通知不可用保持业务退出码。。
- `scripts/nga_checkin.py`：NGA每日签到（重复签到按成功处理）；可选执行任务2、任务131和任务30计数；可选执行4次免广告视频及5次N币视频任务计数；可选记录5次分享事件并领取分享奖励；签到后查询账户资产响应是否有效；每行一个 UID|Token 账号的独立处理与失败汇总；执行前可选随机延迟；完全离线的配置预演；青龙脱敏汇总通知。
- `scripts/nodeseek_checkin.py`：NodeSeek 每日签到；已签到状态识别；近 N 天签到鸡腿收益统计；可选随机奖励模式与多账号错峰执行；多账号独立处理与脱敏汇总通知；断网预演配置验证。
- `scripts/passnat_checkin.py`：PassNAT 每日签到；今日已签到的幂等成功识别；查询并显示套餐、流量、隧道、状态和到期时间；显示最近登录地区、运营商和 IP；可选随机错峰执行；换行分隔的多账号独立处理；青龙脱敏汇总通知；完全断网预演。
- `scripts/quark_signin.py`：验证夸克账号 Cookie 并显示官方返回的昵称或公开身份；查询当日签到状态，识别今日已签到；领取每日存储空间奖励并展示奖励和连签进度；换行配置多账号，独立处理并汇总失败；可选随机延迟、请求超时、完全断网预演；脱敏时间轴日志、账号及任务统计、结构化汇总和青龙通知；失败时输出固定响应字段的类型及有限数字业务码，辅助定位问题且不输出原始响应。
- `scripts/sfsu_checkin.py`：验证顺丰速运登录会话；每日签到并识别已签到状态；查询积分、完成安全的积分任务并领取奖励；查询丰蜜、完成丰蜜任务、执行大冒险和容量扩充并领取奖励；经显式授权后领取生活特权券；每月 26 至 28 日执行会员日非消费任务、免费抽奖、红包合成和 8 级红包提取；支持多账号独立执行、完全断网预演、脱敏汇总和青龙通知。
- `scripts/smzdm_checkin.js`：校验账号的 sk 与 sess 配套凭据；执行什么值得买每日签到并识别今日已签到状态；查询签到奖励与连续签到状态；满足条件时领取连续签到额外奖励；查询并显示接口可取得的账号身份、等级、金币和碎银概览；统计当月经验变动；支持逐行多账号独立处理与失败汇总；提供完全断网的离线预演；输出时间轴日志、兼容结果记录和单行 TASK_SUMMARY JSON；按青龙通知策略发送脱敏汇总；展示签到天数、补签卡、普通奖励和礼包明细；查询值会员总经验、等级经验及有效期。
- `scripts/sudojia_33agilestudio.js`：邮箱密码登录并获取会话令牌；查询账户信息，显示返回的非敏感昵称、用户名、显示名称或公开 UID；每日签到获得积分；查询当前积分；按换行配置多账号，失败独立统计并非零退出；完全断网预演及配置校验；青龙脱敏通知、分阶段日志和单行结构化汇总。
- `scripts/sudojia_allgirls.js`：获取并显示官方昵称；查询每日签到状态，已签到时避免重复请求；未签到时执行签到并复查已签到状态；查询当前积分；支持逐行多账号、请求超时与账号独立失败统计；支持完全断网预演、青龙通知和单行结构化汇总。
- `scripts/sudojia_amx.js`：查询账号信息并显示接口返回的昵称，不输出手机号；查询今日签到状态，已签到则跳过重复签到；未签到时执行每日签到，并再次查询签到状态核验结果，显示可用的奖励积分；查询当前积分；按非空行支持多账号，逐账号统计，失败时非零退出；完全断网预演、阶段日志和单行 TASK_SUMMARY 结构化汇总；通过青龙 sendNotify.js 发送脱敏总结；支持全局开关、通知超时和失败隔离。
- `scripts/sudojia_bananavideo.js`：每日 01:10 执行登录、账号昵称查询、签到、广告任务、长视频下载任务登记、观看十个视频、二维码任务登记及金币查询。；显式启用后可添加五个随机视频收藏；移除上游清空全部收藏的危险行为。；显式启用后可发布评论：独立 HTTPS 一言文本提供方、作者与来源署名、空白规范化、二百八十字符上限及本地回退。；每行一账号、首个分隔符解析、会话隔离、有限重试、请求超时和严格业务成功校验。；完全断网预演、分阶段脱敏日志、账号与任务统计、单行 TASK_SUMMARY 及青龙通知。。
- `scripts/sudojia_beiyinmei.js`：验证登录状态并显示接口返回的昵称，不输出手机号或凭据。；每日执行贝因美小程序签到，仅业务码 0 判定签到成功，未知状态按失败处理。；支持每行一个账号，失败隔离和整体非零退出。；完全断网预演、分阶段耗时日志、账号及任务统计和单行结构化汇总。；实际运行通过青龙 sendNotify.js 发送脱敏结果通知，支持全局开关；预演仅输出通知模拟摘要。。
- `scripts/sudojia_botanystar.js`：使用手机号与密码的 MD5 值登录，独立保存各账号会话；每日签到并显示奖励和连续签到天数；完成类型 10 和 60 的浏览任务，两项请求之间等待 11 秒；查询当前绿星币余额；安全显示官方返回的非敏感昵称、显示名称或公开账号身份；每行一个账号，独立统计并汇总失败退出状态；完全断网预演、请求超时、响应大小限制及明确业务成功校验；青龙通知、带时间戳的分阶段日志和单行 TASK_SUMMARY 结构化汇总。
- `scripts/sudojia_bwtea.js`：登录状态校验及官方昵称显示；查询新版签到状态及连续签到天数，未签到时执行签到并复核状态；查询当前积分及即将到期的积分和日期；逐行多账号隔离执行与失败非零退出；完全断网预演、脱敏青龙通知及时间轴和结构化统计。
- `scripts/sudojia_colorful_mall.js`：根据原始登录请求体换取独立账号凭据并校验登录状态；显示官方返回的昵称，不输出手机号及凭据；查询旧版签到状态，未签到时执行旧版签到，并执行新版签到；查询连续签到天数和当前积分；显式开启后查询社区评论积分和热门文章，每次最多发表三条评论，当日积分达到九分时停止；评论优先使用 HTTPS 一言，解析正文、作者和来源并按要求署名；所有声明的请求或内容异常回退本地文本；每行一个账号，账号隔离，任一失败非零退出；完全断网预演、阶段日志、账号及任务统计、单行 TASK_SUMMARY 和青龙脱敏通知。
- `scripts/sudojia_flyant.js`：每日签到；查询连续签到天数；查询累计获得、使用及剩余环保豆；按账号真实步数兑换一次；显式启用抽奖并展示奖品，验证余额后执行；显式启用早起打卡与报名；多账号独立执行与失败退出码；断网预演、时间轴日志和结构化汇总；青龙脱敏通知；预演仅本地预览。
- `scripts/sudojia_fnnas.js`：读取并显示本站返回的账号昵称和公开 UID，抑制手机号及凭据输出；每日签到，识别明确的今日已签到状态；执行后重新读取页面验证结果；查询最近、本月、连续、累计打卡次数或时间、累计和最近奖励、当前打卡等级；查询积分、牛值、飞牛币和登录天数；每行一个账号，逐账号隔离异常并汇总退出状态；完全断网预演、分阶段日志、账号统计及单行 TASK_SUMMARY 结构化汇总；正式执行成功、部分失败、失败和配置错误均尝试发送青龙脱敏通知；预演生成摘要并记录不发送状态。
- `scripts/sudojia_hgf.js`：每日自动签到，显示接口返回的数字酒币奖励。；浏览小阿头条并领取任务奖励。；保留每天 05:33 的执行计划，签到日期按北京时间计算。；每行一个账号，逐账号隔离失败，提供超时和严格业务成功判断。；显示官方返回的非敏感账号身份；不输出凭据或接口原始响应。；支持完全断网预演、分阶段时间轴日志、账号及子任务统计和单行 TASK_SUMMARY 汇总。；通过青龙 sendNotify.js 发送脱敏通知，支持全局开关；预演通知禁止网络投递，通知失败不改变业务退出码。。
- `scripts/sudojia_hlzj_game.js`：独立完成请求签名和登录，显示官方返回的昵称及公开用户编号。；领取今日电力并显示明日奖励。；查询签到状态，未签到时执行签到，显示奖励和连续签到天数。；可选消耗游戏电力，支持轮次刷新、次数上限和完成后领取宝箱。；按行配置多账号，账号之间隔离，失败返回非零退出码。；完全断网预演、分阶段日志、账号及任务统计和单行机器可读汇总。；正式运行结束尝试青龙通知，支持全局关闭；预演仅展示通知摘要。。
- `scripts/sudojia_hzhfp.js`：获取并原样显示官方微信昵称，不输出手机号；每日签到并查询连续签到天数；查询当前积分；按行配置多账号并独立统计失败；断网演练、时间轴日志及单行结构化任务汇总；正式执行通过青龙发送脱敏通知，通知失败不改变业务退出码。
- `scripts/sudojia_instax.js`：查询官方昵称、公开 UID、当前积分和等级；每日签到（活动 25）；显式开启后查询抽奖机会并连续抽奖（活动 42），展示奖品结果；换行多账号隔离执行及逐账号统计；完全断网预演、脱敏青龙通知和单行结构化任务汇总。
- `scripts/sudojia_jhcard.js`：登录并展示官方返回的账号姓名，不展示手机号或凭据；每日签到；查询连续签到天数；查询当前积分；显式开启后执行五次随机帖子评论；公开评论优先使用一言文案及作者、出处署名，失败时采用本地文案；每行一个账号、独立处理、失败非零退出；完全断网预演、脱敏通知、时间轴日志及结构化汇总。
- `scripts/sudojia_jiangshan.js`：每日签到并查询连续签到天数；读取新闻并复查任务完成进度；可选分享任务上报、评论、点赞与本地服务任务上报；评论优先使用一言正文与作者出处署名，所有声明异常均回退本地文本；查询官方账号昵称、用户名、显示名或公开 UID 及当前积分；逐行多账号、独立失败统计、断网预演、脱敏青龙通知与结构化汇总。
- `scripts/sudojia_jindian.js`：查询并显示官方账号昵称等非秘密身份信息；检查每日签到状态，已签到时避免重复写入；执行每日签到，显示奖励并复查签到状态；查询当前积分，包括已经签到的账号；支持逐行配置多账号并隔离失败；支持断网预演、青龙脱敏通知和带时间戳的阶段日志、账号统计及单行结构化汇总。
- `scripts/sudojia_jlc.js`：查询并显示官方返回的公开账号身份；查询当日签到状态，已签到时不重复操作；执行每日签到并复查官方签到状态；显式授权后领取待选奖励，领取后最多重试签到一次；查询金豆余额；按行配置多账号并独立统计，失败时整体非零退出；完全断网预演、时间轴日志及单行结构化汇总；通过青龙发送脱敏任务通知，预演仅本地模拟通知。
- `scripts/sudojia_jlc_yj.js`：查询并显示官方返回的公开昵称；每日签到并检查官方 success 严格为 true；查询并校验当前积分；每行一个账号，独立处理与失败非零退出；完全离线预演，不调用业务接口和通知服务；请求超时、响应大小限制及脱敏错误处理；时间轴阶段日志、账号与任务统计及单行 TASK_SUMMARY 汇总；通过青龙 sendNotify.js 发送脱敏总结，支持全局开关并保留业务退出码。
- `scripts/sudojia_juejin.js`：检查登录和今日签到状态；显示官方返回的账号昵称；每日签到，已签到时不重复提交，重复签到业务码须经状态复核；查询矿石余额；统计连续和累计签到天数；换行多账号独立处理和失败退出；完全断网参数预演；青龙脱敏汇总通知和阶段日志、单行结构化统计。
- `scripts/sudojia_kozbs.js`：查询官方返回的公开昵称和当前积分。；检查今日签到状态，已签到时避免重复签到。；未签到时执行每日签到，以业务码 errno 严格等于数字 0 确认接口成功。；支持换行多账号、独立失败处理和整体失败退出码。；提供完全断网预演、阶段耗时、账号与任务统计以及单行结构化汇总。；正式执行后通过青龙发送脱敏汇总，支持全局关闭及通知失败不影响业务退出码。。
- `scripts/sudojia_ktgzs.js`：查询并显示官方返回的账号名称，不输出手机号；每日签到，显示签到奖励和连续签到天数；查询最近积分流水中的当前积分；每行一个账号，独立处理并汇总失败退出码；完全断网预演，校验账号配置并展示三个业务阶段；通过青龙通知模块发送脱敏任务总结，支持总开关和通知目录设置；带时间戳的阶段日志、账号统计、任务统计及单行 TASK_SUMMARY 结构化汇总。
- `scripts/sudojia_kukahome.js`：读取并显示官方返回的账号昵称，不输出手机号或原始响应；每日签到并校验业务状态与积分结果；查询连续签到天数与当前积分；逐行多账号独立执行及失败非零退出；完全断网预演、分阶段日志及单行结构化任务总结；青龙脱敏通知，通知异常不改变业务退出码。
- `scripts/sudojia_kuro.js`：检查 Token 与鸣潮角色，保留 H5 到 Android 的验证回退；社区每日签到并显示获得库洛币及连续签到天数；查询账户库洛币余额；鸣潮每日签到及当日奖励查询；查询战双绑定角色，有角色时每日签到并查询当日奖励；显示官方返回的非敏感账号身份；多账号独立处理、请求超时和严格业务结果检查；断网预演、分阶段日志、账号统计及结构化任务汇总；通过青龙通知模块发送脱敏汇总，通知失败保留业务退出码。
- `scripts/sudojia_laoban.js`：查询并显示官方账号昵称，不输出手机号或凭据；按中国标准时间检查每日签到状态，未签到时签到并复查；查询累计签到天数，领取可领取的连续签到积分奖励；执行商品与资讯各三次浏览，并复查积分任务完成状态；保留秒杀任务状态检查及上游停用提示，不调用未经验证的秒杀接口；同步并查询当前积分；每行多账号独立执行、超时及业务成功校验、失败非零退出；完全断网预演、时间轴日志、账号与任务统计、单行结构化汇总和青龙脱敏通知。
- `scripts/sudojia_longfor.js`：读取并显示官方昵称，隐藏手机号及凭据；每日签到并区分今日已签到；显式启用后抽奖签到、获取机会及执行一次抽奖、显示结果；支持多账号、完全离线预演、超时及业务成功校验；按账号分阶段日志、统计和单行结构化汇总；通过青龙通知模块发送脱敏汇总，通知失败不改变业务退出码。
- `scripts/sudojia_mallcoo.js`：查询并显示账号昵称；每日签到，识别今日已签到并复核新签到状态；查询当前积分余额；查询连续签到天数；查询过期积分提示；多账号逐行配置与独立失败处理；完全断网预演、脱敏日志及结构化汇总；通过青龙发送脱敏通知，通知失败不改变业务退出码。
- `scripts/sudojia_mawuwang.js`：校验登录凭据；读取官方返回的非敏感昵称或用户名以核对账号；每日查询签到状态，已签到时跳过重复提交，未签到时执行签到；查询当前积分、即将过期积分和过期时间；按行配置多账号，独立运行并汇总失败退出码；完全断网预演，验证参数并演示全部任务阶段；通过青龙发送脱敏结果通知，包含积分和签到结果；通知失败不改变业务退出码；时间轴日志、逐账号和总体统计及单行 TASK_SUMMARY 结构化汇总。
- `scripts/sudojia_midea.js`：查询账号登录信息与会员等级，显示接口提供的非敏感公开身份；每日签到并严格验证 errcode 为数字 0；查询当前积分和成长值；换行多账号、独立错误处理及整体失败退出码；完全断网预演、时间轴日志和单行 TASK_SUMMARY 统计；通过青龙 sendNotify.js 发送脱敏任务摘要，通知异常保留业务退出码。
- `scripts/sudojia_moto.js`：查询账号信息并显示官方昵称，刷新当前运行中的会话凭据；提交每日签到，严格根据签到接口数字业务码 0 确认成功；按明确要求暂停签到状态查询及二次核验；查询当前能量；每行一个账号，独立执行并汇总失败退出码；完全无网络预演，检查参数并展示流程；青龙脱敏通知、分阶段日志和单行 TASK_SUMMARY 统计；输出请求路径、HTTP 状态及脱敏业务码分类，区分网络、格式、凭据、重复签到提示和业务失败。
- `scripts/sudojia_mxbc.js`：验证小程序账号登录状态，显示官方返回的非敏感昵称、用户名、显示名称或公开 UID；不显示手机号。；每日签到并显示本次雪王币奖励和连续签到天数。；签到后查询当前雪王币余额；签到失败仍尝试查询，整体保持失败状态。；支持每行一个 Token 的多账号，账号之间独立处理。；支持完全断网预演，验证参数和三阶段执行流程。；自带 HTTPS 请求、RSA-SHA256 签名、统一请求与签名时间戳、15 秒总超时、响应大小限制和严格业务成功校验。；提供时间轴日志、阶段耗时、每账号及全任务统计，以及恰好一条 TASK_SUMMARY JSON。；正式运行在成功、部分失败、失败和配置错误后发送脱敏青龙通知，通知失败不改变业务退出码；离线预演输出脱敏通知摘要，不调用网络通知通道。。
- `scripts/sudojia_naixue.js`：校验账号登录状态，显示官方返回的非敏感昵称或用户标识。；查询签到状态和记录天数，已签到时跳过重复提交，未签到时执行每日签到并校验成功标志。；查询当前奈雪币余额。；支持逐行多账号、请求超时、业务失败退出及脱敏统计。；支持完全离线预演、青龙通知和单行 TASK_SUMMARY 汇总。。
- `scripts/sudojia_nestle.js`：查询官方用户信息并显示昵称等非敏感公开身份，不显示手机号或凭据。；查询任务列表并显示可用于授权的任务编号。；仅提交显式白名单中的任务，以接口 errcode=200 验证成功；默认仅查询。；查询当前巢币余额。；每天08:28运行，支持按行配置多个账号及逐账号失败隔离。；提供完全断网的模拟预演、带时间戳的分阶段日志和单行 TASK_SUMMARY 汇总。；正式运行后发送脱敏青龙通知，通知失败不改变业务退出码；预演仅展示通知摘要。。
- `scripts/sudojia_nfhk.js`：每日签到，识别今日已签到状态；查询中国时区当月签到进度；查询可用里程；每行一个账号，逐账号处理并统计失败；断网预演、分阶段日志、结构化总结和青龙脱敏通知；接口返回非敏感昵称、用户名、显示名称或公开用户标识时显示账号身份。
- `scripts/sudojia_opposhop.js`：从活动页面 DSL 自动发现签到和任务活动 ID；核验登录与会员信息，显示官方会员名称；每日签到并重新查询验证签到状态，识别今日已签到；查询连续签到天数；读取任务列表，按显式任务 ID 白名单完成任务并领奖，始终排除黑卡和购物类型；手动确认当月固定奖励 ID 后可领取 3、5、10、15 天累计奖励；每行多账号独立执行，任一失败整体非零退出；无网络预演、分阶段日志、账号及任务统计、单行结构化总结、青龙通知。
- `scripts/sudojia_pangge.js`：校验登录状态并显示官方返回的非敏感昵称；查询签到状态、连续签到天数和累计签到天数；未签到时执行每日签到并再次查询确认，已签到时跳过；查询当前账号积分；支持换行多账号及独立失败统计；提供完全断网预演、分阶段日志及单行结构化汇总；通过青龙发送脱敏结果通知，支持全局关闭。
- `scripts/sudojia_paotea.js`：登录状态校验及官方返回的非敏感身份展示；每日签到及已签到识别，签到后复核状态；查询连续签到天数和下一阶段奖励，显示距离奖励的天数；查询当前积分、即将过期积分和失效时间；逐行多账号独立执行和失败退出；完全断网预演、分阶段脱敏日志和单行结构化总结；青龙通知及全局通知开关，通知异常不改变业务退出码。
- `scripts/sudojia_shmedia.js`：显示官方返回的昵称、用户名、显示名称或公开 UID，不输出手机号或凭据；查询任务列表，签到、阅读和视频积分任务，检查操作后任务进度；可选收藏、公开评论和分享积分任务，默认关闭；保留上游跳过任务 004 的行为；评论优先请求一言，按作者及出处署名；所有声明的服务失败情形回退本地文本，预演不请求服务；查询当前积分及限时、虚拟两类可兑换商品，不自动兑换；每行一个账号、独立错误处理、超时及响应大小限制、有限循环；完全断网预演、青龙脱敏通知、时间轴日志、每账号统计和单行结构化汇总。
- `scripts/sudojia_shuifei.js`：查询官方昵称与剩余签到次数，隐藏手机号及凭据；按剩余次数签到，已签到时跳过并保留连续签到天数展示；查询当前积分；支持每行一个账号独立执行和失败退出码；提供完全断网预演、分阶段日志与结构化汇总；通过青龙通知模块发送脱敏汇总，通知不可用不改变业务退出码。
- `scripts/sudojia_sspanel.js`：通过邮箱和密码登录各账号的 SSPANEL 站点；每日签到并严格验证登录和签到业务成功码；展示接口提供的总套餐、已用流量及剩余流量；展示接口提供的非敏感账号身份；逐行多账号、独立会话及失败汇总；断网演练、阶段日志、结构化汇总及青龙脱敏通知。
- `scripts/sudojia_starmom.js`：每日签到及签到积分校验；浏览主会场、热销爆品、优惠券、视频和粮油专场并领取任务积分；显示官方昵称、等级和积分；换行多账号及独立失败处理；断网预演、分阶段日志和结构化任务汇总；青龙脱敏通知与全局开关。
- `scripts/sudojia_tebu.js`：查询并显示官方返回的非敏感账号身份；为每个账号独立发现签到活动；每日签到并显示获得积分；查询当前积分；支持换行多账号、独立失败处理和非零失败退出码；支持完全断网预演、分阶段日志与单行结构化汇总；通过青龙发送脱敏汇总，通知不可用时保留业务退出码。
- `scripts/sudojia_tilta.js`：获取官方昵称用于账号核对，抑制凭据及手机号输出；每日签到并复查今日日历状态；可选社区文章点赞，默认关闭；浏览两件商品及查询对应商品活动信息；提交社区、新闻中心、配件研究所三类阅读任务，保留阅读等待时间；复查任务完成状态并查询当前积分；排除订单评价，未知任务不自动执行且标记失败；支持每行一个账号及完全断网预演；分阶段脱敏日志、账号统计、单行结构化汇总和青龙通知。
- `scripts/sudojia_tuchong.js`：手机号密码登录，沿用上游 AES-128-ECB 手机号加密与请求头。；查询并展示官方昵称及公开 UID。；每日签到获取积分。；查询当前积分与等级。；每行一个账号，账号独立处理，任一失败整体非零退出。；完全断网预演与配置格式校验。；限时请求、响应大小限制、业务结果校验和脱敏日志。；正式运行通过青龙发送脱敏通知；通知失败不改变业务退出码；断网预演仅生成本地通知摘要。；带时间戳的分阶段结果、每账号及总体统计，输出唯一单行 TASK_SUMMARY。。
- `scripts/sudojia_v2ex.js`：校验登录状态并显示页面返回的公开用户名；领取每日登录奖励，识别当天已领取状态；展示页面提供的连续登录天数；查询金币、银币、铜币余额，无法解析时明确失败；每天 09:00 执行，支持逐行多账号和单账号失败隔离；完全断网预演，包含通知模拟；青龙脱敏汇总通知，可全局关闭；通知失败保留业务退出码；带时间戳和阶段耗时的日志、账号统计与单行 TASK_SUMMARY 汇总。
- `scripts/sudojia_wnna.js`：查询上海时区当日签到状态，仅在明确未签到时提交签到；展示连续签到天数，已签到账号不重复提交；查询并展示官方昵称、等级和当前积分；换行多账号独立执行，失败闭合并汇总退出状态；完全断网预演、分阶段脱敏日志和单行结构化任务汇总；青龙通知摘要，通知不可用不改变业务退出码。
- `scripts/sudojia_xhn.js`：使用抓包表单登录并检查授权令牌；每日签到并核验业务成功码；查询当前可用积分并验证响应字段；逐行多账号独立执行，任一失败整体非零退出；完全断网预演及参数检查；带时间戳的分阶段日志、账号统计和单行结构化总结；通过青龙发送脱敏汇总；预演只输出通知摘要，不联网；显示官方返回的非敏感昵称、显示名或公开账号身份。
- `scripts/sudojia_xiangwan.js`：每日登录并签到，显示本次签到玩豆奖励；查询当前玩豆余额，显示官方返回的昵称；可选受限权限 Token 缓存、有效性验证与密码登录回退；每行一个账号，逐账号隔离处理及失败退出；完全断网参数与流程预演；青龙脱敏通知、分阶段日志及单行结构化任务汇总。
- `scripts/sudojia_xiaomi_community.js`：查询并展示官方返回的公开用户名和用户编号，抑制敏感字段；每天执行微信小程序签到，展示接口确认的增加积分；查询成长值明细并按上游规则汇总展示当前成长值；支持每行一个账号、账号独立处理、失败非零退出；支持无网络预演、分阶段日志、账号统计和单行结构化汇总；通过青龙通知模块发送脱敏结果，通知失败保留业务退出码；失败时输出有限数字业务码、固定错误分类和响应类型，帮助脱敏诊断且不放宽成功条件。
- `scripts/sudojia_xinxi.js`：查询官方昵称并原样显示非凭据身份，查询执行前后喜点；每日签到并显示奖励与连续签到天数，识别今日已签到；显式启用后查询免费次数并最多执行一次免费抽奖，禁止积分抽奖；显式启用分享任务及商城浏览奖励，各最多两次，浏览提交前等待三十秒；逐行多账号独立处理、请求超时、业务状态和响应字段校验；完全断网预演、青龙脱敏通知、分阶段日志及单行结构化汇总。
- `scripts/sudojia_xpfarm.js`：获取官方账号昵称并展示以核对账号；每日签到，已签到时跳过；按显式配置的任务编号完成任务并领取奖励；查询当前积分；按显式配置的次数上限施肥和浇水；查询种树类型、成长进度、水滴和肥力；换行多账号独立处理与失败退出码；完全断网预演、分阶段日志、结构化统计和青龙脱敏通知。
- `scripts/sudojia_znds.js`：验证登录状态并显示官方公开 UID；每日签到并区分签到成功和今日已完成；显式配置后访问指定用户空间；查询积分、威望、金币及Z币，要求四项均可解析；逐行多账号独立运行并汇总失败退出码；完全断网预演与通知模拟；青龙脱敏通知、分阶段耗时与单行结构化汇总。
- `scripts/sudojia_zxice.js`：校验账号登录状态并展示官方返回的非敏感昵称；查询今日签到状态，已签到时避免重复操作；每日签到并展示接口确认的奶滴奖励；查询当前奶滴值；支持每行一个账号，独立处理并汇总失败退出码；完全断网预演、分阶段时间轴日志、账号统计和单行 TASK_SUMMARY 汇总；通过青龙 sendNotify.js 发送脱敏结果通知，支持全局开关；完全断网预演生成本地通知摘要。
- `scripts/tieba_checkin.py`：验证百度贴吧登录状态并获取签到所需的 TBS；显示登录接口可取得的账号昵称、用户名或公开 UID，方便核对账号；读取账号关注的贴吧列表并识别当日已签到项目；为尚未签到的关注贴吧执行每日签到；支持每行一个账号的多账号独立处理和统一脱敏通知；提供完全断网、不会产生账号副作用的配置预演；输出逐阶段时间轴、账号统计和单行结构化任务汇总。
- `scripts/tsthb_checkin.py`：从官方活动列表查询当前签到活动，优先每日签到入口；校验账号并展示官方返回的非敏感身份，隐藏手机号；每日签到并展示奖励名称或积分；每行一个账号，账号独立执行与失败汇总；可配置的随机延迟及倒计时，保留每天 09:55 调度；完整断网预演、分阶段日志、任务统计及单行结构化汇总；青龙脱敏通知及全局开关，通知失败保留业务退出码；每次 HTTP 请求设置 20 秒整体等待时限，覆盖域名解析和慢速响应；签到不自动重试。
- `scripts/ty_netdisk_checkin.py`：使用官方密码登录流程和 RSA 加密建立独立账号 Cookie 会话；每日签到、区分新签到和今日已签到、显示奖励空间并严格校验业务结果；每行配套凭据、多账号独立执行、任一失败整体非零退出；保留每日16:01计划、可配置随机延迟及账号间10～30秒随机间隔；显示官方非敏感昵称或公开身份，抑制手机号、凭据、会话及原始响应；青龙任务汇总通知、时间轴日志、阶段耗时、账号统计及单行 TASK_SUMMARY 记录；完全断网预演、凭据格式检查及旧环境变量迁移提示；兼容密码页字段属性顺序、已抵达密码页的重定向和上游 callbackMsg JSONP 登录响应；脱敏诊断 HTTP 状态、短数字业务码、固定协议字段类型、HTML 或空正文；账号结果及通知保留失败阶段；每账号 HTTP 总时限覆盖域名解析和响应读取；请求开始和耗时日志；无自动重试；Python 3.9+ 标准库自实现 HTTP、Cookie 与 RSA 公钥加密，限制响应大小及官方 HTTPS 重定向；区分域名解析失败、网络连接失败、TLS 验证失败和超时。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

### 必选参数（优先配置）

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="1"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_REFRESH_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个刷新令牌，空行会被忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/atxyq.py</code></td><td><code>atxyqs</code></td><td>是</td><td>格式：每个非空行一个账号：Authorization#Uid；仅在第一个 # 拆分，后续文本原样保留；Uid 为数字。旧版 @ 账号分隔必须改为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDU_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bsly_draw.py</code></td><td><code>bsly</code></td><td>是</td><td>格式：每个非空行一个账号：token#User-Agent#账号备注。先按第一个 # 拆出 token，再按最后一个 # 拆出备注；User-Agent 内的 # 保留，备注不可包含 #。不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bwcj.py</code></td><td><code>bwcjCookie</code></td><td>是</td><td>格式：每个非空行一个 Token，或 Token|customerId；仅在首个 | 分割。同账号配套字段，账号仅用换行分隔，不支持原 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cdrail.py</code></td><td><code>CDRAIL_DATA</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象或 URL 编码查询字符串；必填 token、app-token，Cookie 和设备请求头按本人抓包提供。支持 appToken/app_token 及 device-id/device_id 别名和其他自定义请求头；传输控制头忽略。查询字符串用 &amp; 分字段，各字段仅在第一个 = 处分割，值中的 &amp; 编码为 %26；推荐 JSON 保留复杂凭据。不得以 @ 或 &amp; 分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_COOKIE</code></td><td>是</td><td>格式：ticket=&lt;value&gt; 或裸 ticket；多账号每行一个；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ddnsto.py</code></td><td><code>DDNSTO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行填写 路由器ID|完整Cookie；仅在首个 | 分隔，同一行内 Cookie 原样保留，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/durex.py</code></td><td><code>dlshyzx</code></td><td>是</td><td>格式：每个非空行一个完整令牌；保留变量名；不再使用上游的 # 或其他符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ikuuu_checkin.py</code></td><td><code>IKUUU_ACCOUNT</code></td><td>是</td><td>格式：每行一个账号：邮箱|密码；只用第一个竖线分隔，密码中的后续竖线会保留；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_COOKIE</code></td><td>是</td><td>格式：每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 &amp; 或 @ 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/main.py</code></td><td><code>WALLHAVEN_SAVE_DIR</code></td><td>否</td><td>格式：绝对目录路径；自动追加当天日期子目录。预演可使用 /tmp/wallhaven-dry-run-placeholder。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nga_checkin.py</code></td><td><code>NGA_ACCOUNT</code></td><td>是</td><td>格式：每行一个账号：access_uid|access_token；只用第一个竖线分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nodeseek_checkin.py</code></td><td><code>NODESEEK_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行，每行为完整 Cookie 请求头值；Cookie 内的 &amp; 和 @ 保持原样；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/passnat_checkin.py</code></td><td><code>PASSNAT_SK</code></td><td>是</td><td>格式：每个非空行是一个账号的完整 Authorization 值；仅以换行分隔账号，不使用其他分隔符。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/quark_signin.py</code></td><td><code>QUARK_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留分号及等号，不使用 &amp;、&amp;&amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sfsu_checkin.py</code></td><td><code>sfsyUrl</code></td><td>是</td><td>格式：每个非空行一个完整的 URL 编码登录/分享 URL；整行作为同一账号凭据，不使用 &amp;、@ 等字符分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个账号，格式 sk|完整 Cookie；只在第一个 | 处分割，保留后续 Cookie 文本。不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_33agilestudio.js</code></td><td><code>AGILE_STUDIO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个邮箱#密码，只按第一个 # 分隔，密码中的后续 #、&amp; 和 @ 均保留；禁止使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_allgirls.js</code></td><td><code>ALL_GIRLS_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的 AccessToken；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_amx.js</code></td><td><code>AMX_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 Token；不使用 &amp; 或 @ 分隔账号，行内字符保持不变，首尾空白忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_bananavideo.js</code></td><td><code>BANANA_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个账号：手机号#密码；仅按第一个 # 分割，密码中的后续 #、&amp;、@ 原样保留；手机号为十一位数字。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_beiyinmei.js</code></td><td><code>BYM_ACCOUNT</code></td><td>是</td><td>格式：每个非空行填写 SID|access_token，仅按第一个竖线拆分，其后文本完整保留；不要使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_botanystar.js</code></td><td><code>BOTANY_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个手机号#密码，仅按第一个 # 分隔，密码中的后续 # 和 &amp; 原样保留；行首尾空白会去除。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_bwtea.js</code></td><td><code>BW_TEA_TOKEN</code></td><td>是</td><td>格式：每个非空行填写 token#id，仅首个 # 分隔配套凭据，后续内容原样保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_colorful_mall.js</code></td><td><code>COLORFUL_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 JSON 对象；OpenId、Iv、EncryptedData 均为非空字符串；不得用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_flyant.js</code></td><td><code>FLY_ANT_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号：Token 或 Token|真实步数；仅按第一个竖线拆分，不支持 &amp; 分隔账号。步数为正整数，每次执行仅兑换一次，避免当天重复运行兑换。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_fnnas.js</code></td><td><code>FN_NAS_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Cookie；同账号字段用分号保留，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_hgf.js</code></td><td><code>HGF_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的 sessionid；仅按换行分隔，不使用 &amp; 或 @；空行忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_hlzj_game.js</code></td><td><code>HLZJ_UNID</code></td><td>是</td><td>格式：每个非空行填写一个账号的 union_id；不使用 &amp;、@ 或空格分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_hzhfp.js</code></td><td><code>HZHFP_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整令牌，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_instax.js</code></td><td><code>INSTAX_TOKEN</code></td><td>是</td><td>格式：每个非空行一个令牌；不以 &amp; 或 @ 分隔账号。兼容令牌后附 #false 禁止该账号抽奖；仅在第一个 # 处分割，其余内容完整校验。旧 #true 不再默认开启抽奖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_jhcard.js</code></td><td><code>JHCARD_BODY</code></td><td>是</td><td>格式：每个非空行一个完整 JSON，必需 phone、password、sendMessageKey、deviceType、appType、sign；行末可追加 #true 开启五次公开评论，#false 或省略均关闭。JSON 内的分隔字符原样保留，不使用 &amp; 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_jiangshan.js</code></td><td><code>JIANG_SHAN_SESSION</code></td><td>是</td><td>格式：每行一个账号的会话值，仅以换行分隔；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_jindian.js</code></td><td><code>JINDIAN_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的 access-token，不含请求头名称；不使用 &amp;、@ 等符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_jlc.js</code></td><td><code>JLC_TOKEN</code></td><td>是</td><td>格式：每行一个账号：x-jlc-accesstoken值#secretkey值；仅以首个 # 分割，其后的 # 保留；不支持用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_jlc_yj.js</code></td><td><code>JLC_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Cookie，保留分号及值中的 &amp;、@ 等字符，不添加 export 或包裹引号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_juejin.js</code></td><td><code>JUEJIN_COOKIE</code></td><td>是</td><td>格式：每行 sessionid#原始查询串；仅以首个 # 分隔，查询串中的 &amp; 保留；可包含 aid=2608。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_kozbs.js</code></td><td><code>KOZBS_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整令牌；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_ktgzs.js</code></td><td><code>KTGZS_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的 Authorization 完整值；保留值内字符，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/sudojia_kukahome.js</code></td><td><code>GU_HOME_TOKEN</code></td><td>是</td><td>格式：每行 AccessToken#X-Customer，仅在首个 # 处分割，后续字符原样保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>GU_HOME_APP_SECRET</code></td><td>是</td><td>格式：应用签名密钥原文。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_kuro.js</code></td><td><code>KURO_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Token；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_laoban.js</code></td><td><code>LAOBAN_OPENID</code></td><td>是</td><td>格式：每行一个账号的 openid，仅填写字段值，不带引号或请求正文；不使用 &amp; 或 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_longfor.js</code></td><td><code>LONG_FOR_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号凭据，不使用 &amp; 或 @ 分隔；同一值发送为 lmToken 与 X-LF-UserToken。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_mallcoo.js</code></td><td><code>MALLCOO_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 Token，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_mawuwang.js</code></td><td><code>MAWUW_TOKEN</code></td><td>是</td><td>格式：每个非空行填写 token#id，仅在第一个 # 分割；其后内容完整保留，不以 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_midea.js</code></td><td><code>MIDEA_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留 Cookie 内的分号、等号和 &amp;，不按 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_moto.js</code></td><td><code>MOTO_TOKEN</code></td><td>是</td><td>格式：每个非空行填写 token#uid，仅按第一个 # 分隔；uid 为数字，不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/sudojia_mxbc.js</code></td><td><code>MXBC_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 Access-Token；去除行首尾空白，不使用 &amp;、@ 或其他符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MXBC_SIGNING_KEY</code></td><td>是</td><td>格式：完整 RSA 私钥 PEM 文本（保留实际换行和 BEGIN/END 标记），或完整 PEM 文本的 Base64 编码；同一应用的账号共用此签名配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_naixue.js</code></td><td><code>NAIXUE_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的令牌，不使用 &amp; 或 @ 分隔，不包含 Bearer 前缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_nestle.js</code></td><td><code>NESTLE_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的 Token，也兼容带 Bearer 前缀的值；不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_nfhk.js</code></td><td><code>NFHK_COOKIE</code></td><td>是</td><td>格式：仅填写字段值，不带 sign_user_token=；每个非空行一个账号，不使用 &amp; 或 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_opposhop.js</code></td><td><code>OPPOSHOP_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：User-Agent|Cookie；仅按第一个竖线分割，后续 Cookie 原样保留；不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_pangge.js</code></td><td><code>PANG_GE_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 token，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_paotea.js</code></td><td><code>PAO_TEA_TOKEN</code></td><td>是</td><td>格式：每行一个账号，格式为 Token#活动ID，仅按第一个 # 分隔；活动ID为数字，不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_shmedia.js</code></td><td><code>SHYP_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整 token；仅换行分隔，不使用 &amp; 或 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_shuifei.js</code></td><td><code>SHUI_FEI_COOKIE</code></td><td>是</td><td>格式：每行 Cookie#memberId，仅在首个 # 处分割；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_sspanel.js</code></td><td><code>SITE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：HTTPS站点地址,邮箱:密码。仅在第一个逗号和之后的第一个冒号处分割，密码中的后续标点完整保留；不支持换行密码。禁止以 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_starmom.js</code></td><td><code>STAR_MOM_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 token，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_tebu.js</code></td><td><code>TEBU_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整 token，不使用 &amp;、@ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_tilta.js</code></td><td><code>TILTA_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整 authorization 值；不使用 &amp; 或 @ 分隔账号，无需添加额外前缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_tuchong.js</code></td><td><code>TUC_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：手机号#密码。仅在第一个 # 分割，其后密码原样保留，包括 #、&amp;、@；不支持用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_v2ex.js</code></td><td><code>V2EX_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留值中的 &amp;、@ 和分号，不用这些字符分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_wnna.js</code></td><td><code>WNNA_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的原始令牌，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xhn.js</code></td><td><code>XHN_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号的 URL 编码表单，包含 password、logintype、RegistrationID、appid、type、username；保留全部原始字段与编码，&amp; 仅分隔表单字段，不分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xiangwan.js</code></td><td><code>XWGAME_ACCOUNTS</code></td><td>是</td><td>格式：手机号#密码，每个非空行一个账号；仅在第一个 # 处分割，后续密码字符完整保留。不再使用 &amp; 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xiaomi_community.js</code></td><td><code>XIAOMI_COMM_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；字段以分号分隔，字段值按第一个等号之后的全部内容保留；不按 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xinxi.js</code></td><td><code>XINXI_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个完整 sso 值；不添加变量名或引号，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xpfarm.js</code></td><td><code>XPFARM_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整 authorization 值；仅按换行分隔，不使用 &amp; 或 @ 分隔账号，不添加变量赋值语句。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_znds.js</code></td><td><code>ZNDS_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Cookie，保留分号、等号与 &amp;；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_zxice.js</code></td><td><code>ZX_ICE_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的 access-token 原值；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tieba_checkin.py</code></td><td><code>TIEBA_COOKIE</code></td><td>是</td><td>格式：每个账号占一个非空行；单行填写 BDUSS 值，或填写形如 BDUSS=&lt;值&gt;; STOKEN=&lt;值&gt; 的完整 Cookie。同一账号的 Cookie 字段保留在同一行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tsthb_checkin.py</code></td><td><code>tsthbck</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 &amp; 或 @ 分隔账号，字段内部字符保持原样。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ty_netdisk_checkin.py</code></td><td><code>TY_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，格式：用户名|密码；仅在第一个 | 分割，后续密码原样保留；账号之间只能换行；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

### 可选参数

不需要自定义行为时可以不配置；有默认值的参数会自动使用默认值。

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="6"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_DRIVE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes 或 on 表示启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_MAX_DELAY_SECONDS</code></td><td>否</td><td>格式：非负整数秒数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_PERSIST_ROTATED_TOKENS</code></td><td>否</td><td>格式：1、true、yes 或 on 表示启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_TOKEN_OUTPUT_FILE</code></td><td>否</td><td>格式：本地绝对文件路径；文件以 0600 权限原子替换，每行一个令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="12"><code>scripts/atxyq.py</code></td><td><code>ATXYQ_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1 开启，模拟所有已启用动作与通知，不表示业务成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>atxyqDel</code></td><td>否</td><td>格式：整数，默认 0 不删除；非零删除本人最近十篇列表内帖子。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_LIKE</code></td><td>否</td><td>格式：默认 0；1 对最多两篇文章各点赞后取消点赞，保持上游成对动作。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_POST</code></td><td>否</td><td>格式：默认 0；1 发布一篇动态，优先一言并保留作者来源署名，失败回退本地正文。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_LOCAL_TEXT</code></td><td>否</td><td>格式：可选，空白折叠后 1 至 280 字；默认本地校园正文。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_IMAGE_NAME</code></td><td>否</td><td>格式：可选图片文件名，必须与 ATXYQ_IMAGE_DIR 同时填写；不会上传或自动生成图片。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_IMAGE_DIR</code></td><td>否</td><td>格式：可选图片服务目录，与 ATXYQ_IMAGE_NAME 配套；启用发帖时登记已有图片。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_HELP_LIKE</code></td><td>否</td><td>格式：默认 0；1 为指定帖子点赞一次，不读取远程助力名单。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_INVITE</code></td><td>否</td><td>格式：默认 0；1 创建 ATXYQ_ASSIST 指定邀请关系，未知业务响应按失败处理。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ATXYQ_ASSIST</code></td><td>否</td><td>格式：可选 JSON 对象，含 topicId、text、userId、schoolId；三个编号为数字，text 为目标帖原正文；开启助力或邀请时必填。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用；其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDUWANGPAN_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BAIDUWANGPAN_DELAY_MAX</code></td><td>否</td><td>格式：非负整数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：1/0 或常见布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/bsly_draw.py</code></td><td><code>BSLY_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，其他值为实跑，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BSLY_ENABLE_DRAW</code></td><td>否</td><td>格式：仅 1 允许实跑抽奖，默认 0；未开启的实跑以配置错误非零退出。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BSLY_MAX_DRAWS</code></td><td>否</td><td>格式：1 至 100 的整数，每账号请求次数上限，默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；预演仅本地模拟通知，保证断网。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选的本地目录；通知不可用不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/bwcj.py</code></td><td><code>BWCJ_TASKS</code></td><td>否</td><td>格式：new、old 或 new,old；默认 new。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_ACTIVITY_ID</code></td><td>否</td><td>格式：数字字符串，默认 947079313798000641。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_STORE_ID</code></td><td>否</td><td>格式：正整数，默认 49006。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启完全断网预演，默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/cdrail.py</code></td><td><code>CDRAIL_DRY_RUN</code></td><td>否</td><td>格式：默认0；1、true、yes、on启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIMEOUT</code></td><td>否</td><td>格式：1至120的整数秒，默认15；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：默认true；仅true启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0至86400的整数秒，默认3600；预演不等待；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭；预演只生成本地通知摘要以保证断网；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知不可用或失败不改变业务退出码；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_ACTIVITY_COUNT</code></td><td>否</td><td>默认 3；范围 0-3；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_ACTION_DELAY</code></td><td>否</td><td>默认 2；范围 0-30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_POST_CONTENTS</code></td><td>否</td><td>格式：多条内容用换行或 | 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_RANDOM_DELAY_MAX</code></td><td>否</td><td>默认 0；范围 0-3600；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_USER_AGENT</code></td><td>否</td><td>多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_DRY_RUN</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/ddnsto.py</code></td><td><code>ddns_userid</code></td><td>是</td><td>格式：单个路由器ID，仅字母、数字、下划线或连字符；不接受多行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ddns_cookie</code></td><td>是</td><td>格式：单行完整 Cookie，含唯一且非空的 csrftoken；末尾不必带分号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DDNSTO_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演，0 执行真实续费；默认 0；也支持 true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。预演尝试通知时封锁网络，因此远程通知不会送达。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：已有通知模块目录的路径，不执行下载或安装。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/durex.py</code></td><td><code>DUREX_DRY_RUN</code></td><td>否</td><td>格式：1 开启断网预演，0 正式执行；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_SHARE</code></td><td>否</td><td>格式：1 开启分享记录上报，0 关闭；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_SHARE_ACT_ID</code></td><td>否</td><td>格式：数字活动编号；默认沿用上游 343766308960192；仅开启分享时使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_DRAW</code></td><td>否</td><td>格式：1 开启抽奖，0 关闭；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>dlshyzx_drawid</code></td><td>否</td><td>格式：数字活动编号；所有账号参与同一活动；仅 DUREX_DRAW=1 时必填。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；断网预演仅生成本地通知预览。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；否则查找可导入的 notify 和 /ql/data/scripts、/ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/ikuuu_checkin.py</code></td><td><code>IKUUU_MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 到 3600 的整数秒，默认 0（不延迟）。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的绝对目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/main.py</code></td><td><code>WALLHAVEN_PAGES</code></td><td>否</td><td>格式：1 至 100 的整数，默认 5。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WALLHAVEN_DRY_RUN</code></td><td>否</td><td>格式：0、false、no、off 表示正式运行；其他值表示断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。断网预演仅生成通知摘要，不调用通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="12"><code>scripts/nga_checkin.py</code></td><td><code>NGA_UA</code></td><td>否</td><td>格式：单行 User-Agent，默认 Nga_Official/90409；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_DAILY_MISSIONS</code></td><td>否</td><td>格式：布尔值，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_VIDEO_MISSIONS</code></td><td>否</td><td>格式：布尔值，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_SHARE_MISSIONS</code></td><td>否</td><td>格式：布尔值，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_QUERY_STATS</code></td><td>否</td><td>格式：布尔值，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_RANDOM_DELAY_MAX</code></td><td>否</td><td>格式：0至21600，默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ACTION_DELAY_SECONDS</code></td><td>否</td><td>格式：0至30，默认1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_VIDEO_DELAY_SECONDS</code></td><td>否</td><td>格式：0至120，默认30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_HTTP_TIMEOUT</code></td><td>否</td><td>格式：3至60，默认20；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_DRY_RUN</code></td><td>否</td><td>格式：布尔值，默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：布尔值，默认1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/nodeseek_checkin.py</code></td><td><code>NODESEEK_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_RANDOM</code></td><td>否</td><td>格式：布尔值，默认 true；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：布尔值，默认 false；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0..86400 整数秒，默认 3600；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_STATS_DAYS</code></td><td>否</td><td>格式：1..365 整数天，默认 30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0/false/no/off 表示禁用，默认启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/passnat_checkin.py</code></td><td><code>PASSNAT_DRY_RUN</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数秒，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/quark_signin.py</code></td><td><code>QUARK_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QUARK_TIMEOUT_SECONDS</code></td><td>否</td><td>格式：3 至 60 的整数秒数，默认 15。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QUARK_RANDOM_DELAY_MAX_SECONDS</code></td><td>否</td><td>格式：0 至 3600 的整数秒数，默认 0；预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，无需安装或下载应用。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sfsu_checkin.py</code></td><td><code>SFSU_DRY_RUN</code></td><td>否</td><td>格式：布尔值；1 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_AUTO_COUPON</code></td><td>否</td><td>格式：布尔值；1 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_RANDOM_DELAY_MAX</code></td><td>否</td><td>格式：0 至 86400 的整数秒数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：布尔开关，默认启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_USER_AGENT_APP</code></td><td>否</td><td>格式：单行客户端 User-Agent；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用离线预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知组件目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_33agilestudio.js</code></td><td><code>AGILE_STUDIO_DRY_RUN</code></td><td>否</td><td>格式：1 为断网预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；预演始终只生成摘要，不联网投递。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径，仅用于可选通知，业务无此依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_allgirls.js</code></td><td><code>ALL_GIRLS_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_amx.js</code></td><td><code>AMX_DRY_RUN</code></td><td>否</td><td>格式：1 为预演；其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 禁用，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，不下载或安装通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_bananavideo.js</code></td><td><code>BANANA_DRY_RUN</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BANANA_FAVORITE</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BANANA_COMMENT</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_beiyinmei.js</code></td><td><code>BYM_DRY_RUN</code></td><td>否</td><td>格式：1 表示预演，其余值表示实际执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_botanystar.js</code></td><td><code>BOTANY_DRY_RUN</code></td><td>否</td><td>格式：1 表示预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_bwtea.js</code></td><td><code>BW_TEA_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；业务运行不依赖该目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_colorful_mall.js</code></td><td><code>COLORFUL_DRY_RUN</code></td><td>否</td><td>格式：1 开启；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>COLORFUL_COMMENT</code></td><td>否</td><td>格式：仅 1 开启；每账号每次最多三条，已达当日九分上限则停止。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>COLORFUL_COMMENT_TEXT</code></td><td>否</td><td>格式：合并空白并去除首尾空白后不超过 280 个字符；为空或超长则使用内置文本。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/sudojia_flyant.js</code></td><td><code>FLY_ANT_DRAW</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FLY_ANT_EARLY_SIGN</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FLY_ANT_BET</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FLY_ANT_DRY_RUN</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_fnnas.js</code></td><td><code>FN_NAS_DRY_RUN</code></td><td>否</td><td>格式：1 表示断网预演，其他值表示正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，不区分大小写；预演只生成摘要，不发送网络通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知，不参与业务请求。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_hgf.js</code></td><td><code>HGF_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径，可省略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_hlzj_game.js</code></td><td><code>HLZJ_DRY_RUN</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HLZJ_USE_POWER</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HLZJ_POWER_LIMIT</code></td><td>否</td><td>格式：1 至 100 的整数，默认 20；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，可不设置；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_hzhfp.js</code></td><td><code>HZHFP_DRY_RUN</code></td><td>否</td><td>格式：1 表示演练，其余值表示正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，忽略大小写；演练始终仅输出本地通知以保证断网。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块目录的绝对路径；不用于业务接口。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_instax.js</code></td><td><code>INSTAX_DRAW</code></td><td>否</td><td>格式：0（默认关闭）或 1（显式开启）；账号 #false 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>INSTAX_DRY_RUN</code></td><td>否</td><td>格式：0 或 1；1 时不请求业务接口或通知网络，仅打印脱敏通知预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径；非业务依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_jhcard.js</code></td><td><code>JHCARD_DRY_RUN</code></td><td>否</td><td>格式：1 开启，其余值正式运行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_jiangshan.js</code></td><td><code>JIANG_SHAN_ACTIONS</code></td><td>否</td><td>格式：逗号分隔动作：sign 签到、read 阅读、share 分享任务上报、comment 公开评论、like 点赞、local 本地服务任务上报。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JIANG_SHAN_COMMENT_TEXT</code></td><td>否</td><td>格式：合并空白后非空且不超过 280 个字符，不填写任何个人信息或凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JIANG_SHAN_DRY_RUN</code></td><td>否</td><td>格式：1 或 0；预演不调用业务或文本接口，通知调用禁止网络传输。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_jindian.js</code></td><td><code>JINDIAN_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于青龙通知集成；业务执行不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_jlc.js</code></td><td><code>JLC_CLAIM_REWARD</code></td><td>否</td><td>格式：0（默认）或 1（授权领取并最多再签到一次）；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，其余值为正式执行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录绝对路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_jlc_yj.js</code></td><td><code>JLC_YJ_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全离线预演；其他值正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；无需额外仓库，模块缺失不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_juejin.js</code></td><td><code>JUEJIN_DRY_RUN</code></td><td>否</td><td>格式：1 启用，其余值执行正式任务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录绝对路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_kozbs.js</code></td><td><code>KOZBS_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，其余值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，大小写不敏感；其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径，仅用于可选通知，不影响独立业务执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_ktgzs.js</code></td><td><code>KTGZS_DRY_RUN</code></td><td>否</td><td>格式：1 表示预演，其他值表示正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块的目录路径；仅通知使用，业务请求不依赖该模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_kukahome.js</code></td><td><code>GU_HOME_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，不区分大小写。预演只生成摘要，不联网发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录路径；不可用时记录通知失败并保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_kuro.js</code></td><td><code>KURO_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；业务请求不依赖通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_laoban.js</code></td><td><code>LAOBAN_DRY_RUN</code></td><td>否</td><td>格式：1 表示预演；未设置时正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 表示关闭，不区分大小写；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；仅用于可选通知，不参与业务请求。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/sudojia_longfor.js</code></td><td><code>LONG_FOR_DRY_RUN</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LONG_FOR_ENABLE_LOTTERY</code></td><td>否</td><td>格式：0 或 1，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LONG_FOR_SIGN_ACTIVITY</code></td><td>否</td><td>格式：数字字符串；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LONG_FOR_LOTTERY_ACTIVITY</code></td><td>否</td><td>格式：数字字符串；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_mallcoo.js</code></td><td><code>MALLCOO_DRY_RUN</code></td><td>否</td><td>格式：1 开启，其他值关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_mawuwang.js</code></td><td><code>MAWUW_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径，不包含文件名。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_midea.js</code></td><td><code>MIDEA_DRY_RUN</code></td><td>否</td><td>格式：1 为完全离线预演，其他值为正式执行；预演不验证 Cookie，不发送通知，仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；依次查找此目录、/ql/data/scripts、/ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_moto.js</code></td><td><code>MOTO_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全无网络预演，其他值表示正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，忽略大小写；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，仅用于可选通知，不是业务依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_mxbc.js</code></td><td><code>MXBC_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网预演；其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机可信通知模块目录的路径；业务执行不依赖该目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_naixue.js</code></td><td><code>NAIXUE_DRY_RUN</code></td><td>否</td><td>格式：1 开启，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，大小写不限。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_nestle.js</code></td><td><code>NESTLE_TASK_GUIDS</code></td><td>否</td><td>格式：每行一个任务编号，仅含英文字母、数字、下划线或连字符，最多128字符；白名单对所有账号生效，任一指定任务不在列表中则该账号失败。默认不提交任何任务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NESTLE_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网模拟；其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭通知；断网预演仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；仅通知使用，不作为业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_nfhk.js</code></td><td><code>NFHK_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网预演，其他值表示正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 表示关闭，忽略大小写；其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块目录绝对路径，非业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_opposhop.js</code></td><td><code>OPPOSHOP_TASK_IDS</code></td><td>否</td><td>格式：英文逗号分隔的数字任务 ID；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OPPOSHOP_CUMULATIVE_REWARDS</code></td><td>否</td><td>格式：0 或 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OPPOSHOP_DRY_RUN</code></td><td>否</td><td>格式：0 或 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_pangge.js</code></td><td><code>PANG_GE_DRY_RUN</code></td><td>否</td><td>格式：1 或 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_paotea.js</code></td><td><code>PAO_TEA_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；仅通知使用，业务不依赖该目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/sudojia_shmedia.js</code></td><td><code>SHYP_DRY_RUN</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_ENABLE_FAVOR</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_ENABLE_COMMENT</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_ENABLE_SHARE</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_COMMENT_TEXT</code></td><td>否</td><td>格式：压缩空白后 1 至 280 个字符；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_shuifei.js</code></td><td><code>SHUI_FEI_DRY_RUN</code></td><td>否</td><td>格式：1 表示预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_sspanel.js</code></td><td><code>SSPANEL_DRY_RUN</code></td><td>否</td><td>格式：1 为断网演练，其他值为正式执行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭（不区分大小写）；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知，不影响业务运行；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_starmom.js</code></td><td><code>STAR_MOM_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全断网预演；默认正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，仅用于可选通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_tebu.js</code></td><td><code>TEBU_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行；预演不签到，不加载通知模块，只生成通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块所在目录的绝对路径，仅通知使用，业务不依赖此文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_tilta.js</code></td><td><code>TILTA_ALLOW_LIKE</code></td><td>否</td><td>格式：0或1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TILTA_DRY_RUN</code></td><td>否</td><td>格式：0或1；预演包含通知模拟且完全不联网。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，仅用于可选通知；业务执行不依赖该文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_tuchong.js</code></td><td><code>TUC_DRY_RUN</code></td><td>否</td><td>格式：1 为预演；其他值或未设置为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，大小写不敏感；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知集成；业务请求无外部文件依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_v2ex.js</code></td><td><code>V2EX_DRY_RUN</code></td><td>否</td><td>格式：1 启用；其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；预演仅模拟通知，不发送网络请求。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；未设置时搜索 /ql/data/scripts 和 /ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_wnna.js</code></td><td><code>WNNA_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，可选。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_xhn.js</code></td><td><code>XHN_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知不可用不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_xiangwan.js</code></td><td><code>XWGAME_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，不登录、不签到、不读取或写入缓存、不调用通知模块；仅生成脱敏通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XWGAME_TOKEN_CACHE</code></td><td>否</td><td>格式：可选文件路径；新文件权限为 0600，以手机号摘要索引；拒绝不安全文件。缓存验证失败回退密码登录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余开启；预演只生成摘要，不发送网络通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；通知模块仅用于通知，业务请求由本脚本独立实现。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_xiaomi_community.js</code></td><td><code>XIAOMI_COMM_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sudojia_xinxi.js</code></td><td><code>XINXI_DRY_RUN</code></td><td>否</td><td>格式：0 或 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_FREE_DRAW</code></td><td>否</td><td>格式：0 或 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_REWARD_TASKS</code></td><td>否</td><td>格式：0 或 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他值开启；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，仅用于通知，业务逻辑无需此模块；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/sudojia_xpfarm.js</code></td><td><code>XPFARM_TASK_IDS</code></td><td>否</td><td>格式：1–16 的整数，英文逗号分隔；默认空，不自动执行或领取未知任务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XPFARM_FERTILIZER_LIMIT</code></td><td>否</td><td>格式：0–100 整数，默认 0；启用后可能立即消耗肥料。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XPFARM_WATER_LIMIT</code></td><td>否</td><td>格式：0–100 整数，默认 0；启用后可能立即消耗水滴和肥力。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XPFARM_DRY_RUN</code></td><td>否</td><td>格式：1 为断网预演，其他值为正式运行；预演不执行业务请求或外部通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 忽略大小写时关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，仅用于通知；模块缺失或失败不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sudojia_znds.js</code></td><td><code>ZNDS_VISIT_UID</code></td><td>否</td><td>格式：单个数字公开 UID，所有账号共用；访问可能产生足迹或奖励。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZNDS_DRY_RUN</code></td><td>否</td><td>格式：1 表示断网预演，通知仅模拟，不代表实际签到成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（不区分大小写）关闭，其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，仅用于通知，不是业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_zxice.js</code></td><td><code>ZX_ICE_DRY_RUN</code></td><td>否</td><td>格式：1 开启预演，其他值执行正式任务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；只用于通知，业务请求不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/tieba_checkin.py</code></td><td><code>TIE_BA_COOKIE</code></td><td>是</td><td>格式：每个账号占一个非空行；单行填写 BDUSS 值或包含 BDUSS 的完整 Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DRY_RUN</code></td><td>否</td><td>格式：启用值为 1、true、yes 或 on，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_VERBOSE</code></td><td>否</td><td>格式：启用值为 1、true、yes 或 on，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DELAY_MS</code></td><td>否</td><td>格式：整数毫秒，脚本会限制在 500 至 10000 之间，默认 1200。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no 或 off 表示关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，目录内应包含 notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/tsthb_checkin.py</code></td><td><code>TSTHB_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示启用。预演不执行等待、HTTP 或通知模块，仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：忽略大小写，只有 true 启用随机延迟，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数，单位秒；随机延迟开启时在 0 至该值之间随机选择并显示倒计时。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；不会下载安装通知组件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/ty_netdisk_checkin.py</code></td><td><code>TY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：true启用随机延迟；其他值关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0～86400的整数；账号间另外随机等待10～30秒；预演均不等待；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TY_ACCOUNT_TIMEOUT</code></td><td>否</td><td>格式：10～600的整数；单次请求另有15秒超时，不自动重试；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off关闭通知；其余启用；预演只生成摘要而不传输；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知目录路径；不可用或发送失败不改变业务退出码；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

- `scripts/aliyunpan_checkin.py`：ALIYUN_REFRESH_TOKEN 每个非空行填写一个账号；忽略空行并独立处理各账号。。
- `scripts/atxyq.py`：atxyqs 每个非空行一个账号，配套 Authorization 与 Uid 用第一个 # 拆分；后续字段不再次拆分。各账号独立执行，任一账号失败整体非零退出；不再使用 @ 分隔账号。。
- `scripts/baiduwangpan_checkin.py`：BAIDU_COOKIE 中每个非空行是一个独立账号；依次处理，任一账号失败时进程整体非零退出。。
- `scripts/bsly_draw.py`：每个非空行一个账号，账号独立处理；任一账号格式错误或执行失败时整体非零退出。。
- `scripts/bwcj.py`：每个非空行一个账号；同账号 Token 与可选 customerId 使用首个 | 分割。各账号独立处理，任一失败整体非零退出。。
- `scripts/cdrail.py`：每个非空行一个账号，同一账号的配套凭据集中在该行；各账号独立处理，任一账号失败整体非零退出。。
- `scripts/cfmoto_checkin.py`：CFMOTO_COOKIE 每行一个账号。
- `scripts/ddnsto.py`：每个非空行一个账号，使用 路由器ID|完整Cookie，仅按首个 | 拆分；各账号独立执行，任一账号失败整体非零退出。兼容旧变量仅支持单账号。。
- `scripts/durex.py`：每个非空行一个账号的 Access-Token；各账号独立处理；任何账号失败则整体非零退出。。
- `scripts/ikuuu_checkin.py`：IKUUU_ACCOUNT 每个非空行表示一个账号，行内格式为邮箱|密码；账号之间只使用换行。。
- `scripts/kuaishou_reward_status.py`：KUAISHOU_COOKIE 每个非空行对应一个账号；任一账号失败时任务整体非零退出。
- `scripts/nga_checkin.py`：NGA_ACCOUNT 每个非空行表示一个账号，行内格式为 access_uid|access_token；账号之间只使用换行。。
- `scripts/nodeseek_checkin.py`：NODESEEK_COOKIE 中每个非空行是一个独立账号；逐账号执行，任一失败时进程整体非零退出。
- `scripts/passnat_checkin.py`：PASSNAT_SK 中每个非空行对应一个账号；账号独立执行，任一账号失败时进程整体返回非零。。
- `scripts/quark_signin.py`：每个非空行一个账号，完整 Cookie 作为一个字段保留；账号独立执行，任一账号失败则进程非零退出。。
- `scripts/sfsu_checkin.py`：sfsyUrl 中每个非空行是一个独立账号的完整 URL；逐账号隔离处理，任一账号失败则进程非零退出。。
- `scripts/smzdm_checkin.js`：每个非空行一个账号；同账号 sk 和 Cookie 用首个 | 配对。逐账号独立执行，任意账号配置或业务失败时整体非零退出。。
- `scripts/sudojia_33agilestudio.js`：每个非空行一个邮箱#密码，仅第一个 # 为字段分隔符，各账号独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_allgirls.js`：每个非空行一个账号；按行独立处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_amx.js`：每个非空行一个账号的 access-token，按行独立处理；任一账号失败时整体非零退出。。
- `scripts/sudojia_bananavideo.js`：每个非空行一个账号；各账号独立登录，任一账号失败则整体非零退出。。
- `scripts/sudojia_beiyinmei.js`：每个非空行一个账号，以首个竖线组合 SID 与 access_token；账号独立执行，任一账号失败则整体非零退出。。
- `scripts/sudojia_botanystar.js`：每个非空行一个账号，格式为手机号#密码；仅在第一个 # 分割，账号分别处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_bwtea.js`：每个非空行一个账号，按首个 # 分割 token 与 user.id；各账号独立处理，任一失败整体非零退出。。
- `scripts/sudojia_colorful_mall.js`：每个非空行一个账号完整 JSON；同一账号凭据合并保存，账号之间独立处理，任一账号失败整体非零退出。。
- `scripts/sudojia_flyant.js`：每个非空行一个账号；Token 与该账号可选真实步数用首个竖线分隔。账号依次独立执行，任一账号失败则整体非零退出。。
- `scripts/sudojia_fnnas.js`：每行一个账号的完整 Cookie，忽略空行；各账号独立处理，任一失败则整体非零退出。。
- `scripts/sudojia_hgf.js`：每个非空行一个账号，独立执行签到及浏览领奖；任一账号任一步骤失败则整体非零退出。。
- `scripts/sudojia_hlzj_game.js`：每个非空行一个账号；独立登录、处理和统计，任一账号失败则整体非零退出。。
- `scripts/sudojia_hzhfp.js`：每个非空行填写一个账号令牌，按行独立执行；任一账号失败则进程非零退出。。
- `scripts/sudojia_instax.js`：每个非空行一个账号，独立处理；任一账号失败则进程非零退出。。
- `scripts/sudojia_jhcard.js`：每个非空行一个账号，登录 JSON 与该账号的可选评论开关放在同一行；账号独立执行，任一失败整体非零退出。。
- `scripts/sudojia_jiangshan.js`：每个非空行一个账号，逐个独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_jindian.js`：每个非空行一个账号，忽略空行，各账号独立处理；任一账号失败则整体非零退出。。
- `scripts/sudojia_jlc.js`：每个非空行一个账号，按首个 # 拆分同一账号的两项凭据；账号独立处理，任一账号失败时整体非零退出。。
- `scripts/sudojia_jlc_yj.js`：每个非空行一个账号的完整 Cookie，忽略空行；账号独立处理，任一失败整体非零退出。。
- `scripts/sudojia_juejin.js`：每个非空行对应一个账号，配套凭据以首个 # 分隔；逐账号独立处理，任一账号失败整体非零退出。。
- `scripts/sudojia_kozbs.js`：每个非空行一个账号，去掉行首尾空白；账号独立执行，任一账号失败则整体非零退出。。
- `scripts/sudojia_ktgzs.js`：每个非空行一个账号，各账号独立处理；任一账号失败，整体退出码非零。。
- `scripts/sudojia_kukahome.js`：每个非空行对应一个账号，按首个 # 分割同账号的两个请求头；各账号独立处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_kuro.js`：每个非空行一个账号，顺序独立执行；角色资料仅保存在所属账号内，任一账号失败则进程非零退出。。
- `scripts/sudojia_laoban.js`：每个非空行代表一个账号；逐个独立处理，任意账号失败时进程非零退出。。
- `scripts/sudojia_longfor.js`：LONG_FOR_TOKEN 每个非空行一个账号，逐个独立处理；任一账号失败则整体非零退出。。
- `scripts/sudojia_mallcoo.js`：每个非空行一个账号，账号独立处理；任一账号失败时整体非零退出。。
- `scripts/sudojia_mawuwang.js`：每个非空行一个账号，token 和 id 用第一个 # 连接；逐账号独立运行，任何账号失败时整体非零退出。。
- `scripts/sudojia_midea.js`：每个非空行一个账号，逐个独立处理；任一账号失败，进程非零退出。。
- `scripts/sudojia_moto.js`：每个非空行一个账号，token 和 uid 必须属于同一账号；仅按首个 # 分隔。独立处理各账号，任一账号失败则进程非零退出。。
- `scripts/sudojia_mxbc.js`：MXBC_TOKEN 每个非空行一个账号，逐个独立验证、签到和查询；任一账号失败则整体非零退出。签名私钥为应用公共配置，不使用符号拼接账号。。
- `scripts/sudojia_naixue.js`：每个非空行一个账号，独立处理；任一账号失败则进程非零退出。。
- `scripts/sudojia_nestle.js`：NESTLE_TOKEN 每个非空行一个账号，独立处理；任一账号失败时进程非零退出。。
- `scripts/sudojia_nfhk.js`：每个非空行填写一个账号的 token；逐个账号独立执行，任一账号失败则进程非零退出。。
- `scripts/sudojia_opposhop.js`：每行一个账号，格式为 User-Agent|Cookie；仅在第一个竖线处分割。同一账号配套凭据必须来自同一次登录。任一账号失败则进程非零退出。。
- `scripts/sudojia_pangge.js`：每个非空行一个账号，独立处理；任一账号失败，整体非零退出。。
- `scripts/sudojia_paotea.js`：每个非空行对应一个账号；每行独立配置 Token 和活动ID，账号独立处理，任一账号失败时进程非零退出。。
- `scripts/sudojia_shmedia.js`：SHYP_TOKEN 每个非空行一个账号；依次独立处理，任一账号失败则进程非零退出。。
- `scripts/sudojia_shuifei.js`：每个非空行一个账号，Cookie 与 memberId 使用首个 # 连接；逐账号执行，任一账号失败则整体非零退出。。
- `scripts/sudojia_sspanel.js`：每个非空行一个账号，各账号独立登录、签到和统计；任一账号失败则整体非零退出。。
- `scripts/sudojia_starmom.js`：每个非空行一个账号，独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_tebu.js`：每个非空行一个账号，顺序独立处理；任一账号失败整体非零退出。。
- `scripts/sudojia_tilta.js`：每行一个账号，忽略空行，各账号独立执行，任意账号失败时整体非零退出。。
- `scripts/sudojia_tuchong.js`：每个非空行一个账号，仅以第一个 # 分割手机号和密码；账号顺序执行，相互隔离，任一账号失败时整体非零退出。。
- `scripts/sudojia_v2ex.js`：每个非空行一个账号，逐个独立执行，任一账号失败则进程非零退出。。
- `scripts/sudojia_wnna.js`：每个非空行一个账号，逐账号独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_xhn.js`：每个非空行一个完整登录表单，忽略空行；账号独立处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_xiangwan.js`：每个非空行一个手机号#密码；首个 # 后均为密码，不以 & 或 @ 分隔账号。逐账号独立处理，任一账号失败整体非零退出。。
- `scripts/sudojia_xiaomi_community.js`：每个非空行一个账号，完整 Cookie 配套字段属于同一账号；独立执行，任一账号失败时整体非零退出。。
- `scripts/sudojia_xinxi.js`：XINXI_TOKEN 每个非空行一个账号，逐账号独立执行，任一账号失败则进程非零退出。。
- `scripts/sudojia_xpfarm.js`：每个非空行一个账号，顺序独立执行；任一账号失败时整体非零退出。。
- `scripts/sudojia_znds.js`：每个非空行一个账号，配套认证字段包含在同一完整 Cookie 中，不按 & 或 @ 拆分；账号独立执行，任一失败则整体非零退出。。
- `scripts/sudojia_zxice.js`：每行一个非空账号凭据，按顺序独立运行；任何账号失败均以非零状态退出。。
- `scripts/tieba_checkin.py`：每个非空行表示一个账号；同一账号的全部 Cookie 字段必须写在同一行，脚本不会使用 &、@ 等字符拆分账号。账号逐个独立处理，任一账号失败都会使进程以非零状态退出。。
- `scripts/tsthb_checkin.py`：每个非空行一个账号，按顺序独立执行；任一账号失败则整体非零退出。。
- `scripts/ty_netdisk_checkin.py`：每个非空行一个账号，用户名|密码仅切分第一个竖线；账号独立执行，任意账号失败则整体非零退出。。

## 参数获取方法

### 必选参数获取（重点）

#### `ALIYUN_REFRESH_TOKEN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：登录阿里云盘网页版，从本人已认证会话的浏览器存储中复制 refresh_token；切勿分享。
- 填写格式：`每个非空行填写一个刷新令牌，空行会被忽略。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `atxyqs`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：在微信艾特校园圈小程序登录后，抓取自己发往 api.atxz.cool 的请求头 Authorization 与 Uid；失效后重新登录抓取。
- 填写格式：`每个非空行一个账号：Authorization#Uid；仅在第一个 # 拆分，后续文本原样保留；Uid 为数字。旧版 @ 账号分隔必须改为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDU_COOKIE`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：登录 https://pan.baidu.com/ 后打开浏览器开发者工具的 Network 面板，刷新页面，选择一个 pan.baidu.com 请求，复制 Request Headers 中完整的 Cookie 值。
- 填写格式：`每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `bsly`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：在本人授权的微信小程序 wx1a72addb7ee74f67 中抓取抽奖请求，读取 token 与 User-Agent 请求头；账号备注自行填写，不应包含敏感信息。不要分享凭据。
- 填写格式：`每个非空行一个账号：token#User-Agent#账号备注。先按第一个 # 拆出 token，再按最后一个 # 拆出备注；User-Agent 内的 # 保留，备注不可包含 #。不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `bwcjCookie`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：在本人微信霸王茶姬小程序登录后，从本人授权的业务请求头获取 Qm-User-Token；可选 customerId 从积分流水接口 data.data 项获取，仅在流水为空时补充。不要使用手机号或设备标识代替。
- 填写格式：`每个非空行一个 Token，或 Token|customerId；仅在首个 | 分割。同账号配套字段，账号仅用换行分隔，不支持原 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CDRAIL_DATA`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：在本人已登录的成都地铁 App 中抓取签到请求 https://app.cdmetro.chengdurail.cn/platform/users/user/sign-in-integral，从请求头获取 token、app-token、Cookie 和实际 deviceId；凭据失效后重新登录获取。不得分享抓包内容。
- 填写格式：`每个非空行一个 JSON 对象或 URL 编码查询字符串；必填 token、app-token，Cookie 和设备请求头按本人抓包提供。支持 appToken/app_token 及 device-id/device_id 别名和其他自定义请求头；传输控制头忽略。查询字符串用 & 分字段，各字段仅在第一个 = 处分割，值中的 & 编码为 %26；推荐 JSON 保留复杂凭据。不得以 @ 或 & 分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CFMOTO_COOKIE`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：使用本人测试账号在 CFMOTO App 执行一次相关请求，从本人控制的本地网络调试记录中复制 Cookie 请求头里的 ticket；如 App 阻止调试，不要绕过安全机制。
- 填写格式：`ticket=<value> 或裸 ticket；多账号每行一个`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DDNSTO_ACCOUNTS`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：登录 DDNSTO 官网设备页面，在浏览器开发者工具网络面板复制 www.ddnsto.com 请求的完整 Cookie（含 csrftoken）。先申请一次七天免费套餐，从 /api/user/routers/路由器ID/ 请求路径取路由器ID；该值不是登录用户ID。可用兼容旧变量代替。
- 填写格式：`每个非空行填写 路由器ID|完整Cookie；仅在首个 | 分隔，同一行内 Cookie 原样保留，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `dlshyzx`

- 所属脚本：`scripts/durex.py`
- 获取或设置：在微信杜蕾斯会员中心小程序登录，用本人授权的抓包工具读取 vip.ixiliu.cn 请求头 Access-Token；失效时重新登录获取。
- 填写格式：`每个非空行一个完整令牌；保留变量名；不再使用上游的 # 或其他符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IKUUU_ACCOUNT`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：填写本人 ikuuu 登录邮箱和对应密码；在青龙面板中按邮箱|密码拼成一行。
- 填写格式：`每行一个账号：邮箱|密码；只用第一个竖线分隔，密码中的后续竖线会保留`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUAISHOU_COOKIE`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：在本人已登录的快手或快手极速版中打开“积分换好礼”页面，从本人控制的本地网络调试记录里找到 accelerate/info 请求，复制 Cookie 请求头；至少保留 kuaishou.api_st。不要绕过证书固定或使用第三方提取网站。
- 填写格式：`每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 & 或 @ 分隔`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WALLHAVEN_SAVE_DIR`

- 所属脚本：`scripts/main.py`
- 获取或设置：在青龙中设置自己有写权限的壁纸保存目录。原脚本使用 /ql/data/downloads/local-website/img；本版必须显式设置以避免默认写入。无需账号或凭据。
- 填写格式：`绝对目录路径；自动追加当天日期子目录。预演可使用 /tmp/wallhaven-dry-run-placeholder。`

#### `NGA_ACCOUNT`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：登录NGA官方客户端后，在本人设备的同一条 https://ngabbs.com/nuke.php 请求中读取 access_uid 与 access_token，按 access_uid|access_token 拼成一行；不要分享调试记录。
- 填写格式：`每行一个账号：access_uid|access_token；只用第一个竖线分隔`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NODESEEK_COOKIE`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：登录 nodeseek.com，打开浏览器开发者工具的 Network，刷新页面，选择同站请求，复制 Request Headers 中完整的 cookie 值。请妥善保存，不要发送给他人。
- 填写格式：`每个账号一个非空行，每行为完整 Cookie 请求头值；Cookie 内的 & 和 @ 保持原样`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PASSNAT_SK`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：登录 PassNAT 网页端，在浏览器开发者工具的网络面板中查看已登录 API 请求，复制 Authorization 请求头的完整值；每个账号单独一行，切勿公开。
- 填写格式：`每个非空行是一个账号的完整 Authorization 值；仅以换行分隔账号，不使用其他分隔符。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QUARK_COOKIE`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：登录夸克网盘 https://pan.quark.cn/，打开浏览器开发者工具的网络面板，选择已登录的夸克请求，复制请求头 Cookie 的完整值；失效后重新登录获取。只复制值，不包含 Cookie: 前缀或备注。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留分号及等号，不使用 &、&& 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `sfsyUrl`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：登录顺丰速运 App 或微信小程序，进入“我的-积分”，抓包 shareGiftReceiveRedirect 或 share/app/shareRedirect 请求，保存其完整 URL。不要将 URL 发到日志或通知中。多账号每个非空行一个 URL。
- 填写格式：`每个非空行一个完整的 URL 编码登录/分享 URL；整行作为同一账号凭据，不使用 &、@ 等字符分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_ACCOUNT`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：登录什么值得买手机客户端，使用本人授权的抓包工具查看签到请求；取请求表单 sk 和同一次请求的完整 Cookie（必须含 sess）。二者必须属于同一账号，不使用其他人的凭据。
- 填写格式：`每个非空行一个账号，格式 sk|完整 Cookie；只在第一个 | 处分割，保留后续 Cookie 文本。不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AGILE_STUDIO_ACCOUNTS`

- 所属脚本：`scripts/sudojia_33agilestudio.js`
- 获取或设置：在 https://33.agilestudio.cn 注册或登录，使用该账户的邮箱与登录密码；如忘记密码，先通过网站找回。将配套凭据填写到青龙环境变量，不需要抓取令牌。
- 填写格式：`每个非空行一个邮箱#密码，只按第一个 # 分隔，密码中的后续 #、& 和 @ 均保留；禁止使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ALL_GIRLS_TOKEN`

- 所属脚本：`scripts/sudojia_allgirls.js`
- 获取或设置：登录所有女生会员服务中心微信小程序，在本人授权的抓包工具中查找主机 7.wawo.cc 的请求，复制请求头 AccessToken 的完整值；失效后重新登录获取。不要复制整个请求头或分享令牌。
- 填写格式：`每个非空行一个账号的 AccessToken；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AMX_TOKEN`

- 所属脚本：`scripts/sudojia_amx.js`
- 获取或设置：登录安慕希微信小程序，在本人授权的抓包环境中查找发往 msmarket.msx.digitalyili.com 的请求，复制请求头 access-token 的完整值。失效后重新登录获取。请勿复制整个请求头或分享凭据。
- 填写格式：`每个非空行一个完整 Token；不使用 & 或 @ 分隔账号，行内字符保持不变，首尾空白忽略。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BANANA_ACCOUNT`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：在香蕉视频 APP 注册或登录，使用本人绑定的手机号和设置的登录密码；忘记密码请先在 APP 重置。无需抓包。
- 填写格式：`每个非空行一个账号：手机号#密码；仅按第一个 # 分割，密码中的后续 #、&、@ 原样保留；手机号为十一位数字。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BYM_ACCOUNT`

- 所属脚本：`scripts/sudojia_beiyinmei.js`
- 获取或设置：登录贝因美微信小程序，使用自己的授权抓包工具检查 h5.youzan.com 请求。取 extra-data 请求头内的 sid，以及签到 checkinV2.json 请求查询参数 access_token，二者必须属于同一账号。凭据时效较短，失效后重新登录获取。原 BYM_SID 单值配置需迁移至此变量，脚本不再使用源码内置令牌。
- 填写格式：`每个非空行填写 SID|access_token，仅按第一个竖线拆分，其后文本完整保留；不要使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BOTANY_ACCOUNT`

- 所属脚本：`scripts/sudojia_botanystar.js`
- 获取或设置：在植物星球小程序注册登录后，进入“我的 → 账号管理 → 修改密码”设置密码，使用注册手机号和该密码。
- 填写格式：`每个非空行一个手机号#密码，仅按第一个 # 分隔，密码中的后续 # 和 & 原样保留；行首尾空白会去除。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BW_TEA_TOKEN`

- 所属脚本：`scripts/sudojia_bwtea.js`
- 获取或设置：在本人微信霸王茶姬小程序登录时抓包，找到 https://webapi2.qmai.cn/web/seller/oauth/flash-sale-login 响应中的 token 和 user.id；失效后重新登录获取。不要分享抓包内容。
- 填写格式：`每个非空行填写 token#id，仅首个 # 分隔配套凭据，后续内容原样保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `COLORFUL_TOKEN`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：在七彩虹商城微信小程序退出登录，开启本地抓包后重新登录；复制 https://shop.skycolorful.com/api/User/DecryptPhoneNumber 请求体的完整 JSON。在本地压缩成一行，保留 OpenId、Iv、EncryptedData 及其他原始字段；勿上传至在线 JSON 工具。失效时重新登录抓取。
- 填写格式：`每个非空行一个完整 JSON 对象；OpenId、Iv、EncryptedData 均为非空字符串；不得用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `FLY_ANT_TOKEN`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：登录微信旧衣回收小程序，抓取 https://openapp.fmy90.com 的请求头 authorization，删除 bearer 前缀。每个账号独立获取；可在竖线后填写该账号当日真实且未兑换的步数。
- 填写格式：`每个非空行一个账号：Token 或 Token|真实步数；仅按第一个竖线拆分，不支持 & 分隔账号。步数为正整数，每次执行仅兑换一次，避免当天重复运行兑换。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `FN_NAS_COOKIE`

- 所属脚本：`scripts/sudojia_fnnas.js`
- 获取或设置：登录 https://club.fnnas.com，在浏览器开发者工具的网络面板选择本站已登录请求，复制请求头 Cookie。必须包含 pvRK_2132_auth 和 pvRK_2132_saltkey；过期后重新登录获取，勿公开分享。
- 填写格式：`每个非空行填写一个账号的完整 Cookie；同账号字段用分号保留，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HGF_COOKIE`

- 所属脚本：`scripts/sudojia_hgf.js`
- 获取或设置：登录微信厚工坊商城小程序（#小程序://厚工坊商城/aWVCNOaniBxf4Pk），通过本人设备的抓包工具查看发往 https://api.hgf1862.com 的请求头 sessionid；仅复制该字段的完整值，不填请求头名称或完整 Cookie。失效后重新登录获取。
- 填写格式：`每个非空行一个账号的 sessionid；仅按换行分隔，不使用 & 或 @；空行忽略。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HLZJ_UNID`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：打开海澜之家微信小程序，进入底部游戏，抓取本人账号向 https://gmdevpro.hlzjppgl.cn/server/api/authorized-login 发送的请求体，复制 union_id 字段值。凭据失效时重新获取，不要复制整个请求体。
- 填写格式：`每个非空行填写一个账号的 union_id；不使用 &、@ 或空格分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HZHFP_TOKEN`

- 所属脚本：`scripts/sudojia_hzhfp.js`
- 获取或设置：登录微信媓钻小程序（#小程序://媓钻/gANSWauVDzi4SPH），在本人设备抓取 api.hzyxhfp.com 的请求，复制 Authorization 请求头并删除开头的 Bearer 和空格；失效后重新登录抓取。不要分享凭据。
- 填写格式：`每个非空行一个账号的完整令牌，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `INSTAX_TOKEN`

- 所属脚本：`scripts/sudojia_instax.js`
- 获取或设置：登录富士 instax 玩拍由我俱乐部小程序，在「我的」绑定手机号加入会员。在本人授权的抓包环境中读取 instax.app.xcxd.net.cn 请求头 Authorization，去掉 Bearer 前缀。
- 填写格式：`每个非空行一个令牌；不以 & 或 @ 分隔账号。兼容令牌后附 #false 禁止该账号抽奖；仅在第一个 # 处分割，其余内容完整校验。旧 #true 不再默认开启抽奖。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JHCARD_BODY`

- 所属脚本：`scripts/sudojia_jhcard.js`
- 获取或设置：在江淮卡友 APP 登录时抓取 http://jacwxmp.starnetah.com:18280/v2driver/v2/login 的原始请求体，保留所有字段；失效后重新抓取。服务原接口使用明文 HTTP。
- 填写格式：`每个非空行一个完整 JSON，必需 phone、password、sendMessageKey、deviceType、appType、sign；行末可追加 #true 开启五次公开评论，#false 或省略均关闭。JSON 内的分隔字符原样保留，不使用 & 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JIANG_SHAN_SESSION`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：登录多娇江山 APP，在本人设备抓取发往 https://vapp.tmuyun.com 的请求，复制请求头 X-SESSION-ID 的完整值；过期后重新登录并抓取。不要复制整个请求头或 Cookie。
- 填写格式：`每行一个账号的会话值，仅以换行分隔；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JINDIAN_TOKEN`

- 所属脚本：`scripts/sudojia_jindian.js`
- 获取或设置：登录微信小程序「金典有机生活+」，在本人授权的抓包环境中读取发往 msmarket.msx.digitalyili.com 的请求头 access-token；只填写该值，失效时重新登录获取。
- 填写格式：`每个非空行一个账号的 access-token，不含请求头名称；不使用 &、@ 等符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JLC_TOKEN`

- 所属脚本：`scripts/sudojia_jlc.js`
- 获取或设置：登录嘉立创下单助手或 https://m.jlc.com/mapp/，抓取发送到 m.jlc.com 的请求头 x-jlc-accesstoken 和 secretkey；取同一账号的两个字段，不要分享抓包内容。
- 填写格式：`每行一个账号：x-jlc-accesstoken值#secretkey值；仅以首个 # 分割，其后的 # 保留；不支持用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JLC_COOKIE`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：登录 https://oshwhub.com/sign_in 后打开浏览器开发者工具的网络面板，从发往 oshwhub.com 的已登录请求头复制完整 Cookie；过期后重新登录获取。不要从 m.jlc.com 获取。
- 填写格式：`每个非空行填写一个账号的完整 Cookie，保留分号及值中的 &、@ 等字符，不添加 export 或包裹引号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JUEJIN_COOKIE`

- 所属脚本：`scripts/sudojia_juejin.js`
- 获取或设置：登录稀土掘金网页，在开发者工具的 Cookie 中复制 sessionid 的值；在网络面板手动签到，找到 api.juejin.cn/growth_api/v1/check_in 请求，复制问号之后的原始查询串。须含 uuid、spider、msToken、a_bogus；签名过期或登录失效后重新抓取，不自动生成签名。
- 填写格式：`每行 sessionid#原始查询串；仅以首个 # 分隔，查询串中的 & 保留；可包含 aid=2608。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KOZBS_TOKEN`

- 所属脚本：`scripts/sudojia_kozbs.js`
- 获取或设置：登录植白说官方商城微信小程序，在本人授权的抓包环境中查找 https://www.kozbs.com 请求，从请求头复制 x-dts-token 的值。凭据失效后重新登录获取，不要复制完整请求头。
- 填写格式：`每个非空行填写一个账号的完整令牌；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KTGZS_TOKEN`

- 所属脚本：`scripts/sudojia_ktgzs.js`
- 获取或设置：在微信打开开天工作室小程序，在自己的授权抓包环境中查找发往 https://api.box.vipinfinity.com 的请求，复制请求头 Authorization 的完整值。失效后重新登录并获取，不要复制 Cookie 或整个请求。
- 填写格式：`每个非空行一个账号的 Authorization 完整值；保留值内字符，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `GU_HOME_TOKEN`

- 所属脚本：`scripts/sudojia_kukahome.js`
- 获取或设置：登录顾家会员微信小程序，在本人授权的抓包环境中查看 https://mc.kukahome.com 请求头，取得同一账号的 AccessToken 和 X-Customer。凭据过期后重新登录获取。
- 填写格式：`每行 AccessToken#X-Customer，仅在首个 # 处分割，后续字符原样保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `GU_HOME_APP_SECRET`

- 所属脚本：`scripts/sudojia_kukahome.js`
- 获取或设置：从获授权的顾家应用 appid=667516 签名配置或合法取得的本任务上游脚本 appSecret 常量取得。所有账号共用应用签名参数，不是账号令牌；维护版不内置该值。断网预演无需此项。
- 填写格式：`应用签名密钥原文。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KURO_TOKEN`

- 所属脚本：`scripts/sudojia_kuro.js`
- 获取或设置：登录库街区官网 https://www.kurobbs.com/，在浏览器开发者工具 Application → Local storage 中复制 auth_token 的值；也可从本人已登录 APP 发往 api.kurobbs.com 的请求头获取 token。游戏须绑定角色并开启库街区展示。
- 填写格式：`每个非空行填写一个账号的完整 Token；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LAOBAN_OPENID`

- 所属脚本：`scripts/sudojia_laoban.js`
- 获取或设置：登录老板电器服务微商城微信小程序，在本人授权的抓包环境中查看 https://vip.foxech.com 请求正文，复制 openid 字段值；不是请求头。不得分享凭据。
- 填写格式：`每行一个账号的 openid，仅填写字段值，不带引号或请求正文；不使用 & 或 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LONG_FOR_TOKEN`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：登录龙湖天街微信小程序，用自己的抓包工具查看 gw2c-hw-open.longfor.com 请求头 token 或 lmToken；仅使用本人账号凭据。
- 填写格式：`每个非空行一个账号凭据，不使用 & 或 @ 分隔；同一值发送为 lmToken 与 X-LF-UserToken。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MALLCOO_TOKEN`

- 所属脚本：`scripts/sudojia_mallcoo.js`
- 获取或设置：登录欣都龙城微信小程序，抓取 https://m.mallcoo.cn 请求，在请求正文 Header.Token 中获取当前账号令牌；过期后重新登录抓取。
- 填写格式：`每个非空行一个完整 Token，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MAWUW_TOKEN`

- 所属脚本：`scripts/sudojia_mawuwang.js`
- 获取或设置：微信登录馬伍旺饮料厂小程序，通过本人授权抓包查看 https://webapi.qmai.cn/web/seller/oauth/flash-sale-login 响应，取 token 与 user.id。失效时重新登录获取，不分享响应。
- 填写格式：`每个非空行填写 token#id，仅在第一个 # 分割；其后内容完整保留，不以 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIDEA_COOKIE`

- 所属脚本：`scripts/sudojia_midea.js`
- 获取或设置：在本人账号登录的美的会员微信小程序中，使用本机抓包工具查看发往 https://mvip.midea.cn 的已登录请求，复制请求头 Cookie 的完整值，不包含 Cookie: 前缀。失效后重新登录并抓取；不要分享凭据。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留 Cookie 内的分号、等号和 &，不按 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MOTO_TOKEN`

- 所属脚本：`scripts/sudojia_moto.js`
- 获取或设置：登录摩托范 App，在本人授权的抓包环境中查看 https://api.58moto.com 的请求头 token 和同一账号的 uid；组合后填入青龙环境变量。不得公开分享抓包内容。
- 填写格式：`每个非空行填写 token#uid，仅按第一个 # 分隔；uid 为数字，不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MXBC_TOKEN`

- 所属脚本：`scripts/sudojia_mxbc.js`
- 获取或设置：在本人蜜雪冰城小程序登录后，用抓包工具查看 https://mxsa.mxbc.net 的账号接口请求头，提取 Access-Token 值。不要复制整个请求头或向他人发送抓包记录；失效后重新登录获取。
- 填写格式：`每个非空行一个完整 Access-Token；去除行首尾空白，不使用 &、@ 或其他符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MXBC_SIGNING_KEY`

- 所属脚本：`scripts/sudojia_mxbc.js`
- 获取或设置：正式运行需要应用 RSA 签名私钥。已有签名材料的来源为原上游 sudojia/AutoTaskScript 的 src/wx_mini/sudojia_mxbc.js 中 privateKeyStr；仅在确认有权使用后提取 PEM 完整文本。也可使用服务认可的授权应用签名材料。本版不内置、不下载签名私钥，不可用请求中的 sign 或 Access-Token 代替。离线预演无需此变量。
- 填写格式：`完整 RSA 私钥 PEM 文本（保留实际换行和 BEGIN/END 标记），或完整 PEM 文本的 Base64 编码；同一应用的账号共用此签名配置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NAIXUE_TOKEN`

- 所属脚本：`scripts/sudojia_naixue.js`
- 获取或设置：登录奈雪点单微信小程序，在自己的授权抓包工具中查看 tm-api.pin-dao.cn 请求头 Authorization，复制其值并删掉 Bearer 前缀。失效时重新登录获取；不要分享抓包内容。
- 填写格式：`每个非空行一个账号的令牌，不使用 & 或 @ 分隔，不包含 Bearer 前缀。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NESTLE_TOKEN`

- 所属脚本：`scripts/sudojia_nestle.js`
- 获取或设置：登录微信“雀巢会员”小程序，在自己授权的抓包环境中找到 crm.nestlechinese.com 的请求头 authorization，复制其值并去掉 Bearer 前缀；失效后重新登录获取。不要分享凭据。
- 填写格式：`每个非空行一个账号的 Token，也兼容带 Bearer 前缀的值；不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NFHK_COOKIE`

- 所属脚本：`scripts/sudojia_nfhk.js`
- 获取或设置：登录南方航空小程序并完成实名认证，使用自己的抓包工具查看 https://wxapi.csair.com/marketing-tools/ 路径请求的 Cookie，复制 sign_user_token 的值；失效后重新登录获取。
- 填写格式：`仅填写字段值，不带 sign_user_token=；每个非空行一个账号，不使用 & 或 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OPPOSHOP_ACCOUNTS`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：在 OPPO商城 APP 开启抓包，进入我的－签到任务，从 https://hd.opposhop.cn/api/cn/oapi/users/web/member/check?unpaid=0 请求获取同一账号的 User-Agent 和 Cookie。不要公开抓包结果。
- 填写格式：`每个非空行一个账号：User-Agent|Cookie；仅按第一个竖线分割，后续 Cookie 原样保留；不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PANG_GE_TOKEN`

- 所属脚本：`scripts/sudojia_pangge.js`
- 获取或设置：登录微信胖哥俩肉蟹煲小程序，在本人授权抓包中找到 saash5.namek.com.cn 请求，复制请求头 token 的值；失效时重新登录获取。
- 填写格式：`每个非空行填写一个账号的完整 token，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PAO_TEA_TOKEN`

- 所属脚本：`scripts/sudojia_paotea.js`
- 获取或设置：登录微信小程序“爷爷不泡茶”，通过本人授权的抓包查看 webapi.qmai.cn 请求头 qm-user-token，以及签到统计 userSignStatistics 请求体中的 activityId。每个账号填写其当前活动ID，不再使用历史默认活动或继承其他账号活动。
- 填写格式：`每行一个账号，格式为 Token#活动ID，仅按第一个 # 分隔；活动ID为数字，不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHYP_TOKEN`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：登录上海杨浦 APP，使用本人设备的抓包工具查看 https://ypapi.shmedia.tech 请求头 token。复制完整值，不含字段名；过期后重新登录获取。
- 填写格式：`每个非空行一个账号的完整 token；仅换行分隔，不使用 & 或 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHUI_FEI_COOKIE`

- 所属脚本：`scripts/sudojia_shuifei.js`
- 获取或设置：在微信公众号水费易打开个人中心，抓取 m.ipaiyun.cn 的个人中心请求，取得请求头 Cookie 和请求正文 memberId，必须属于同一账号。
- 填写格式：`每行 Cookie#memberId，仅在首个 # 处分割；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SITE_ACCOUNTS`

- 所属脚本：`scripts/sudojia_sspanel.js`
- 获取或设置：在网站页脚确认 Powered by SSPANEL，从浏览器地址栏获取站点 HTTPS 地址；使用本人注册邮箱及登录密码。需要验证码或双因素验证的站点无法通过本脚本登录。
- 填写格式：`每个非空行一个账号：HTTPS站点地址,邮箱:密码。仅在第一个逗号和之后的第一个冒号处分割，密码中的后续标点完整保留；不支持换行密码。禁止以 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `STAR_MOM_TOKEN`

- 所属脚本：`scripts/sudojia_starmom.js`
- 获取或设置：打开微信小程序星妈优选（#小程序://星妈优选/c8Gx0xHeOxwrMUv），使用本人授权的抓包工具，从 https://www.feihevip.com 请求头获取 token。有效期很短，失效需重新获取。
- 填写格式：`每个非空行一个完整 token，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TEBU_TOKEN`

- 所属脚本：`scripts/sudojia_tebu.js`
- 获取或设置：登录特步会员中心微信小程序，用抓包工具查看发往 https://mall-mobile-v6.vecrp.com 的请求，复制请求头 token 的完整值；失效后重新登录获取。仅在自己的设备上获取，不复制 Cookie 或整个请求头。
- 填写格式：`每个非空行一个账号的完整 token，不使用 &、@ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TILTA_TOKEN`

- 所属脚本：`scripts/sudojia_tilta.js`
- 获取或设置：打开并登录 TILTA影像城微信小程序，通过本人授权的抓包工具查看发往 https://java.vrupup.com 的请求，复制请求头 authorization 的完整值。有效期较短，失效后需重新获取。
- 填写格式：`每个非空行一个账号的完整 authorization 值；不使用 & 或 @ 分隔账号，无需添加额外前缀。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TUC_ACCOUNTS`

- 所属脚本：`scripts/sudojia_tuchong.js`
- 获取或设置：在图虫 APP 注册并绑定手机号，在账号设置中设置或重设登录密码；使用本人账号的手机号和密码，无需抓包。
- 填写格式：`每个非空行一个账号：手机号#密码。仅在第一个 # 分割，其后密码原样保留，包括 #、&、@；不支持用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `V2EX_COOKIE`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：在浏览器登录 https://www.v2ex.com，打开开发者工具的网络面板，刷新页面，复制该站点已登录请求的 Cookie 请求头完整值，不含 Cookie: 前缀。失效后重新登录获取。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留值中的 &、@ 和分号，不用这些字符分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WNNA_TOKEN`

- 所属脚本：`scripts/sudojia_wnna.js`
- 获取或设置：打开微信小程序“薇诺娜专柜商城”，通过本人授权的抓包环境查看 api.qiumeiapp.com 请求体中的 appUserToken。此值也用作用户信息接口的 zgUserToken。不要提供完整请求体。
- 填写格式：`每个非空行填写一个账号的原始令牌，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XHN_ACCOUNTS`

- 所属脚本：`scripts/sudojia_xhn.js`
- 获取或设置：使用真机注册新湖南 APP，在本人登录前开启抓包，登录成功后复制 https://xhnapi2.voc.com.cn/v5/user/login 的完整请求体。不要复制响应或请求头。登录失效后重新抓取。
- 填写格式：`每个非空行一个账号的 URL 编码表单，包含 password、logintype、RegistrationID、appid、type、username；保留全部原始字段与编码，& 仅分隔表单字段，不分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XWGAME_ACCOUNTS`

- 所属脚本：`scripts/sudojia_xiangwan.js`
- 获取或设置：在享玩游戏APP注册账号并设置登录密码，使用本人手机号及密码；不是短信验证码，无需抓包。将每个账号填入青龙环境变量的一行。
- 填写格式：`手机号#密码，每个非空行一个账号；仅在第一个 # 处分割，后续密码字符完整保留。不再使用 & 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XIAOMI_COMM_COOKIE`

- 所属脚本：`scripts/sudojia_xiaomi_community.js`
- 获取或设置：在自己的设备登录微信小程序「小米社区」，抓取 api.vip.miui.com 的请求，从请求头复制完整 Cookie，必须同时包含 serviceToken 和 miui_vip_ph；仅有 serviceToken 不足以签到。失效后重新登录并获取。
- 填写格式：`每个非空行一个账号的完整 Cookie；字段以分号分隔，字段值按第一个等号之后的全部内容保留；不按 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XINXI_TOKEN`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：登录心喜微信小程序，使用自己的抓包工具查看发往 https://api.xinc818.com 的请求，复制请求头 sso 的完整值；失效后重新登录获取。
- 填写格式：`每个非空行填写一个完整 sso 值；不添加变量名或引号，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XPFARM_TOKEN`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：在微信打开兴攀农场小程序，使用本人授权的抓包工具查看发往 https://p.xpfarm.cn 的请求，复制 authorization 请求头完整值。仅保存在青龙环境变量中，失效后重新登录抓取。
- 填写格式：`每个非空行一个账号的完整 authorization 值；仅按换行分隔，不使用 & 或 @ 分隔账号，不添加变量赋值语句。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZNDS_COOKIE`

- 所属脚本：`scripts/sudojia_znds.js`
- 获取或设置：登录 https://www.znds.com，打开浏览器开发者工具的网络面板，复制本站已登录请求的 Cookie 请求头，须含 auth 和 saltkey；过期后重新登录获取。
- 填写格式：`每个非空行填写一个账号的完整 Cookie，保留分号、等号与 &；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZX_ICE_TOKEN`

- 所属脚本：`scripts/sudojia_zxice.js`
- 获取或设置：登录甄稀冰淇淋微信小程序，使用抓包工具查看本人发往 msmarket.msx.digitalyili.com 的请求，复制请求头 access-token 的值。失效后重新登录并获取；不要复制整个请求头或向他人提供凭据。
- 填写格式：`每个非空行填写一个账号的 access-token 原值；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：在浏览器登录百度贴吧后，从 tieba.baidu.com 的请求 Cookie 中复制 BDUSS；可只填写 BDUSS 的值，也可填写包含 BDUSS 的完整 Cookie。请仅在自己的青龙环境中保存。
- 填写格式：`每个账号占一个非空行；单行填写 BDUSS 值，或填写形如 BDUSS=<值>; STOKEN=<值> 的完整 Cookie。同一账号的 Cookie 字段保留在同一行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `tsthbck`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：在微信塔斯汀小程序登录，用本人授权的抓包工具查看 sss-web.tastientech.com 请求头中的 user-token；仅复制该字段值，过期后重新获取。
- 填写格式：`每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 & 或 @ 分隔账号，字段内部字符保持原样。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TY_ACCOUNTS`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：在天翼云盘官方客户端或官方网站确认账号及登录密码；忘记密码请使用官方找回流程，出现验证码或风控时先人工处理。旧 TY_USERNAME/TY_PASSWORD 须将同账号配对后合为本变量；不要修改密码中的特殊字符。
- 填写格式：`每个非空行一个账号，格式：用户名|密码；仅在第一个 | 分割，后续密码原样保留；账号之间只能换行`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。


### 可选参数说明

#### `ALIYUN_DRIVE_DRY_RUN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；设为 1 可在不联网、不等待、不签到且不保存凭据的情况下模拟所有账号。
- 填写格式：`1、true、yes 或 on 表示启用。`

#### `ALIYUN_MAX_DELAY_SECONDS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；设置正式执行前的最大随机等待时间，默认 0。
- 填写格式：`非负整数秒数。`

#### `ALIYUN_PERSIST_ROTATED_TOKENS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；仅在需要把轮换后的刷新令牌写入文件时明确设为 1，默认关闭。
- 填写格式：`1、true、yes 或 on 表示启用。`

#### `ALIYUN_TOKEN_OUTPUT_FILE`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：启用令牌持久化时，填写位于现有目录内的令牌文件绝对路径。
- 填写格式：`本地绝对文件路径；文件以 0600 权限原子替换，每行一个令牌。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `ATXYQ_DRY_RUN`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：在青龙环境变量中开启完全断网预演。
- 填写格式：`默认 0；1 开启，模拟所有已启用动作与通知，不表示业务成功。`

#### `atxyqDel`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：兼容原上游变量，仅在确认愿意删除本人最近帖子时开启。
- 填写格式：`整数，默认 0 不删除；非零删除本人最近十篇列表内帖子。`

#### `ATXYQ_LIKE`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：在青龙环境变量中显式开启校园文章互动。
- 填写格式：`默认 0；1 对最多两篇文章各点赞后取消点赞，保持上游成对动作。`

#### `ATXYQ_POST`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：在青龙环境变量中显式开启公开发帖。
- 填写格式：`默认 0；1 发布一篇动态，优先一言并保留作者来源署名，失败回退本地正文。`

#### `ATXYQ_LOCAL_TEXT`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：自行填写愿意公开发布的非敏感校园文字，作为一言失败时的回退。
- 填写格式：`可选，空白折叠后 1 至 280 字；默认本地校园正文。`

#### `ATXYQ_IMAGE_NAME`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：从本人小程序已上传图片的服务响应取得文件名，不填写凭据或伪造图片。
- 填写格式：`可选图片文件名，必须与 ATXYQ_IMAGE_DIR 同时填写；不会上传或自动生成图片。`

#### `ATXYQ_IMAGE_DIR`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：从同一张本人已上传图片的服务响应取得目录；上游动态目录形式为 @senior/dynamic/。
- 填写格式：`可选图片服务目录，与 ATXYQ_IMAGE_NAME 配套；启用发帖时登记已有图片。`

#### `ATXYQ_HELP_LIKE`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：仅在确认 ATXYQ_ASSIST 为本人选择的目标后开启。
- 填写格式：`默认 0；1 为指定帖子点赞一次，不读取远程助力名单。`

#### `ATXYQ_INVITE`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：仅在愿意绑定所选邀请关系并确认目标后开启。
- 填写格式：`默认 0；1 创建 ATXYQ_ASSIST 指定邀请关系，未知业务响应按失败处理。`

#### `ATXYQ_ASSIST`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：从自己确认的目标帖子与邀请请求取得公开帖子编号、原正文、目标用户编号和学校编号；不得包含凭据。
- 填写格式：`可选 JSON 对象，含 topicId、text、userId、schoolId；三个编号为数字，text 为目标帖原正文；开启助力或邀请时必填。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：使用青龙全局通知开关。
- 填写格式：`默认 1；0、false、no、off 禁用；其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：可选指定已有青龙 notify.py 或 sendNotify.js 所在目录；默认查找脚本目录、可导入通知模块和青龙常见目录。
- 填写格式：`本地目录路径，通知不可用或失败不改变业务退出码。`

#### `BAIDUWANGPAN_DRY_RUN`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：设为 1 可仅验证配置，不访问网络且不改变账号状态。
- 填写格式：`1/true/yes/on 启用`

#### `BAIDUWANGPAN_DELAY_MAX`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：可选的账号间最大随机等待秒数，默认 0（不等待）。
- 填写格式：`非负整数`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：青龙全局通知开关，默认启用；设为 0、false、no 或 off 可禁用。
- 填写格式：`1/0 或常见布尔值`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：如青龙 notify.py 不在标准位置，可设为其所在目录。
- 填写格式：`包含 notify.py 的目录路径`

#### `BSLY_DRY_RUN`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：在青龙环境变量中设置；预演时设为 1。
- 填写格式：`1 为完全断网预演，其他值为实跑，默认 0。`

#### `BSLY_ENABLE_DRAW`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：确认允许消耗抽奖机会后在青龙环境变量中设置为 1。
- 填写格式：`仅 1 允许实跑抽奖，默认 0；未开启的实跑以配置错误非零退出。`

#### `BSLY_MAX_DRAWS`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：根据活动规则和希望消耗的机会数量自行设置。
- 填写格式：`1 至 100 的整数，每账号请求次数上限，默认 1。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，不区分大小写；预演仅本地模拟通知，保证断网。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：使用自定义青龙公共通知模块时，设置 notify.py 所在目录；通常无需设置。
- 填写格式：`可选的本地目录；通知不可用不改变业务退出码。`

#### `BWCJ_TASKS`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：按需选择；默认新版签到，旧版需显式开启。
- 填写格式：`new、old 或 new,old；默认 new。`

#### `BWCJ_ACTIVITY_ID`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：从本人小程序新版签到请求中的 activityId 获取；默认保留上游历史值，活动失效时核对当前请求。
- 填写格式：`数字字符串，默认 947079313798000641。`

#### `BWCJ_STORE_ID`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：从本人小程序签到请求中的 storeId 或 store_id 获取。
- 填写格式：`正整数，默认 49006。`

#### `BWCJ_DRY_RUN`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：预演时设置为 1，无需从服务获取。
- 填写格式：`1、true、yes、on 开启完全断网预演，默认关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：青龙通知总开关，默认开启；需在青龙配置通知渠道。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：可选，填写青龙 notify.py 所在目录；默认尝试导入 notify 及青龙标准目录。
- 填写格式：`目录路径。`

#### `CDRAIL_DRY_RUN`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：自行设置为1启用完全断网预演。
- 填写格式：`默认0；1、true、yes、on启用`

#### `TIMEOUT`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：按网络情况自行设置。
- 填写格式：`1至120的整数秒，默认15`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：自行设置是否启用首次签到前随机等待。
- 填写格式：`默认true；仅true启用`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：自行设置随机等待上限。
- 填写格式：`0至86400的整数秒，默认3600；预演不等待`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：青龙通知全局开关。
- 填写格式：`默认1；0、false、no、off关闭；预演只生成本地通知摘要以保证断网`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/cdrail.py`
- 获取或设置：可选，填写青龙现有 notify.py 所在目录；也自动查找可导入模块及青龙标准目录。
- 填写格式：`本地目录路径；通知不可用或失败不改变业务退出码`

#### `CFMOTO_ACTIVITY_COUNT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置互动任务轮数，设为 0 可只签到。
- 默认值：`3`

#### `CFMOTO_ACTION_DELAY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置每个积分动作之间的等待秒数。
- 默认值：`2`

#### `CFMOTO_POST_CONTENTS`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅在随机文案接口不可用时，作为自定义本地兜底文案。
- 填写格式：`多条内容用换行或 | 分隔`

#### `CFMOTO_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置任务启动前的最大随机等待秒数。
- 默认值：`0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；默认通过青龙通知组件推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `CFMOTO_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；设为 0 可关闭 notify.py 通知。
- 默认值：`1`

#### `CFMOTO_USER_AGENT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：通常无需设置；仅默认 User-Agent 失效时，从同一 CFMOTO App 请求头复制。

#### `CFMOTO_DRY_RUN`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅预演时手工设为 1。
- 默认值：`0`

#### `ddns_userid`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：兼容上游单账号参数；从官网设备页面的 /api/user/routers/路由器ID/ 请求路径获取，与 ddns_cookie 配套使用。配置 DDNSTO_ACCOUNTS 时忽略此变量。
- 填写格式：`单个路由器ID，仅字母、数字、下划线或连字符；不接受多行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ddns_cookie`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：兼容上游单账号参数；登录官网后在开发者工具网络面板复制 Cookie 请求头，与 ddns_userid 配套使用。
- 填写格式：`单行完整 Cookie，含唯一且非空的 csrftoken；末尾不必带分号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DDNSTO_DRY_RUN`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`1 启用断网预演，0 执行真实续费；默认 0；也支持 true/false、yes/no、on/off。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：在青龙环境变量中手动设置；通知调用使用青龙 notify.py。
- 填写格式：`默认 1；0、false、no、off 关闭通知。预演尝试通知时封锁网络，因此远程通知不会送达。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：如青龙通知模块不在默认脚本目录，可填写已有 notify.py 所在目录；此配置不影响续费接口。
- 填写格式：`已有通知模块目录的路径，不执行下载或安装。`

#### `DUREX_DRY_RUN`

- 所属脚本：`scripts/durex.py`
- 获取或设置：在青龙环境变量中设置；断网预演使用 1。
- 填写格式：`1 开启断网预演，0 正式执行；默认 0。`

#### `DUREX_SHARE`

- 所属脚本：`scripts/durex.py`
- 获取或设置：本人确实完成活动分享并确认需要上报记录后设置。
- 填写格式：`1 开启分享记录上报，0 关闭；默认 0。`

#### `DUREX_SHARE_ACT_ID`

- 所属脚本：`scripts/durex.py`
- 获取或设置：从本人小程序分享请求的 act_id 参数获取并核对活动仍有效。
- 填写格式：`数字活动编号；默认沿用上游 343766308960192；仅开启分享时使用。`

#### `DUREX_DRAW`

- 所属脚本：`scripts/durex.py`
- 获取或设置：在小程序查看抽奖规则，明确同意可能消耗机会或积分后设置。
- 填写格式：`1 开启抽奖，0 关闭；默认 0。`

#### `dlshyzx_drawid`

- 所属脚本：`scripts/durex.py`
- 获取或设置：从本人小程序抽奖接口 /mp/activity.lottery/draw 的 snId 参数获取；开启抽奖时必须填写，不使用过期示例。
- 填写格式：`数字活动编号；所有账号参与同一活动；仅 DUREX_DRAW=1 时必填。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/durex.py`
- 获取或设置：青龙全局通知开关；通知模块由青龙提供。
- 填写格式：`默认 1；0、false、no、off 关闭；断网预演仅生成本地通知预览。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/durex.py`
- 获取或设置：填写已安装青龙 notify.py 所在目录；不需要下载其他仓库。
- 填写格式：`可选目录路径；否则查找可导入的 notify 和 /ql/data/scripts、/ql/scripts。`

#### `IKUUU_MAX_RANDOM_DELAY`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：可选；需要错峰执行时自行设置。
- 填写格式：`0 到 3600 的整数秒，默认 0（不延迟）。`

#### `IKUUU_DRY_RUN`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：测试配置时设为 1；该模式完全断网且不执行签到。
- 填写格式：`1 启用；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：青龙全局通知开关；默认开启。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`包含 notify.py 的绝对目录路径。`

#### `KUAISHOU_DRY_RUN`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；预演时手工设置为 1，正式查询时删除或设为 0。
- 填写格式：`1/true/yes/on 开启断网预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `WALLHAVEN_PAGES`

- 所属脚本：`scripts/main.py`
- 获取或设置：按需在青龙环境变量中设置抓取页数；默认保留上游的最新第 1 至 5 页。
- 填写格式：`1 至 100 的整数，默认 5。`

#### `WALLHAVEN_DRY_RUN`

- 所属脚本：`scripts/main.py`
- 获取或设置：断网核验时设置为 1；正式运行设为 0 或不设置。
- 填写格式：`0、false、no、off 表示正式运行；其他值表示断网预演。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/main.py`
- 获取或设置：使用青龙已有的通知设置；本脚本不需要配置通知凭据。
- 填写格式：`默认 1；0、false、no、off 关闭通知。断网预演仅生成通知摘要，不调用通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/main.py`
- 获取或设置：仅当青龙 notify.py 未位于标准脚本目录或模块搜索路径时，指定其所在目录。通知不可用不影响下载退出码。
- 填写格式：`包含 notify.py 的本地目录路径。`

#### `NGA_UA`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：通常无需设置；如接口要求，可填写获取凭据时NGA官方客户端请求中的 User-Agent。
- 填写格式：`单行 User-Agent，默认 Nga_Official/90409`

#### `NGA_ENABLE_DAILY_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 1 明确启用任务2、131、30的计数动作。
- 填写格式：`布尔值，默认 0`

#### `NGA_ENABLE_VIDEO_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 1 明确启用免广告及N币视频任务计数；会改变任务/奖励状态。
- 填写格式：`布尔值，默认 0`

#### `NGA_ENABLE_SHARE_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 1 明确启用分享记录和奖励领取；仅记录分享事件，不自动发布文本。
- 填写格式：`布尔值，默认 0`

#### `NGA_QUERY_STATS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 0 可关闭签到后的资产查询。
- 填写格式：`布尔值，默认 1`

#### `NGA_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：按需填写执行前随机延迟的最大秒数。
- 填写格式：`0至21600，默认0`

#### `NGA_ACTION_DELAY_SECONDS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：按需调整连续日常/分享动作之间的间隔。
- 填写格式：`0至30，默认1`

#### `NGA_VIDEO_DELAY_SECONDS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：按需调整视频任务计数之间的间隔；过短可能不被服务端认可。
- 填写格式：`0至120，默认30`

#### `NGA_HTTP_TIMEOUT`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：按网络状况设置单次HTTPS请求超时秒数。
- 填写格式：`3至60，默认20`

#### `NGA_DRY_RUN`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 1 仅校验配置并展示计划动作，完全不访问NGA。
- 填写格式：`布尔值，默认0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：全局通知开关；设为0、false、no或off关闭。
- 填写格式：`布尔值，默认1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：仅当notify.py不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `NODESEEK_DRY_RUN`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：手动设置为 1 以执行断网配置预演
- 填写格式：`1/true/yes/on 表示启用`

#### `NS_RANDOM`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：按是否使用 NodeSeek 随机签到奖励模式设置
- 填写格式：`布尔值，默认 true`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：如需在时间窗口内错峰执行则设为 true
- 填写格式：`布尔值，默认 false`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：自定义错峰时间窗口
- 填写格式：`0..86400 整数秒，默认 3600`

#### `NS_STATS_DAYS`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：自定义签到收益统计窗口
- 填写格式：`1..365 整数天，默认 30`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：青龙全局通知开关；如需关闭本脚本通知则设为 0
- 填写格式：`0/false/no/off 表示禁用，默认启用`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：仅当青龙通知脚本不在默认路径时，设为 notify.py 或 sendNotify.js 所在目录
- 填写格式：`本地目录绝对路径`

#### `PASSNAT_DRY_RUN`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：无需获取；设置为 1、true、yes 或 on 即启用完全断网预演。
- 填写格式：`布尔值`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：无需获取；仅在需要随机错峰时设置为 true，默认关闭。
- 填写格式：`布尔值`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：无需获取；与 RANDOM_SIGNIN=true 配合设置最大随机延迟秒数。
- 填写格式：`非负整数秒，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：无需获取；默认启用，设置为 0、false、no 或 off 可关闭通知。
- 填写格式：`布尔值`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：如 notify.py 不在青龙标准目录，可设置为其所在目录。
- 填写格式：`包含 notify.py 的本地目录路径`

#### `QUARK_DRY_RUN`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：设为 1 可完全断网检查配置与执行流程，不验证真实凭据、不签到、不调用通知模块；会生成通知摘要。
- 填写格式：`1、true、yes、on 开启，默认关闭。`

#### `QUARK_TIMEOUT_SECONDS`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：按网络环境设置单次 HTTP 请求超时。
- 填写格式：`3 至 60 的整数秒数，默认 15。`

#### `QUARK_RANDOM_DELAY_MAX_SECONDS`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：按需要设置每个实时账号执行前的随机延迟上限。
- 填写格式：`0 至 3600 的整数秒数，默认 0；预演不等待。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：使用青龙现有通知配置；设为 0 可关闭。通知异常不影响业务退出码。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：可选，填写青龙现有 notify.py 所在目录；也会尝试导入 notify 及青龙标准脚本目录。
- 填写格式：`本地目录路径，无需安装或下载应用。`

#### `SFSU_DRY_RUN`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：设为 1 启用完全断网预演。
- 填写格式：`布尔值；1 表示启用`

#### `SF_AUTO_COUPON`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：仅在确认允许脚本自动创建生活特权免费券订单时设为 1；默认关闭。
- 填写格式：`布尔值；1 表示启用`

#### `SF_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：按需设置任务启动前的最大随机延迟秒数；默认 0，不延迟。
- 填写格式：`0 至 86400 的整数秒数`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：青龙全局通知开关；设为 0、false、no 或 off 可关闭通知。
- 填写格式：`布尔开关，默认启用`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，设置为包含 notify.py 的目录。
- 填写格式：`本地目录路径`

#### `SMZDM_USER_AGENT_APP`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：可选，从本人手机客户端请求头获取 User-Agent；不配置时根据 Cookie 的安卓版本字段生成，缺失时使用维护版默认值。
- 填写格式：`单行客户端 User-Agent`

#### `SMZDM_DRY_RUN`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：离线验证时设为 1；正式执行时删除或设为 0。
- 填写格式：`1、true、yes、on 启用离线预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：默认开启青龙汇总通知；按需设为 0、false、no 或 off 关闭。预演仅生成脱敏通知，不调用联网通知组件。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未配置时检查 /ql/data/scripts 和 /ql/scripts。通知不可用不改变业务退出码。
- 填写格式：`本机通知组件目录路径`

#### `AGILE_STUDIO_DRY_RUN`

- 所属脚本：`scripts/sudojia_33agilestudio.js`
- 获取或设置：需要断网预演时手动设为 1。
- 填写格式：`1 为断网预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_33agilestudio.js`
- 获取或设置：按通知需要配置，默认启用。
- 填写格式：`0、false、no、off 关闭，不区分大小写；预演始终只生成摘要，不联网投递。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_33agilestudio.js`
- 获取或设置：仅在青龙通知模块不在默认目录时，填写已有 sendNotify.js 所在目录；否则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机通知模块目录路径，仅用于可选通知，业务无此依赖。`

#### `ALL_GIRLS_DRY_RUN`

- 所属脚本：`scripts/sudojia_allgirls.js`
- 获取或设置：在青龙环境变量中手动设置，断网预演时设为 1。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_allgirls.js`
- 获取或设置：使用青龙全局通知开关，默认开启；断网测试设置为 0。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_allgirls.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录绝对路径。`

#### `AMX_DRY_RUN`

- 所属脚本：`scripts/sudojia_amx.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 为预演；其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_amx.js`
- 获取或设置：青龙通知总开关，默认启用。
- 填写格式：`0、false、no、off 禁用，忽略大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_amx.js`
- 获取或设置：可选：设置已有青龙 sendNotify.js 所在目录；否则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径，不下载或安装通知模块。`

#### `BANANA_DRY_RUN`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：设为 1 进行完全断网预演。
- 填写格式：`0 或 1，默认 0`

#### `BANANA_FAVORITE`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：确认愿意添加五个随机视频收藏后设为 1；不会删除已有或新增收藏。
- 填写格式：`0 或 1，默认 0`

#### `BANANA_COMMENT`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：确认愿意公开发布随机视频评论后设为 1；文本优先使用一言并署名，任何获取失败均回退本地文本。
- 填写格式：`0 或 1，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：青龙通知全局开关；默认启用。预演会调用通知模块但阻止联网，通知失败不影响业务退出码。
- 填写格式：`0、false、no、off 关闭，其余启用`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_bananavideo.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`可选本地目录`

#### `BYM_DRY_RUN`

- 所属脚本：`scripts/sudojia_beiyinmei.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 表示预演，其余值表示实际执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_beiyinmei.js`
- 获取或设置：青龙环境变量中设置，默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_beiyinmei.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时自动检查 /ql/data/scripts 和 /ql/scripts。业务执行不依赖通知模块。
- 填写格式：`本地目录路径。`

#### `BOTANY_DRY_RUN`

- 所属脚本：`scripts/sudojia_botanystar.js`
- 获取或设置：需要断网预演时设为 1，正式运行不设置。
- 填写格式：`1 表示预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_botanystar.js`
- 获取或设置：青龙环境变量中设置；默认开启通知。
- 填写格式：`0、false、no、off 关闭通知，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_botanystar.js`
- 获取或设置：可填写青龙已有 sendNotify.js 所在目录；不设置时自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知模块目录路径。`

#### `BW_TEA_DRY_RUN`

- 所属脚本：`scripts/sudojia_bwtea.js`
- 获取或设置：在青龙环境变量中手动设置为 1 可断网预演。
- 填写格式：`1 为预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_bwtea.js`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，其余开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_bwtea.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置则查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知模块目录；业务运行不依赖该目录。`

#### `COLORFUL_DRY_RUN`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：设为 1 进行完全断网预演。
- 填写格式：`1 开启；默认关闭。`

#### `COLORFUL_COMMENT`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：确认愿意向商城社区公开发表评论后设为 1；默认关闭，不影响签到和积分查询。
- 填写格式：`仅 1 开启；每账号每次最多三条，已达当日九分上限则停止。`

#### `COLORFUL_COMMENT_TEXT`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：可选的本地备用评论，仅在一言请求或内容校验失败时使用；勿填写任何个人或凭据信息。
- 填写格式：`合并空白并去除首尾空白后不超过 280 个字符；为空或超长则使用内置文本。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：青龙通知全局开关，默认开启。
- 填写格式：`0、false、no、off 关闭，忽略大小写；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_colorful_mall.js`
- 获取或设置：可选，填写现有青龙 sendNotify.js 所在目录；未设置时依次检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；通知不可用或失败不改变业务退出码。`

#### `FLY_ANT_DRAW`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：由用户自行设置；抽奖，可能消耗环保豆，余额验证且不少于 10 才执行
- 填写格式：`0 或 1，默认 0`

#### `FLY_ANT_EARLY_SIGN`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：由用户自行设置；早起打卡，请先在小程序确认活动资格与时间
- 填写格式：`0 或 1，默认 0`

#### `FLY_ANT_BET`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：由用户自行设置；早起报名，可能扣除环保豆，请先在小程序确认规则
- 填写格式：`0 或 1，默认 0`

#### `FLY_ANT_DRY_RUN`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：由用户自行设置；完全断网预演，通知只输出本地脱敏预览
- 填写格式：`0 或 1，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：青龙通知总开关，默认开启；正式执行通过青龙通知模块投递。
- 填写格式：`默认 1；0、false、no、off 关闭通知`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_flyant.js`
- 获取或设置：可选，填写已有青龙 sendNotify.js 或 notify.py 所在目录；未设置则搜索青龙标准目录。
- 填写格式：`本地目录绝对路径`

#### `FN_NAS_DRY_RUN`

- 所属脚本：`scripts/sudojia_fnnas.js`
- 获取或设置：在青龙环境变量中手动设置，断网预演时设为 1。
- 填写格式：`1 表示断网预演，其他值表示正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_fnnas.js`
- 获取或设置：青龙通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭通知，不区分大小写；预演只生成摘要，不发送网络通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_fnnas.js`
- 获取或设置：如使用自定义青龙通知模块，填写现有 sendNotify.js 所在目录；不设置时查找青龙标准目录。
- 填写格式：`本地目录路径，仅用于可选通知，不参与业务请求。`

#### `HGF_DRY_RUN`

- 所属脚本：`scripts/sudojia_hgf.js`
- 获取或设置：手动设置为 1 启用断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_hgf.js`
- 获取或设置：青龙环境变量中设置；默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_hgf.js`
- 获取或设置：如青龙通知模块不在标准目录，填写已有 sendNotify.js 所在目录；不下载或安装通知模块。
- 填写格式：`本机通知模块目录路径，可省略。`

#### `HLZJ_DRY_RUN`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：自行设置；设为 1 完全断网预演，通知仅预览。
- 填写格式：`0 或 1，默认 0`

#### `HLZJ_USE_POWER`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：确认允许消耗游戏电力后设为 1；关闭时同时跳过依赖电力操作的宝箱领取。
- 填写格式：`0 或 1，默认 0`

#### `HLZJ_POWER_LIMIT`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：自行设置每账号单次运行的电力请求上限；仍有剩余任务时达到上限按失败处理。
- 填写格式：`1 至 100 的整数，默认 20`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：使用青龙已有通知配置；设为 0、false、no 或 off 可关闭通知。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_hlzj_game.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径，可不设置`

#### `HZHFP_DRY_RUN`

- 所属脚本：`scripts/sudojia_hzhfp.js`
- 获取或设置：手动设置为 1 可断网演练；省略为正式执行。
- 填写格式：`1 表示演练，其余值表示正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_hzhfp.js`
- 获取或设置：青龙环境变量中手动设置；默认启用通知。
- 填写格式：`0、false、no、off 关闭通知，忽略大小写；演练始终仅输出本地通知以保证断网。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_hzhfp.js`
- 获取或设置：可填写青龙现有 sendNotify.js 所在目录；未设置时自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`通知模块目录的绝对路径；不用于业务接口。`

#### `INSTAX_DRAW`

- 所属脚本：`scripts/sudojia_instax.js`
- 获取或设置：自行设置；确认愿意消耗抽奖机会后设为 1。
- 填写格式：`0（默认关闭）或 1（显式开启）；账号 #false 优先。`

#### `INSTAX_DRY_RUN`

- 所属脚本：`scripts/sudojia_instax.js`
- 获取或设置：离线验证时设置为 1。
- 填写格式：`0 或 1；1 时不请求业务接口或通知网络，仅打印脱敏通知预演。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_instax.js`
- 获取或设置：使用青龙通知配置；默认开启。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_instax.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时查找青龙标准目录。
- 填写格式：`本机通知模块目录路径；非业务依赖。`

#### `JHCARD_DRY_RUN`

- 所属脚本：`scripts/sudojia_jhcard.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 开启，其余值正式运行`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jhcard.js`
- 获取或设置：青龙通知全局开关，默认开启；预演只展示脱敏通知，不联网投递。
- 填写格式：`0、false、no、off 关闭，忽略大小写`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jhcard.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；默认查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径`

#### `JIANG_SHAN_ACTIONS`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：按需配置，默认 sign,read。share、comment、like、local 需要显式加入才执行。空字符串表示仅查询。
- 填写格式：`逗号分隔动作：sign 签到、read 阅读、share 分享任务上报、comment 公开评论、like 点赞、local 本地服务任务上报。`

#### `JIANG_SHAN_COMMENT_TEXT`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：可选本地评论回退文本；默认“感谢分享这则资讯。”。启用评论后先从一言获取正文、作者与出处，网络或 HTTP 错误、超时、响应过大、JSON 无效、正文缺失或超长时回退。
- 填写格式：`合并空白后非空且不超过 280 个字符，不填写任何个人信息或凭据。`

#### `JIANG_SHAN_DRY_RUN`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：离线验证时设置为 1，正式执行为 0 或不设置。
- 填写格式：`1 或 0；预演不调用业务或文本接口，通知调用禁止网络传输。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：沿用青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jiangshan.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。通知模块不可用时记录状态，不改变业务退出码。
- 填写格式：`本机通知模块目录。`

#### `JINDIAN_DRY_RUN`

- 所属脚本：`scripts/sudojia_jindian.js`
- 获取或设置：手动设置为 1 开启断网预演。
- 填写格式：`1 为预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jindian.js`
- 获取或设置：按通知需求手动设置，默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jindian.js`
- 获取或设置：可选：填写青龙 sendNotify.js 所在目录；未设置时自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径，仅用于青龙通知集成；业务执行不依赖此目录。`

#### `JLC_CLAIM_REWARD`

- 所属脚本：`scripts/sudojia_jlc.js`
- 获取或设置：可选，确认接受官方接口默认奖励后手动设置；上游描述默认奖励为金豆，但接口没有显式奖励类型参数。默认不自动选择奖励。
- 填写格式：`0（默认）或 1（授权领取并最多再签到一次）`

#### `JLC_DRY_RUN`

- 所属脚本：`scripts/sudojia_jlc.js`
- 获取或设置：本地验证时设为 1，不调用业务接口或通知网络。
- 填写格式：`1 为完全断网预演，其余值为正式执行`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jlc.js`
- 获取或设置：使用青龙已配置的 sendNotify.js；默认开启，预演时仅模拟通知以保证断网。
- 填写格式：`0、false、no、off 关闭，不区分大小写；默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jlc.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。通知不可用或失败时保留业务退出码。
- 填写格式：`本机目录绝对路径`

#### `JLC_YJ_DRY_RUN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`1 开启完全离线预演；其他值正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：在青龙环境变量中手动设置；默认开启。
- 填写格式：`0、false、no、off 关闭通知，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：可选填写已有青龙 sendNotify.js 所在目录；否则依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径；无需额外仓库，模块缺失不改变业务退出码。`

#### `JUEJIN_DRY_RUN`

- 所属脚本：`scripts/sudojia_juejin.js`
- 获取或设置：设置为 1 进行完全断网预演。
- 填写格式：`1 启用，其余值执行正式任务。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_juejin.js`
- 获取或设置：青龙全局通知开关，默认启用。断网预演生成通知摘要但不投递，以保证零网络访问。
- 填写格式：`0、false、no、off 关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_juejin.js`
- 获取或设置：可选：填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录绝对路径。`

#### `KOZBS_DRY_RUN`

- 所属脚本：`scripts/sudojia_kozbs.js`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`1 为完全断网预演，其余值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_kozbs.js`
- 获取或设置：在青龙环境变量中设置全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，大小写不敏感；其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_kozbs.js`
- 获取或设置：可填写青龙官方通知模块 sendNotify.js 所在目录；未配置时自动查找 /ql/data/scripts 与 /ql/scripts。
- 填写格式：`本机通知模块目录路径，仅用于可选通知，不影响独立业务执行。`

#### `KTGZS_DRY_RUN`

- 所属脚本：`scripts/sudojia_ktgzs.js`
- 获取或设置：在青龙环境变量中设置为 1 启用完全断网预演。
- 填写格式：`1 表示预演，其他值表示正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_ktgzs.js`
- 获取或设置：青龙通知总开关，默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_ktgzs.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；不设置则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机通知模块的目录路径；仅通知使用，业务请求不依赖该模块。`

#### `GU_HOME_DRY_RUN`

- 所属脚本：`scripts/sudojia_kukahome.js`
- 获取或设置：青龙环境变量中设置。
- 填写格式：`1 为完全断网预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_kukahome.js`
- 获取或设置：青龙环境变量中设置，全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭，不区分大小写。预演只生成摘要，不联网发送。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_kukahome.js`
- 获取或设置：可选，填写已有青龙 sendNotify.js 所在目录；未设置时依次查找 /ql/data/scripts、/ql/scripts。
- 填写格式：`本地通知模块目录路径；不可用时记录通知失败并保留业务退出码。`

#### `KURO_DRY_RUN`

- 所属脚本：`scripts/sudojia_kuro.js`
- 获取或设置：手动设置为 1 进行断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_kuro.js`
- 获取或设置：青龙环境变量中设置；默认开启。
- 填写格式：`0、false、no、off 关闭通知，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_kuro.js`
- 获取或设置：可选：填写已有青龙 sendNotify.js 所在目录；未设置时查找青龙标准脚本目录。
- 填写格式：`本地目录路径；业务请求不依赖通知模块。`

#### `LAOBAN_DRY_RUN`

- 所属脚本：`scripts/sudojia_laoban.js`
- 获取或设置：青龙环境变量中设置为 1 即启用完全断网预演。
- 填写格式：`1 表示预演；未设置时正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_laoban.js`
- 获取或设置：使用青龙已有通知配置，默认开启；需要关闭时设置此变量。
- 填写格式：`0、false、no、off 表示关闭，不区分大小写；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_laoban.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时依次检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；仅用于可选通知，不参与业务请求。`

#### `LONG_FOR_DRY_RUN`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：设置为 1 进行完全离线预演，通知也仅预演。
- 填写格式：`0 或 1，默认 0`

#### `LONG_FOR_ENABLE_LOTTERY`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：明确接受消耗抽奖机会后设置为 1，依次执行抽奖签到及一次抽奖。
- 填写格式：`0 或 1，默认 0`

#### `LONG_FOR_SIGN_ACTIVITY`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：从本人小程序签到请求的 activity_no 获取；默认保留上游历史签到活动 ID。
- 填写格式：`数字字符串`

#### `LONG_FOR_LOTTERY_ACTIVITY`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：从本人小程序抽奖请求的 activity_no 获取；默认保留上游历史抽奖活动 ID，可能已过期。
- 填写格式：`数字字符串`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：青龙全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_longfor.js`
- 获取或设置：填写青龙现有 sendNotify.js 所在目录；未设置时查找青龙标准脚本目录。
- 填写格式：`本地目录路径，仅用于可选通知`

#### `MALLCOO_DRY_RUN`

- 所属脚本：`scripts/sudojia_mallcoo.js`
- 获取或设置：手动设置为 1 开启完全断网预演，默认正式执行。
- 填写格式：`1 开启，其他值关闭`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_mallcoo.js`
- 获取或设置：手动设置，默认开启青龙通知。预演时仅记录通知摘要，不发送网络通知。
- 填写格式：`0、false、no、off 关闭，其他值开启`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_mallcoo.js`
- 获取或设置：可选填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知模块目录`

#### `MAWUW_DRY_RUN`

- 所属脚本：`scripts/sudojia_mawuwang.js`
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_mawuwang.js`
- 获取或设置：青龙全局通知开关，默认启用。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_mawuwang.js`
- 获取或设置：可选，填写已有青龙 sendNotify.js 所在目录；否则自动检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`目录路径，不包含文件名。`

#### `MIDEA_DRY_RUN`

- 所属脚本：`scripts/sudojia_midea.js`
- 获取或设置：离线验证时设为 1，正式任务删除或设为 0。
- 填写格式：`1 为完全离线预演，其他值为正式执行；预演不验证 Cookie，不发送通知，仅展示通知摘要。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_midea.js`
- 获取或设置：按需在青龙环境变量中配置，默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_midea.js`
- 获取或设置：仅当通知模块不在青龙标准路径时，填写自己已有 sendNotify.js 所在目录；无需为业务请求安装其他仓库。
- 填写格式：`可选目录路径；依次查找此目录、/ql/data/scripts、/ql/scripts。`

#### `MOTO_DRY_RUN`

- 所属脚本：`scripts/sudojia_moto.js`
- 获取或设置：预演时手动设为 1；正式运行删除该变量或设为 0。
- 填写格式：`1 表示完全无网络预演，其他值表示正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_moto.js`
- 获取或设置：青龙全局通知开关，默认开启。预演只生成摘要，不调用外部通知，以保证无网络。
- 填写格式：`0、false、no、off 关闭通知，忽略大小写；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_moto.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径，仅用于可选通知，不是业务依赖。`

#### `MXBC_DRY_RUN`

- 所属脚本：`scripts/sudojia_mxbc.js`
- 获取或设置：离线验证时手动设置为 1，正式运行时设为 0 或不设置。
- 填写格式：`1 表示完全断网预演；其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_mxbc.js`
- 获取或设置：在青龙环境变量中设置，默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_mxbc.js`
- 获取或设置：需要自定义通知位置时，填写可信的青龙 sendNotify.js 或 notify.py 所在目录；不设置时依次查找 /ql/data/scripts、/ql/scripts，最后尝试 Python 导入 notify。
- 填写格式：`本机可信通知模块目录的路径；业务执行不依赖该目录。`

#### `NAIXUE_DRY_RUN`

- 所属脚本：`scripts/sudojia_naixue.js`
- 获取或设置：手动设置为 1 开启完全离线预演，预演也模拟通知，不验证凭据有效性。
- 填写格式：`1 开启，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_naixue.js`
- 获取或设置：青龙环境变量中设置；默认开启。
- 填写格式：`0、false、no、off 关闭，大小写不限。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_naixue.js`
- 获取或设置：可选，填写现有青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录绝对路径。`

#### `NESTLE_TASK_GUIDS`

- 所属脚本：`scripts/sudojia_nestle.js`
- 获取或设置：先留空运行查询，从日志读取任务编号，并在小程序核对对应任务的内容、要求和风险；仅填入自己明确授权执行的任务编号。
- 填写格式：`每行一个任务编号，仅含英文字母、数字、下划线或连字符，最多128字符；白名单对所有账号生效，任一指定任务不在列表中则该账号失败。默认不提交任何任务。`

#### `NESTLE_DRY_RUN`

- 所属脚本：`scripts/sudojia_nestle.js`
- 获取或设置：本地预演时设置为 1。
- 填写格式：`1 表示完全断网模拟；其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_nestle.js`
- 获取或设置：青龙环境变量中配置；默认开启。
- 填写格式：`0、false、no、off（不区分大小写）关闭通知；断网预演仅展示通知摘要。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_nestle.js`
- 获取或设置：可选，填写已配置的青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知模块目录；仅通知使用，不作为业务运行依赖。`

#### `NFHK_DRY_RUN`

- 所属脚本：`scripts/sudojia_nfhk.js`
- 获取或设置：自行设置；预演时填写 1。
- 填写格式：`1 表示完全断网预演，其他值表示正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_nfhk.js`
- 获取或设置：青龙环境变量中设置，默认启用通知。
- 填写格式：`0、false、no、off 表示关闭，忽略大小写；其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_nfhk.js`
- 获取或设置：可填写现有青龙 sendNotify.js 所在目录；未配置时检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`通知模块目录绝对路径，非业务运行依赖。`

#### `OPPOSHOP_TASK_IDS`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：从官方任务列表确认任务 ID 及其副作用，只填自己同意执行的任务；黑卡和购物类型 6 始终跳过。默认空值，仅读取任务列表。
- 填写格式：`英文逗号分隔的数字任务 ID`

#### `OPPOSHOP_CUMULATIVE_REWARDS`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：手动核实当前活动奖励 ID 1327、1328、1329、1330 分别对应累计 3、5、10、15 天后设为 1；默认 0，避免跨活动误领。
- 填写格式：`0 或 1`

#### `OPPOSHOP_DRY_RUN`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：设为 1 启用完全断网的参数与流程预演；预演通知仅生成总结，不加载联网通知模块。
- 填写格式：`0 或 1`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：默认启用青龙通知；设为 0、false、no 或 off 可关闭。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_opposhop.js`
- 获取或设置：可选：填写青龙 sendNotify.js 所在目录；未设置时检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录绝对路径`

#### `PANG_GE_DRY_RUN`

- 所属脚本：`scripts/sudojia_pangge.js`
- 获取或设置：手动设置为 1 开启完全断网预演，正式执行时移除或设为 0。
- 填写格式：`1 或 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_pangge.js`
- 获取或设置：默认开启青龙通知；设置 0、false、no 或 off 关闭。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_pangge.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径`

#### `PAO_TEA_DRY_RUN`

- 所属脚本：`scripts/sudojia_paotea.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 为预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_paotea.js`
- 获取或设置：青龙全局通知开关，默认开启；预演也尝试本地通知模块，但禁止通知进程联网。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_paotea.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；否则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；仅通知使用，业务不依赖该目录。`

#### `SHYP_DRY_RUN`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：按需手动设置；完全断网预演，模拟接口结果，不表示线上成功。
- 填写格式：`0 或 1；默认 0`

#### `SHYP_ENABLE_FAVOR`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：按需手动设置；收藏文章并获取积分，默认关闭。
- 填写格式：`0 或 1；默认 0`

#### `SHYP_ENABLE_COMMENT`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：按需手动设置；公开发表评论并获取积分，默认关闭。
- 填写格式：`0 或 1；默认 0`

#### `SHYP_ENABLE_SHARE`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：按需手动设置；调用分享积分接口，默认关闭。
- 填写格式：`0 或 1；默认 0`

#### `SHYP_COMMENT_TEXT`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：自行填写适合公开发布的本地回退评论，不要包含个人信息。远程一言失败时使用；不设置则使用内置文本。
- 填写格式：`压缩空白后 1 至 280 个字符`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：青龙全局通知开关，默认开启。预演会尝试通知入口，但阻止其联网投递。
- 填写格式：`0、false、no、off 关闭，其他值开启`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_shmedia.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；默认查找 /ql/data/scripts 和 /ql/scripts。通知不可用或失败不影响业务退出码。
- 填写格式：`本机目录路径`

#### `SHUI_FEI_DRY_RUN`

- 所属脚本：`scripts/sudojia_shuifei.js`
- 获取或设置：手动设置为 1 可断网预演；不设置则正式执行。
- 填写格式：`1 表示预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_shuifei.js`
- 获取或设置：默认开启通知；设为 0、false、no 或 off 关闭。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_shuifei.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置则搜索青龙标准脚本目录。
- 填写格式：`本地目录路径`

#### `SSPANEL_DRY_RUN`

- 所属脚本：`scripts/sudojia_sspanel.js`
- 获取或设置：离线校验时设为 1，正式执行时设为 0 或不设置。
- 填写格式：`1 为断网演练，其他值为正式执行`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_sspanel.js`
- 获取或设置：使用青龙已有通知配置；默认开启。演练中的通知处理禁止联网。
- 填写格式：`默认 1；0、false、no、off 关闭（不区分大小写）`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_sspanel.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；默认依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径，仅用于可选通知，不影响业务运行`

#### `STAR_MOM_DRY_RUN`

- 所属脚本：`scripts/sudojia_starmom.js`
- 获取或设置：在青龙环境变量中设置。
- 填写格式：`1 开启完全断网预演；默认正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_starmom.js`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_starmom.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；默认查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机通知模块目录，仅用于可选通知。`

#### `TEBU_DRY_RUN`

- 所属脚本：`scripts/sudojia_tebu.js`
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演。
- 填写格式：`1 为预演，其他值为正式执行；预演不签到，不加载通知模块，只生成通知摘要。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_tebu.js`
- 获取或设置：在青龙环境变量中按需设置，默认启用。
- 填写格式：`0、false、no、off 关闭通知，其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_tebu.js`
- 获取或设置：可填写已有青龙 sendNotify.js 所在目录；未设置时依次检查 /ql/data/scripts、/ql/scripts。
- 填写格式：`本机通知模块所在目录的绝对路径，仅通知使用，业务不依赖此文件。`

#### `TILTA_ALLOW_LIKE`

- 所属脚本：`scripts/sudojia_tilta.js`
- 获取或设置：希望自动点赞社区文章时手动设置为1；默认0。
- 填写格式：`0或1`

#### `TILTA_DRY_RUN`

- 所属脚本：`scripts/sudojia_tilta.js`
- 获取或设置：离线验收时设置为1，正式执行设置为0或不设置。
- 填写格式：`0或1；预演包含通知模拟且完全不联网。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_tilta.js`
- 获取或设置：默认开启青龙通知；需要关闭时手动设置。
- 填写格式：`0、false、no、off（不区分大小写）关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_tilta.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径，仅用于可选通知；业务执行不依赖该文件。`

#### `TUC_DRY_RUN`

- 所属脚本：`scripts/sudojia_tuchong.js`
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演。
- 填写格式：`1 为预演；其他值或未设置为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_tuchong.js`
- 获取或设置：青龙全局通知开关，默认开启；预演只展示本地通知摘要，不加载发送模块。
- 填写格式：`0、false、no、off 关闭，大小写不敏感；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_tuchong.js`
- 获取或设置：可选：填写已有青龙 sendNotify.js 所在目录；未设置时依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径，仅用于可选通知集成；业务请求无外部文件依赖。`

#### `V2EX_DRY_RUN`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：青龙环境变量中手动设置，断网验证时设为 1。
- 填写格式：`1 启用；其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：青龙环境变量中按需设置，默认开启通知。
- 填写格式：`0、false、no、off 关闭，不区分大小写；预演仅模拟通知，不发送网络请求。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：如通知模块不在标准青龙目录，填写已有 sendNotify.js 所在目录；不下载或安装任何文件。
- 填写格式：`本地通知模块目录；未设置时搜索 /ql/data/scripts 和 /ql/scripts。`

#### `WNNA_DRY_RUN`

- 所属脚本：`scripts/sudojia_wnna.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_wnna.js`
- 获取或设置：按需设置，默认启用青龙通知。断网预演仅输出通知摘要，不加载通知模块。
- 填写格式：`0、false、no、off 关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_wnna.js`
- 获取或设置：青龙通知模块不在默认目录时，填写包含 sendNotify.js 的目录。默认查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径，可选。`

#### `XHN_DRY_RUN`

- 所属脚本：`scripts/sudojia_xhn.js`
- 获取或设置：手动设置为 1 启用完全断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xhn.js`
- 获取或设置：青龙环境变量中设置；默认开启。
- 填写格式：`0、false、no、off 关闭通知，忽略大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xhn.js`
- 获取或设置：可选填写青龙 sendNotify.js 所在目录；未设置时依次查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；通知不可用不影响业务退出码。`

#### `XWGAME_DRY_RUN`

- 所属脚本：`scripts/sudojia_xiangwan.js`
- 获取或设置：预演时设为 1；正式运行时设为 0 或不设置。
- 填写格式：`1 为完全断网预演，不登录、不签到、不读取或写入缓存、不调用通知模块；仅生成脱敏通知摘要。`

#### `XWGAME_TOKEN_CACHE`

- 所属脚本：`scripts/sudojia_xiangwan.js`
- 获取或设置：需要复用 Token 时，设置到本人可写且受保护目录内的缓存文件路径；默认不启用。不兼容旧版明文手机号键名缓存，请勿直接复用。
- 填写格式：`可选文件路径；新文件权限为 0600，以手机号摘要索引；拒绝不安全文件。缓存验证失败回退密码登录。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xiangwan.js`
- 获取或设置：使用青龙已有通知配置；默认开启。
- 填写格式：`0、false、no、off 关闭，其余开启；预演只生成摘要，不发送网络通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xiangwan.js`
- 获取或设置：可填写青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`可选目录路径；通知模块仅用于通知，业务请求由本脚本独立实现。`

#### `XIAOMI_COMM_DRY_RUN`

- 所属脚本：`scripts/sudojia_xiaomi_community.js`
- 获取或设置：在青龙环境变量中设置为 1 可完全断网预演。
- 填写格式：`1 为预演，其他值为正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xiaomi_community.js`
- 获取或设置：使用青龙现有通知配置，默认启用；预演只模拟通知以保证不联网。
- 填写格式：`0、false、no、off 关闭，忽略大小写；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xiaomi_community.js`
- 获取或设置：可选，填写青龙已有 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 和 /ql/scripts，缺少模块不影响业务退出码。
- 填写格式：`通知模块目录路径。`

#### `XINXI_DRY_RUN`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设置为 1 进行完全断网预演；默认 0。
- 填写格式：`0 或 1`

#### `XINXI_FREE_DRAW`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：愿意参加活动 71 的免费抽奖时设置为 1；默认关闭，每次最多抽一次，免费次数为零时不抽奖。
- 填写格式：`0 或 1`

#### `XINXI_REWARD_TASKS`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：同意提交分享任务记录和商城浏览奖励时设置为 1；默认关闭；分享接口仅记账，不发布文本。
- 填写格式：`0 或 1`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：使用青龙已有通知配置；默认开启。预演只显示通知摘要，确保不联网。
- 填写格式：`0、false、no、off 关闭；其他值开启`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：可选：填写本机青龙 sendNotify.js 所在目录；否则自动查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径，仅用于通知，业务逻辑无需此模块`

#### `XPFARM_TASK_IDS`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：在小程序任务页及本人请求中核实任务编号和动作含义后设置；上游仅明确编号 2 为广告任务，其余含义无参考证据，禁止盲目启用。
- 填写格式：`1–16 的整数，英文逗号分隔；默认空，不自动执行或领取未知任务。`

#### `XPFARM_FERTILIZER_LIMIT`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：确认愿意消耗肥料后设置本次最多施肥次数。
- 填写格式：`0–100 整数，默认 0；启用后可能立即消耗肥料。`

#### `XPFARM_WATER_LIMIT`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：确认愿意消耗水滴后设置本次最多浇水次数。
- 填写格式：`0–100 整数，默认 0；启用后可能立即消耗水滴和肥力。`

#### `XPFARM_DRY_RUN`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：离线验证时设为 1。
- 填写格式：`1 为断网预演，其他值为正式运行；预演不执行业务请求或外部通知。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：使用青龙通知设置；需要关闭通知时设置为 0。
- 填写格式：`默认 1；0、false、no、off 忽略大小写时关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xpfarm.js`
- 获取或设置：可选，填写青龙 sendNotify.js 所在目录；未设置时检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机通知模块目录，仅用于通知；模块缺失或失败不影响业务退出码。`

#### `ZNDS_VISIT_UID`

- 所属脚本：`scripts/sudojia_znds.js`
- 获取或设置：可选：从希望访问的用户空间链接读取 uid 参数。应选择本人账号以外的目标，留空则跳过。
- 填写格式：`单个数字公开 UID，所有账号共用；访问可能产生足迹或奖励。`

#### `ZNDS_DRY_RUN`

- 所属脚本：`scripts/sudojia_znds.js`
- 获取或设置：需要断网预演时设置为 1；正式运行时不设置。
- 填写格式：`1 表示断网预演，通知仅模拟，不代表实际签到成功。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_znds.js`
- 获取或设置：使用青龙已有通知配置，默认启用。
- 填写格式：`0、false、no、off（不区分大小写）关闭，其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_znds.js`
- 获取或设置：可选：填写青龙 sendNotify.js 或 notify.py 所在目录；未设置时自动搜索青龙标准目录及 Python 模块。
- 填写格式：`本机通知模块目录，仅用于通知，不是业务运行依赖。`

#### `ZX_ICE_DRY_RUN`

- 所属脚本：`scripts/sudojia_zxice.js`
- 获取或设置：在青龙环境变量中手动设置；用于完全断网预演。
- 填写格式：`1 开启预演，其他值执行正式任务。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_zxice.js`
- 获取或设置：在青龙环境变量中设置全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_zxice.js`
- 获取或设置：可选，填写已配置好的青龙 sendNotify.js 所在目录；未设置时查找青龙标准脚本目录。
- 填写格式：`本地目录路径；只用于通知，业务请求不依赖此目录。`

#### `TIE_BA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：旧版兼容变量，获取方法与 TIEBA_COOKIE 相同；仅当未设置 TIEBA_COOKIE 时读取。
- 填写格式：`每个账号占一个非空行；单行填写 BDUSS 值或包含 BDUSS 的完整 Cookie。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_DRY_RUN`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；设为 1 可进行完全断网的配置预演。
- 填写格式：`启用值为 1、true、yes 或 on，不区分大小写。`

#### `TIEBA_VERBOSE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；按需设为 1，可在正式执行时显示贴吧名称和脱敏错误详情。
- 填写格式：`启用值为 1、true、yes 或 on，不区分大小写。`

#### `TIEBA_DELAY_MS`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；用于调整连续签到请求之间的固定间隔。
- 填写格式：`整数毫秒，脚本会限制在 500 至 10000 之间，默认 1200。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；青龙通知默认开启，设为 0 可关闭。
- 填写格式：`0、false、no 或 off 表示关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：仅在青龙通知脚本不位于标准目录时填写 notify.py 所在目录。
- 填写格式：`本机目录路径，目录内应包含 notify.py。`

#### `TSTHB_DRY_RUN`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置为 1 启用完全断网预演；默认 0。
- 填写格式：`1、true、yes、on 表示启用。预演不执行等待、HTTP 或通知模块，仅展示通知摘要。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置；保留维护版默认 true。限时验证和需要立即执行时设置 false。
- 填写格式：`忽略大小写，只有 true 启用随机延迟，其他值关闭。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置随机等待上限；保留维护版默认 3600 秒。
- 填写格式：`非负整数，单位秒；随机延迟开启时在 0 至该值之间随机选择并显示倒计时。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：自行设置青龙通知开关；默认 1。通知不可用不影响业务退出码。
- 填写格式：`0、false、no、off 关闭，忽略大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：可选，填写已有青龙 notify.py 所在目录；未配置时尝试导入 notify，并查找 /ql/data/scripts 和 /ql/scripts。签到本身不依赖通知文件。
- 填写格式：`可选目录路径；不会下载安装通知组件。`

#### `TY_DRY_RUN`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：预演时设为1；默认0。
- 填写格式：`1、true、yes、on 启用完全断网预演`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：按需要设置；默认true。验证接口时可设false，避免随机等待。
- 填写格式：`true启用随机延迟；其他值关闭`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：按需要设置随机等待上限；默认3600秒。
- 填写格式：`0～86400的整数；账号间另外随机等待10～30秒；预演均不等待`

#### `TY_ACCOUNT_TIMEOUT`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：按网络条件设置；默认60秒，每账号独立总时限，不包含随机等待。
- 填写格式：`10～600的整数；单次请求另有15秒超时，不自动重试`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：青龙环境变量中设置；默认1。
- 填写格式：`0、false、no、off关闭通知；其余启用；预演只生成摘要而不传输`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：可选：填写青龙现有 notify.py 所在目录；也会尝试导入 notify 及青龙标准目录。
- 填写格式：`本机通知目录路径；不可用或发送失败不改变业务退出码`


## 验证与兼容性

- `scripts/aliyunpan_checkin.py`：SHA-256 `4b1884c921accb1fe4555d1eca158f6ab1acbea919d95c32e0fa1d92df7a3c00`；live 业务成功证据位于 `projects/checkin/validation/9c6fa7a75879fa8b`。
- `scripts/atxyq.py`：SHA-256 `6d8723d7248ad77b80ee7a77734038bb6dae5c87cdebc86da19af1319553fcf1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/6b6ae91490051bce`。
- `scripts/baiduwangpan_checkin.py`：SHA-256 `e9c658f4544427bd94ab4da74a724038d1f849c8b9665464ded6e8a1c4dd2c18`；live 业务成功证据位于 `projects/checkin/validation/d9230b69d9462c7c`。
- `scripts/bsly_draw.py`：SHA-256 `21ee297f54d13d8f725fc2419d1eeba7d34873fd9e321d5431dcbce9cb352664`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/28b170786df4dff2`。
- `scripts/bwcj.py`：SHA-256 `ae20e692177d7102468ed3ddc462576f39fd2c81ea51a9dad626e138700ac4af`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0367e0709855a394`。
- `scripts/cdrail.py`：SHA-256 `5caed175e6b1ff5b1033fbbd59105a71dfb952c8dd79bc9b92f3d354a69e5225`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7389d13167df31b6`。
- `scripts/cfmoto_checkin.py`：SHA-256 `15ecc5e482af800b18360374359667392176fe88ab77c7950509da115f09f07a`；live 业务成功证据位于 `projects/checkin/validation/0ba7bb41fd4c339c`。
- `scripts/ddnsto.py`：SHA-256 `a36378f008a43fa3824429fe8650bb693f256aba081914b5254cc51fcfe58087`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e7b851436459bf8f`。
- `scripts/durex.py`：SHA-256 `dcfd65a77d774a5ea04efb135a56f675f531c6fd11d770279ec6120cbd8e025c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5bc8db2e6a36d14b`。
- `scripts/ikuuu_checkin.py`：SHA-256 `6b8a4428f238d9a1476562c1f347804ee0bc55a58ea399fd14fa334ac86f9ed7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7ea70c9e9d579efb`。
- `scripts/kuaishou_reward_status.py`：SHA-256 `b727e90b3326ec58b00281be13ad27879cb75be0af9a9c5c0a93fe3fbd8aa305`；live 业务成功证据位于 `projects/checkin/validation/ks_cleanroom_v1`。
- `scripts/main.py`：SHA-256 `ea3bb416264f093933b3bf07dbc40a5dc02eeb4e8fc02d1626f2db0e4ac1ae17`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c0137ce8eaf72832`。
- `scripts/nga_checkin.py`：SHA-256 `15a008af4247c2904f9acb1acff562d2062fbc6b1a606da368fc6d6b97fe45cc`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4e0cf5e129fb12a4`。
- `scripts/nodeseek_checkin.py`：SHA-256 `bc4d97b59c92bda264dd477193a902490e25641b333bfe8feab8406d233ef505`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4196e654f2a752f8`。
- `scripts/passnat_checkin.py`：SHA-256 `378ef21771663547b6f58d6d66d4639e79047fee044815af7c84d137b4bf2aaf`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7e0ea7b66d8114d3`。
- `scripts/quark_signin.py`：SHA-256 `2487b5cd4a53457b8d0ce2000f154668060333a0483b846a52a9d329da18a5bb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/18c47e12eda9864c`。
- `scripts/sfsu_checkin.py`：SHA-256 `d48a9999e72bbea15c0de43dc537ab4f37f63c5a6fb38708098482f92761affb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/19b2285cc7b8a82e`。
- `scripts/smzdm_checkin.js`：SHA-256 `80bd84a5e3551cc10e43d22bcaef72a7d799ca7754ce934f0f93217ce83300d4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/621df252c315f2d1`。
- `scripts/sudojia_33agilestudio.js`：SHA-256 `7677c43b5720b0556f6d0b2949405b7c91d218dbc5d020ad6be0dd46ce2308d8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/28da2f8c0aec7716`。
- `scripts/sudojia_allgirls.js`：SHA-256 `c553619d6534fdf01df62c381df54bfb5557104402a27aa037bf381b075d8934`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e8776198aafad33e`。
- `scripts/sudojia_amx.js`：SHA-256 `74c9e4adc427ad5b11fa3790b55857eb5a928af78cabc6c0d7c7d04ee8694c65`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2afe8ef7e443b92b`。
- `scripts/sudojia_bananavideo.js`：SHA-256 `0406e66e2c06dd0ff5f9b74c79cd2bba0f41b104b417a0c40f08830bf023dbb0`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/218007282cf9754f`。
- `scripts/sudojia_beiyinmei.js`：SHA-256 `7829fb15cfeb7cd36abbc90c383ca2774ac04804b3c03f77e2957b87ed3b0195`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e09c8b13ee16c8db`。
- `scripts/sudojia_botanystar.js`：SHA-256 `49514a5ef472c0344b18fd9a97ece749a06dbb354e83ec3972b74fcd8293fbd2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3a5acb1743389e26`。
- `scripts/sudojia_bwtea.js`：SHA-256 `6c7a37e9d10e71acbf0f22997db91262260bfb5b30c0da79c90b0b1c0fe7baec`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5d764238c373f4ce`。
- `scripts/sudojia_colorful_mall.js`：SHA-256 `d8d73f9403e695405a0ed89a282f242158c47aadb97f8576d4049bb94a1146e9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/246de3f61ba99194`。
- `scripts/sudojia_flyant.js`：SHA-256 `8e3e229e4db887c4588444e53211ef4610a82cae51cb463409a4bb06cb831c03`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4fb882fdbc0ba03a`。
- `scripts/sudojia_fnnas.js`：SHA-256 `4106209f1efdb73b3c49564c0ea186123ee5c04bc81f209dcd0ac561c6b6d21d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bab33a90ea57e852`。
- `scripts/sudojia_hgf.js`：SHA-256 `7a2fc3f49f3bb53dd24a27db4453415048f8b5db6640c7a3adbc1bf3c2b406b8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ad46a268a74b34b0`。
- `scripts/sudojia_hlzj_game.js`：SHA-256 `cb6afdaa59ce18500e46bb208ba48c468eca19656abb8b12cd79db5a501bbbb8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4d08d343f131700e`。
- `scripts/sudojia_hzhfp.js`：SHA-256 `3ed150270405b542635e468b2ab1eaf8902dcc9fa41fb6a46b4cef62002a6cab`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/400481011873c4b0`。
- `scripts/sudojia_instax.js`：SHA-256 `815b3148db43b02667a8b792285e4846925af30866e78ff5a1fec5804c29e377`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e229880f6ad33d6f`。
- `scripts/sudojia_jhcard.js`：SHA-256 `ac86d6cc9fda1657bb61169b9feecbb9cadba6a61b95a92bec66912155d2eff6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0dc8d7553d45c649`。
- `scripts/sudojia_jiangshan.js`：SHA-256 `6aeecd07cf2173fa8e1a7775bd17849dd373ce9ca102ba5d5e5e48b9af78f04d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/db8583cdb3a987c1`。
- `scripts/sudojia_jindian.js`：SHA-256 `d9c3bef3a86ccd7da990e856f7567029c688349b162cb554fd9b8407bd515f22`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/1ee8bcd72ce624b6`。
- `scripts/sudojia_jlc.js`：SHA-256 `2048a9c7c28a9c35a13f26ba694c6b6608c12aa80e2c77565088ab0b5e778ad3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/78d21d1077d4682f`。
- `scripts/sudojia_jlc_yj.js`：SHA-256 `4e996c250a1f8a9db7ad1ef10a450599856f38c7518038d8a0b42f9b29cf2451`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/38602005c4e13646`。
- `scripts/sudojia_juejin.js`：SHA-256 `a3ab6439b1c72f4195f35551584cb573e8f9d0515eadd0cb1e60cd712436ea36`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f86741e6210934e9`。
- `scripts/sudojia_kozbs.js`：SHA-256 `a9390adda3bb8938f8d40627ede49a6106dba6267805d7c285f6024e36ef6f58`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/34763140840b492a`。
- `scripts/sudojia_ktgzs.js`：SHA-256 `180d6b848c37e9703d05e65962b1eaf2200052389c048b88f739381b7270346e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3c1b078ac7332577`。
- `scripts/sudojia_kukahome.js`：SHA-256 `e7081807d92d65a4516d0d1c2c6359451127abbed1f4fffbba0f5e1d645075da`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/cea8801e001e143d`。
- `scripts/sudojia_kuro.js`：SHA-256 `be7c42c79d74c6f7586588a793084df541257e17fb784f8be817afd5bd95765d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c4e95d44d1608371`。
- `scripts/sudojia_laoban.js`：SHA-256 `39e4e4100e0b82ac9c308d03855d22caaaf0efe0377d7f0ecf4e7d83f899d351`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/75b0acfeb8163b13`。
- `scripts/sudojia_longfor.js`：SHA-256 `33edfe8a54af9a0b7612b5700a2a2a6bf83e80a556481bc021369adaf0c5f3ad`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a4edb286cd8742e3`。
- `scripts/sudojia_mallcoo.js`：SHA-256 `b5821afa069beb30c1be78bf64dd693a82ee253b2e55105d44d42dd6becdcc30`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7817ed50f25e649b`。
- `scripts/sudojia_mawuwang.js`：SHA-256 `133423898018d04a1784a7cf197c143785cdb359002ed09b826684e793f18b80`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/125dbe5e1b6b8274`。
- `scripts/sudojia_midea.js`：SHA-256 `c474e087bd04b25b5b67faa27c649aec711da38b906cf7f8a969210e2c9061b4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4d2bfc3b3a861962`。
- `scripts/sudojia_moto.js`：SHA-256 `1c73ab0fa75d3ca74dd40f04891ec43fa7d8853eb3866b6dd43cd0939e183363`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2e1e25aaedb9b2c3`。
- `scripts/sudojia_mxbc.js`：SHA-256 `9c2a5be7246f6fbf3ed44f52e358102e649f410f5b4219df8b61075b9e0e7612`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8898c6203ce46def`。
- `scripts/sudojia_naixue.js`：SHA-256 `754c1557511faa7d5ae360b58a2f7e079ff87e68a92fea15e89e5458bfa43756`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9485042a5b621baf`。
- `scripts/sudojia_nestle.js`：SHA-256 `98ba9fa7508d12ac34f2f91c89c20a3354659412c206df72cb7378f373e83e5d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e68269710bb6fed2`。
- `scripts/sudojia_nfhk.js`：SHA-256 `267c19e71999efaddbbd94c7293565b4e37f91f8deac237b6f88fdd20f321e8f`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8c6a0abab760b1dc`。
- `scripts/sudojia_opposhop.js`：SHA-256 `a26cac12229f3c18c37e5557b0ea130b8025ea86c967b5dd8460c91b89cc663d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/11bf36237211e761`。
- `scripts/sudojia_pangge.js`：SHA-256 `4a89dd87925b538c497735bc2a2a45c84b10d5f1658a177922d28738873a63a0`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/75d3da7186c8c51b`。
- `scripts/sudojia_paotea.js`：SHA-256 `9a497af082be58ef72bfa201bc722141d50a9f81c1e8722776a2b010e9f5be19`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/be649dd5fba997a7`。
- `scripts/sudojia_shmedia.js`：SHA-256 `0bdd067ab5f7eb66e62fce27037da779ed6f050e9c81cb20dae010a4f8a4bbd1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b9c2b0f38de689f1`。
- `scripts/sudojia_shuifei.js`：SHA-256 `dd28f0ff5164c33d9b3db09d1214c9c46ee429180edf34dfd7f2fdeb70c9397a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0aecb3979149b2cc`。
- `scripts/sudojia_sspanel.js`：SHA-256 `1055ccec4def07a28137aee50d995f6650d6918197b0d9ff7be7508ed5281ca2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3ab685f53b0a5cc0`。
- `scripts/sudojia_starmom.js`：SHA-256 `bc2b70cfb62513c69d904e375dce06bbc55b7592b9131cea78a2a1e894bc1b29`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4506301c45293563`。
- `scripts/sudojia_tebu.js`：SHA-256 `25c0e6a616e7945d13727f2326b14a059c89cece3405730c8999a16480024428`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a2b79c7df4dc31e7`。
- `scripts/sudojia_tilta.js`：SHA-256 `ca9c192577ffee68ddc1083e55704065dac8f6f756f2d3af1f4fc99e03565d22`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8a2853d90ebdcb0c`。
- `scripts/sudojia_tuchong.js`：SHA-256 `cdc3e24cb80e5424179994733a38c773a31e05e91eb357a0d54e1fd47d32e270`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0554aeea00a7519f`。
- `scripts/sudojia_v2ex.js`：SHA-256 `3bab10b2632bd44e16b758b07d75b859e82710d14b6b5236be377a829c57f4ab`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/705cf315f5da6907`。
- `scripts/sudojia_wnna.js`：SHA-256 `776fd6f05d881afb02e5c070096ab8909a638f944e548065d702ae7e1bb2dd72`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/364d0c6592e14300`。
- `scripts/sudojia_xhn.js`：SHA-256 `b0131f2d77c0d1f5ae6271d2a7604798ee3313db307e23390343d2d5e316abbd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b86681a8e89e05c0`。
- `scripts/sudojia_xiangwan.js`：SHA-256 `692566ebd5403b42b7671029cf12e1d993ebc6199d8ae704fd3bc489b9069ed7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d59346ef3ccb8591`。
- `scripts/sudojia_xiaomi_community.js`：SHA-256 `2426f49711019ec8e7fe8dc664362df99aa478c1828bd5d5f48c331dbb2a88dd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8b06f8c5b53252cf`。
- `scripts/sudojia_xinxi.js`：SHA-256 `d1124649c529854997bf2db59808f7e756510e5ed4e0d69a3d727f9b6c8d47f8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/83f21cfa63eab18f`。
- `scripts/sudojia_xpfarm.js`：SHA-256 `ffa9878cc55005e28061ca97009b8ffa7c48ce01144b325d0354d499c28a897d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9705540ac69a7c3e`。
- `scripts/sudojia_znds.js`：SHA-256 `e642ddf42719ca2ac4e37a94856f3c35e08307bc0b47d993bd5a1a83eb13eba1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e69a67d8a3d7b7a9`。
- `scripts/sudojia_zxice.js`：SHA-256 `eb50f784e85263452ae010edf81d6b0e1d6c864532f2c6f1a170aa168ddc8c5d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/eb4b0810d476bc5e`。
- `scripts/tieba_checkin.py`：SHA-256 `c19c152b7240df266352493f048f0580710c5c2d1f7c2a62a52922025064d912`；live 业务成功证据位于 `projects/checkin/validation/e608052390d250da`。
- `scripts/tsthb_checkin.py`：SHA-256 `f1f423f22e8134fb3080600f07293746eeb4d05783ec1778f489174dc1166d4c`；live 业务成功证据位于 `projects/checkin/validation/82616d06df4e5f53`。
- `scripts/ty_netdisk_checkin.py`：SHA-256 `c35e0283ba47fa3652469504e70a40383c7fc0729a6cee7e96f1cf65383ad0f7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/70f2505a78eb7276`。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。

## 副作用与风险

- `scripts/aliyunpan_checkin.py`：正式执行时为每个账号完成阿里云盘会员签到；正式执行时刷新账号访问令牌，并可能轮换刷新令牌；明确启用持久化时，将当前刷新令牌原子写入配置的本地文件。
- `scripts/atxyq.py`：默认每日签到，记录签到并可能增加积分。；默认领取普通任务奖励，可能增加积分。；开启 ATXYQ_LIKE 后对最多两篇文章点赞并取消点赞。；开启 ATXYQ_POST 后发布公开校园动态；配套图片参数存在时登记本人已有图片。；atxyqDel 非零时删除本人最近十篇列表内帖子。；开启 ATXYQ_HELP_LIKE 后为明确指定的帖子点赞。；开启 ATXYQ_INVITE 后创建所选邀请关系。；正式运行且通知开启时向已配置青龙通知渠道发送脱敏总结。。
- `scripts/baiduwangpan_checkin.py`：为每个已配置的百度网盘账号执行每日会员签到；为每个已配置的百度网盘账号提交每日会员问题答案；在通知开启且青龙通知模块可用时发送一条脱敏任务汇总通知。
- `scripts/bsly_draw.py`：实跑抽奖会消耗抽奖机会，并可能产生奖品或奖励记录；实跑开启通知时向青龙配置的通知渠道发送脱敏任务摘要。
- `scripts/bwcj.py`：新版签到产生签到记录及服务端发放的积分或奖励。；显式开启旧版签到后产生旧版签到记录及服务端奖励。；正式运行时通过青龙配置的通知渠道发送脱敏任务总结。。
- `scripts/cdrail.py`：调用签到接口，完成每日签到并可能增加积分；正式模式通过青龙通知模块发送脱敏结果摘要。
- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容；最多产生三次公开评论、三次点赞和三次分享任务记录；发帖和评论前访问第三方一言接口获取公开随机文本，不发送春风动力账号凭据。
- `scripts/ddnsto.py`：真实执行时创建七天免费套餐订单；真实执行时将订单套餐绑定到指定路由器并延长套餐到期时间；启用通知且青龙模块可用时发送脱敏任务通知。
- `scripts/durex.py`：每日签到改变签到状态并可能获得积分；开启分享后上报活动分享记录并可能获得奖励；开启抽奖后参与活动并可能消耗抽奖机会或积分。
- `scripts/ikuuu_checkin.py`：登录 ikuuu 并创建会话；提交每日签到，可能增加账号流量；实时运行时可能通过青龙通知渠道发送脱敏汇总。
- `scripts/kuaishou_reward_status.py`：。
- `scripts/main.py`：正式运行时在显式指定目录创建日期子目录并保存已验证的壁纸文件；不覆盖已有文件。；正式运行且启用通知时，调用青龙通知模块发送脱敏总结。。
- `scripts/nga_checkin.py`：提交NGA每日签到；启用日常任务选项时增加任务计数；启用视频任务选项时增加视频任务计数并可能获得奖励；启用分享任务选项时记录分享事件并领取奖励。
- `scripts/nodeseek_checkin.py`：成功请求会记录 NodeSeek 当日签到并可能增加鸡腿余额；启用青龙通知时会向已配置的通知渠道发送脱敏任务汇总。
- `scripts/passnat_checkin.py`：向 PassNAT 提交每日签到并可能增加账号流量。
- `scripts/quark_signin.py`：实时模式下为尚未签到的账号完成每日签到并领取存储空间奖励；实时模式下启用通知时通过青龙发送脱敏任务摘要。
- `scripts/sfsu_checkin.py`：执行每日签到；完成符合安全规则的积分及丰蜜任务并领取奖励；进行丰蜜大冒险并在容量不足时扩容；在 SF_AUTO_COUPON=1 时创建一笔生活特权券领取订单；在会员日窗口领取可用邀请奖励、消耗免费抽奖次数、领取任务奖励、合成并提取红包。
- `scripts/smzdm_checkin.js`：在什么值得买账号上执行每日签到并改变当日签到状态；满足条件时领取连续签到额外奖励并改变账号奖励状态。
- `scripts/sudojia_33agilestudio.js`：登录建立账户会话；提交每日签到，按服务端规则获得积分；正式运行且启用通知时，通过青龙通知模块发送脱敏任务摘要。
- `scripts/sudojia_allgirls.js`：未签到时执行每日签到，可能获得平台签到积分。
- `scripts/sudojia_amx.js`：未签到时执行每日签到，可能获得积分。
- `scripts/sudojia_bananavideo.js`：每日签到及任务奖励可能增加金币。；登记广告点击、下载请求、视频播放和二维码保存任务；不实际下载视频或保存二维码文件。；仅显式启用时添加随机视频收藏。；仅显式启用时公开发布评论。；登录创建服务端会话；启用通知时发送脱敏结果通知。。
- `scripts/sudojia_beiyinmei.js`：实际执行每日签到，可能领取签到奖励。；开启通知且模块可用时发送脱敏任务摘要。。
- `scripts/sudojia_botanystar.js`：正式执行登录以创建账号会话；提交每日签到并领取绿星币奖励；提交两项浏览任务并领取绿星币奖励；正式运行默认通过青龙通知模块发送脱敏汇总，可关闭。
- `scripts/sudojia_bwtea.js`：未签到时提交新版每日签到，可能增加积分；启用通知时通过青龙通知渠道发送脱敏任务总结。
- `scripts/sudojia_colorful_mall.js`：登录换取凭据并刷新登录时间；旧版和新版签到可能增加积分及改变签到记录；仅显式开启评论时公开发布社区评论并可能获得积分；通知开启且模块可用时发送脱敏任务总结。
- `scripts/sudojia_flyant.js`：每日签到领取奖励；提供真实步数后兑换环保豆；显式启用抽奖后消耗环保豆并获取抽奖结果；显式启用后参与早起打卡；显式启用早起报名，可能扣除环保豆；正式模式发送青龙通知。
- `scripts/sudojia_fnnas.js`：执行本站每日打卡，可能获得论坛奖励；通知启用且模块可用时发送任务摘要。
- `scripts/sudojia_hgf.js`：每日签到会更新签到记录并可能获得酒币。；提交浏览任务并领取相应任务奖励。；开启通知时，正式运行会通过青龙配置的渠道发送脱敏任务总结。。
- `scripts/sudojia_hlzj_game.js`：领取每日游戏电力奖励。；执行每日签到并领取奖励。；显式开启 HLZJ_USE_POWER 后消耗电力推动游戏进度并领取宝箱。。
- `scripts/sudojia_hzhfp.js`：调用每日签到接口，更新签到记录并可能获得签到积分；正式执行且通知开启时，通过青龙通知模块发送任务汇总。
- `scripts/sudojia_instax.js`：签到改变服务端签到记录，并可能增加积分；显式开启抽奖后消耗抽奖机会，并产生中奖记录。
- `scripts/sudojia_jhcard.js`：签到并领取服务端发放的积分；仅在账号显式追加 #true 时发表五次公开评论。
- `scripts/sudojia_jiangshan.js`：签到及阅读可能增加积分、经验和任务进度；显式启用 share 后上报分享任务并改变进度；显式启用 comment 后发表公开评论；显式启用 like 后点赞文章；显式启用 local 后上报本地服务任务并改变进度。
- `scripts/sudojia_jindian.js`：对尚未签到的账号执行每日签到，可能增加积分。
- `scripts/sudojia_jlc.js`：正式执行时进行每日签到；仅 JLC_CLAIM_REWARD=1 时领取官方默认奖励；正式执行且通知开启时发送青龙任务通知。
- `scripts/sudojia_jlc_yj.js`：正式执行时进行硬件开源平台每日签到；正式执行且通知开启时发送青龙任务通知。
- `scripts/sudojia_juejin.js`：尚未签到时提交每日签到，领取矿石奖励；正式运行且启用通知时发送青龙任务摘要。
- `scripts/sudojia_kozbs.js`：未签到时提交每日签到，可能增加账号积分和签到记录。；通知开启且模块可用时向已配置的通知渠道发送脱敏任务汇总。。
- `scripts/sudojia_ktgzs.js`：正式运行调用每日签到接口，产生签到记录及服务端奖励积分。
- `scripts/sudojia_kukahome.js`：每日签到可能增加账号积分并更新连续签到记录；正式模式通过青龙发送脱敏任务结果通知（可关闭）。
- `scripts/sudojia_kuro.js`：社区签到并领取签到库洛币；鸣潮角色每日签到；战双角色每日签到。
- `scripts/sudojia_laoban.js`：执行每日签到并增加服务端核定积分；领取可领取的连续签到积分奖励；记录商品及资讯浏览，可能触发浏览任务积分奖励；按原接口同步会员信息与会员积分；通知开启且可用时向青龙配置的渠道发送脱敏任务总结。
- `scripts/sudojia_longfor.js`：每日签到可能增加成长值；启用抽奖流程后，抽奖签到可能增加抽奖机会；启用抽奖流程后，一次抽奖消耗机会并可能获得奖励；正式运行且通知开启时发送青龙汇总通知。
- `scripts/sudojia_mallcoo.js`：执行每日签到并按服务规则获得积分；正式运行时通过青龙通知渠道发送任务摘要。
- `scripts/sudojia_mawuwang.js`：未签到时参与签到活动，可能获得积分或签到奖励；正式模式通过青龙已配置渠道发送脱敏通知。
- `scripts/sudojia_midea.js`：正式执行时提交每日签到，可能获得积分或成长值；通知开启且模块可用时，向青龙配置的通知渠道发送脱敏摘要。
- `scripts/sudojia_moto.js`：正式运行提交每日签到，可能获得能量奖励；不自动重试提交；正式运行时通过青龙通知模块发送脱敏任务摘要（可关闭）。
- `scripts/sudojia_mxbc.js`：正式运行执行蜜雪冰城每日签到，可能增加雪王币并更新连续签到天数。；正式运行通过青龙通知模块向用户配置的通知通道发送脱敏任务摘要（可关闭）。。
- `scripts/sudojia_naixue.js`：未签到时提交每日签到，可能增加签到记录及奖励。；开启通知时通过现有青龙通知模块发送脱敏任务总结。。
- `scripts/sudojia_nestle.js`：显式配置 NESTLE_TASK_GUIDS 后，向任务完成接口提交授权任务，可能改变任务完成状态和巢币奖励。；正式运行且通知开启时，通过青龙通知模块发送脱敏任务摘要。。
- `scripts/sudojia_nfhk.js`：执行每日签到并领取服务端对应签到权益；启用通知时发送脱敏任务总结。
- `scripts/sudojia_opposhop.js`：每日签到可能增加积分；显式启用白名单任务后上报完成状态并领取积分奖励；显式启用累计奖励后领取达标奖励；正式执行结束时通过青龙通知模块发送脱敏总结（可关闭）。
- `scripts/sudojia_pangge.js`：每日签到并领取服务端发放的积分；正式运行时按通知开关发送青龙结果通知。
- `scripts/sudojia_paotea.js`：对明确配置的活动执行每日签到；启用通知时通过青龙通知模块发送脱敏总结。
- `scripts/sudojia_shmedia.js`：签到及阅读、视频任务可能增加账号积分并改变任务进度；显式开启后收藏文章并可能获取积分；显式开启后公开发表评论并可能获取积分；显式开启后调用分享积分接口并改变任务进度；正式运行时通过青龙已配置的通知渠道发送脱敏总结。
- `scripts/sudojia_shuifei.js`：未签到时提交签到，可能增加积分及连续签到天数；正式运行时按通知开关发送青龙通知。
- `scripts/sudojia_sspanel.js`：登录创建站点会话；执行每日签到并可能获得站点流量奖励；开启通知时通过青龙已配置渠道发送任务汇总。
- `scripts/sudojia_starmom.js`：每日签到及获取积分；提交五项浏览任务的开始和完成记录并领取积分；正式执行时发送青龙任务通知。
- `scripts/sudojia_tebu.js`：正式执行时提交每日签到并可能获得积分；启用通知且模块可用时发送任务汇总通知。
- `scripts/sudojia_tilta.js`：未签到时提交每日签到并可能获得积分；浏览商品及提交阅读任务会改变任务进度并可能获得积分；显式设置 TILTA_ALLOW_LIKE=1 时点赞随机社区文章；正式运行且通知开启时通过青龙配置渠道发送脱敏任务总结。
- `scripts/sudojia_tuchong.js`：正式运行登录会建立服务端会话。；正式运行每日签到会改变签到状态并可能增加积分。；正式运行在启用通知且青龙模块可用时向已配置通知渠道发送脱敏摘要。。
- `scripts/sudojia_v2ex.js`：领取 V2EX 每日登录奖励并增加账户奖励余额；正式运行时通过已有青龙通知模块发送脱敏任务汇总，可配置关闭。
- `scripts/sudojia_wnna.js`：未签到时执行每日签到并获得服务端发放的奖励；正式运行且通知启用时发送青龙任务通知。
- `scripts/sudojia_xhn.js`：登录产生授权会话；每日签到可能增加账号积分。
- `scripts/sudojia_xiangwan.js`：正式运行使用账号密码登录，可能创建服务端会话；正式运行每日签到并领取玩豆；显式启用缓存后写入受限权限的本地 Token 文件；通知开启且模块可用时发送脱敏任务结果。
- `scripts/sudojia_xiaomi_community.js`：每日调用微信签到接口增加成长值；启用通知且正式执行时，通过青龙已配置通知渠道发送脱敏结果。
- `scripts/sudojia_xinxi.js`：每日签到并可能获得喜点；启用免费抽奖后消耗一次免费机会并可能获得奖励；启用奖励任务后提交分享任务记录与商城浏览完成记录并可能获得喜点。
- `scripts/sudojia_xpfarm.js`：每日签到及其奖励入账；显式启用后变更所选任务完成状态并领取奖励；显式启用后消耗肥料以增加肥力；显式启用后消耗水滴及肥力并推进种树成长；正式运行时通过青龙已配置渠道发送脱敏总结。
- `scripts/sudojia_znds.js`：正式运行执行每日签到，可能获得积分或奖励；仅配置 ZNDS_VISIT_UID 时访问指定他人空间，可能产生足迹或访问奖励；正式运行且通知启用时发送脱敏任务通知。
- `scripts/sudojia_zxice.js`：未签到时提交每日签到并领取奶滴奖励；正式模式按通知配置发送任务结果通知。
- `scripts/tieba_checkin.py`：正式执行时向百度贴吧提交签到请求，改变对应贴吧的当日签到状态；通知开启且青龙通知组件可用时发送脱敏任务汇总。
- `scripts/tsthb_checkin.py`：向官方签到接口提交每日签到，可能获得积分或奖励；正式运行且通知开启时，通过已有青龙通知模块发送脱敏结果。
- `scripts/ty_netdisk_checkin.py`：正式模式每日签到可能增加奖励空间；正式模式按通知配置发送脱敏任务结果。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/aliyunpan_checkin.py`：上游 `agluo/ql-script-hub` / `aliyunpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/atxyq.py`：上游 `Rookie-wb-WH/ql_scripts` / `atxyq.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/baiduwangpan_checkin.py`：上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/bsly_draw.py`：上游 `cloudcranes/some_scripts` / `bsly_draw.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/bwcj.py`：上游 `Rookie-wb-WH/ql_scripts` / `bwcj.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/cdrail.py`：上游 `agluo/ql-script-hub` / `CDRail.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。
- `scripts/ddnsto.py`：上游 `cloudcranes/some_scripts` / `ddnsto.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/durex.py`：上游 `Rookie-wb-WH/ql_scripts` / `durex.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/ikuuu_checkin.py`：上游 `agluo/ql-script-hub` / `ikuuu_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。
- `scripts/main.py`：上游 `cloudcranes/some_scripts` / `Download_wallhaven/main.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/nga_checkin.py`：上游 `agluo/ql-script-hub` / `nga_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/nodeseek_checkin.py`：上游 `agluo/ql-script-hub` / `nodeseek_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/passnat_checkin.py`：上游 `agluo/ql-script-hub` / `passnat_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/quark_signin.py`：上游 `agluo/ql-script-hub` / `quark_signin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/sfsu_checkin.py`：上游 `agluo/ql-script-hub` / `SFSU_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/smzdm_checkin.js`：上游 `ump45nose/smzdm-checkin-ql` / `checkin.js` / `6b9eaced964c348efb46d2c13a45ab5c66caaea8`。
- `scripts/sudojia_33agilestudio.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_33agilestudio.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_allgirls.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_allGirls.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_amx.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_amx.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_bananavideo.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_bananaVideo.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_beiyinmei.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_beiyinmei.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_botanystar.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_botanyStar.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_bwtea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_bwtea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_colorful_mall.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_colorful_mall.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_flyant.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_flyant.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_fnnas.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_fnnas.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_hgf.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hgf.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_hlzj_game.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hlzj_game.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_hzhfp.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_hzhfp.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_instax.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_instax.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_jhcard.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_jhcard.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_jiangshan.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_jiangshan.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_jindian.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_jindian.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_jlc.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_jlc.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_jlc_yj.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_jlc_yj.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_juejin.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_juejin.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_kozbs.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_kozbs.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_ktgzs.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_ktgzs.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_kukahome.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_kukahome.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_kuro.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_kuro.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_laoban.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_laoban.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_longfor.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_longfor.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_mallcoo.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mallcoo.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_mawuwang.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mawuwang.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_midea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_midea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_moto.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_moto.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_mxbc.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_mxbc.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_naixue.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_naixue.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_nestle.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_nestle.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_nfhk.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_nfhk.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_opposhop.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_opposhop.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_pangge.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_pangGe.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_paotea.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_paotea.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_shmedia.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_shmedia.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_shuifei.js`：上游 `sudojia/AutoTaskScript` / `src/public/sudojia_shuifei.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_sspanel.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_sspanel.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_starmom.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_starMom.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_tebu.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_tebu.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_tilta.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_tilta.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_tuchong.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_tuchong.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_v2ex.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_v2ex.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_wnna.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_wnna.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_xhn.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_xhn.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_xiangwan.js`：上游 `sudojia/AutoTaskScript` / `src/client/sudojia_xiangwan.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_xiaomi_community.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xiaomi_community.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_xinxi.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xinxi.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_xpfarm.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_xpfarm.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_znds.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_znds.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_zxice.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_zxice.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/tieba_checkin.py`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_tieba.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/tsthb_checkin.py`：上游 `agluo/ql-script-hub` / `tsthb_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/ty_netdisk_checkin.py`：上游 `agluo/ql-script-hub` / `ty_netdisk_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
