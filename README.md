# shaco-checkin

通用签到类青龙脚本发布仓库。脚本经来源、许可证和基础检查后发布；真实账号人工核验和上架、下架在发布后进行。各脚本验证状态见下文。

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
| 139云盘云朵任务 | `scripts/139_yunduo.py` | `python3 scripts/139_yunduo.py` | `0 9 * * *` |
| 2cycdx自动签到 | `scripts/2cycdx.py` | `python3 scripts/2cycdx.py` | `0 8 * * *` |
| 51CTO博客每日签到 | `scripts/51cto_sign.js` | `node scripts/51cto_sign.js` | `0 8 * * *` |
| 华润通999答题 | `scripts/999.py` | `python3 scripts/999.py` | `1 1 1 1 1` |
| AcFun每日任务 | `scripts/acfun.py` | `python3 scripts/acfun.py` | `0 8 * * *` |
| AgentRouter签到 | `scripts/agentrouter.py` | `python3 scripts/agentrouter.py` | `20 9 * * *` |
| 机场签到（速鹰666） | `scripts/airport.py` | `python3 scripts/airport.py` | `0 0 * * *` |
| AkileCloud 签到与保活 | `scripts/akile_checkin.py` | `python3 scripts/akile_checkin.py` | `0 22 * * *` |
| 阿里云盘每日签到 | `scripts/aliyundrive_checkin.js` | `node scripts/aliyundrive_checkin.js` | `0 8 * * *` |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` |
| 奥拉星每日任务与积分 | `scripts/aolaxing.py` | `python3 scripts/aolaxing.py` | `0 8 * * *` |
| Hax 与 Woiden 可开通区域监控 | `scripts/api_hax.py` | `python3 scripts/api_hax.py` | `21 */6 * * *` |
| 明日方舟寻访公告 | `scripts/arknightsbanner.py` | `python3 scripts/arknightsbanner.py` | `0 10 * * *` |
| 艾特校园圈 | `scripts/atxyq.py` | `python3 scripts/atxyq.py` | `9 10,23 * * *` |
| 上海杨浦商城定时抢购 | `scripts/auto_buy.py` | `python3 scripts/auto_buy.py` | `0 0 10 * * *` |
| AutoClaw 国内版每日签到 | `scripts/autoclaw_cn_daily.py` | `python3 scripts/autoclaw_cn_daily.py` | `15 8 * * *` |
| 阿里云盘签到与奖励领取 | `scripts/autosignin.js` | `node scripts/autosignin.js` | `0 9 * * *` |
| E-Hentai 自动签到 | `scripts/autosignin.py` | `python3 scripts/autosignin.py` | `1 */6 * * *` |
| 百度站点提交 | `scripts/baidu.py` | `python3 scripts/baidu.py` | `0 9 * * *` |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` |
| 百度网盘会员成长值 | `scripts/baiduwp.py` | `python3 scripts/baiduwp.py` | `0 8 * * *` |
| B站每日任务 | `scripts/bilibili.py` | `python3 scripts/bilibili.py` | `0 0 * * *` |
| 百事乐元抽奖 | `scripts/bsly_draw.py` | `python3 scripts/bsly_draw.py` | `0 9 * * *` |
| 布谷TV每日签到 | `scripts/bugutv.py` | `python3 scripts/bugutv.py` | `0 8 * * *` |
| 霸王茶姬签到 | `scripts/bwcj.py` | `python3 scripts/bwcj.py` | `0 9,18 * * *` |
| 菜玩社区每日签到 | `scripts/caigamer.js` | `node scripts/caigamer.js` | `0 20 11 * * *` |
| 成都地铁签到 | `scripts/cdrail.py` | `python3 scripts/cdrail.py` | `0 9 * * *` |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` |
| 雪佛兰APP签到 | `scripts/chevrolet.js` | `node scripts/chevrolet.js` | `0 8 * * *` |
| 咔叽网单签到 | `scripts/ck_2nzz.py` | `python3 scripts/ck_2nzz.py` | `30 8 * * *` |
| AcFun每日签到与可选互动 | `scripts/ck_acfun.py` | `python3 scripts/ck_acfun.py` | `31 7 * * *` |
| CodeArts 每日福利领取 | `scripts/codearts_daily.py` | `python3 scripts/codearts_daily.py` | `15 8 * * *` |
| ComicAI 每日签到 | `scripts/comicai_ai_cookie.py` | `python3 scripts/comicai_ai_cookie.py` | `0 9 * * *` |
| 创想云国内站签到 | `scripts/crealitycloud_checkin.py` | `python3 scripts/crealitycloud_checkin.py` | `0 9 * * *` |
| 大潮App签到阅读 | `scripts/dachao.py` | `python3 scripts/dachao.py` | `30 10,14,18 * * *` |
| WPS天天领福利（可选任务中心） | `scripts/daily_benefits.py` | `python3 scripts/daily_benefits.py` | `1 1 1 1 1` |
| 中国日报 | `scripts/dailynewscn.js` | `node scripts/dailynewscn.js` | `0 15 9 * * *` |
| DDNSTO七天免费续费 | `scripts/ddnsto.py` | `python3 scripts/ddnsto.py` | `30 9 * * *` |
| DeepFlood 签到 | `scripts/deepflood_checkin.py` | `python3 scripts/deepflood_checkin.py` | `33 14 * * *` |
| 杜蕾斯会员中心 | `scripts/durex.py` | `python3 scripts/durex.py` | `9 9 * * *` |
| 恩山论坛签到 | `scripts/enshan_checkin.py` | `python3 scripts/enshan_checkin.py` | `39 12 * * *` |
| Epic免费游戏 | `scripts/epicfreegames.py` | `python3 scripts/epicfreegames.py` | `0 8 * * 6` |
| 鸿星尔克签到 | `scripts/erke.py` | `python3 scripts/erke.py` | `1 1 1 1 1` |
| 森空岛自动签到 | `scripts/f1owkang_qingskyland_skyland.py` | `python3 scripts/f1owkang_qingskyland_skyland.py` | `15 8 * * *` |
| 飞牛Nas论坛签到 | `scripts/fnnasclub.py` | `python3 scripts/fnnasclub.py` | `0 8 * * *` |
| Discuz 论坛日常维护 | `scripts/forum_download.py` | `python3 scripts/forum_download.py` | `20 8 * * *` |
| 废文网签到 | `scripts/fwxs_checkin.js` | `node scripts/fwxs_checkin.js` | `5 8 * * *` |
| 芬享汇每日签到 | `scripts/fxh.js` | `node scripts/fxh.js` | `0 8 * * *` |
| 阴阳师官网视频与原画 | `scripts/get_yys_cgvideo.py` | `python3 scripts/get_yys_cgvideo.py` | `0 9 * * 0` |
| 阴阳师官网原画与CG素材 | `scripts/get_yys_imagelinks.py` | `python3 scripts/get_yys_imagelinks.py` | `0 9 * * 0` |
| HelloGitHub月刊提醒 | `scripts/hellogithub.py` | `python3 scripts/hellogithub.py` | `0 8 1 * *` |
| HiFiTi与HiFiHi签到 | `scripts/hifiti_checkin.py` | `python3 scripts/hifiti_checkin.py` | `30 6 * * *` |
| 活力伊利 | `scripts/hlyl.py` | `python3 scripts/hlyl.py` | `0 8 * * *` |
| 沪上阿姨签到 | `scripts/hsay.py` | `python3 scripts/hsay.py` | `0 9,18 * * *` |
| 华润通微信版签到 | `scripts/huaruntong_wx.py` | `python3 scripts/huaruntong_wx.py` | `1 1 1 1 1` |
| 好游快爆游戏签到 | `scripts/hykb_gamesign.js` | `node scripts/hykb_gamesign.js` | `15 8 * * *` |
| ikuuu 签到 | `scripts/ikuuu_checkin.py` | `python3 scripts/ikuuu_checkin.py` | `0 21 * * *` |
| i茅台申购与耐力 | `scripts/imaotai.py` | `python3 scripts/imaotai.py` | `5 9 * * *` |
| Pixiv 收藏图片下载 | `scripts/index.js` | `node scripts/index.js` | `0 3 * * *` |
| 爱奇艺签到 | `scripts/iqiyi_checkin.py` | `python3 scripts/iqiyi_checkin.py` | `5 10 * * *` |
| 机场面板每日签到 | `scripts/jc_checkin.py` | `python3 scripts/jc_checkin.py` | `0 8 * * *` |
| jcqd 多站签到 | `scripts/jcqd.py` | `python3 scripts/jcqd.py` | `0 9 * * *` |
| 精易论坛签到 | `scripts/jingyiluntan_sign.py` | `python3 scripts/jingyiluntan_sign.py` | `0 8 * * *` |
| 杰士邦安心福利社 | `scripts/jissbon.py` | `python3 scripts/jissbon.py` | `9 9 * * *` |
| 劲友家日常任务 | `scripts/jyj.py` | `python3 scripts/jyj.py` | `0 8 * * *` |
| 全民K歌签到与奖励 | `scripts/kgqq.py` | `python3 scripts/kgqq.py` | `0 9 * * *` |
| 科技玩家签到 | `scripts/kjwj.py` | `python3 scripts/kjwj.py` | `30 7 * * *` |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` |
| KukuAI 每日积分 | `scripts/kuku_daily.py` | `python3 scripts/kuku_daily.py` | `0 8 * * *` |
| 鸣潮·库街区 每日签到 | `scripts/kurobbs_sign.py` | `python3 scripts/kurobbs_sign.py` | `3 0 * * *` |
| LINUX DO 登录与浏览统计 | `scripts/l.py` | `python3 scripts/l.py` | `5 */5 * * *` |
| Leaflow 签到 | `scripts/leaflow_checkin_pyleaflow_checkin.py` | `python3 scripts/leaflow_checkin_pyleaflow_checkin.py` | `34 18 * * *` |
| 咔叽网单每日签到 | `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `python3 scripts/littlewuh_qinglongbox_dailycheckin_scripts.py` | `30 8 * * *` |
| NodeSeek 签到与收益统计 | `scripts/lizhixu_ql_script_hub_nodeseek.py` | `python3 scripts/lizhixu_ql_script_hub_nodeseek.py` | `23 4 * * *` |
| 有道云笔记签到 | `scripts/lizhixu_ql_script_hub_youdao.py` | `python3 scripts/lizhixu_ql_script_hub_youdao.py` | `01 5 * * *` |
| LobsterAI 每日签到 | `scripts/lobsterai_checkin.py` | `python3 scripts/lobsterai_checkin.py` | `0 9 * * *` |
| Loomy 每日积分与新手任务 | `scripts/loomy_daily.py` | `python3 scripts/loomy_daily.py` | `0 8 * * *` |
| 领克App每日签到分享 | `scripts/lynkco_qinglong_single.py` | `python3 scripts/lynkco_qinglong_single.py` | `8 8 * * *` |
| Wallhaven最新壁纸下载 | `scripts/main.py` | `python3 scripts/main.py` | `0 8 * * *` |
| 米饭APP日常维护 | `scripts/mifan_optimized.py` | `python3 scripts/mifan_optimized.py` | `0 9 * * *` |
| 小米运动账号验证与步数上传 | `scripts/mimotion.py` | `python3 scripts/mimotion.py` | `0 20 * * *` |
| 网易云全能打卡 | `scripts/netease_task.py` | `python3 scripts/netease_task.py` | `30 9 * * *` |
| NGA 论坛签到 | `scripts/nga_checkin.py` | `python3 scripts/nga_checkin.py` | `1 17 * * *` |
| NodeSeek签到 | `scripts/nodeseek.py` | `python3 scripts/nodeseek.py` | `0 0 * * *` |
| NodeSeek 论坛签到 | `scripts/nodeseek_checkin.py` | `python3 scripts/nodeseek_checkin.py` | `23 14 * * *` |
| 塔吉多（异环）自动签到 | `scripts/nte.py` | `python3 scripts/nte.py` | `0 8 * * *` |
| OfficeAce 果办每日奖励 | `scripts/officeace_daily.py` | `python3 scripts/officeace_daily.py` | `0 9 * * *` |
| 华润通Ole签到 | `scripts/ole.py` | `python3 scripts/ole.py` | `1 1 1 1 1` |
| PassNAT 签到 | `scripts/passnat_checkin.py` | `python3 scripts/passnat_checkin.py` | `18 0 * * *` |
| PSNINE 每日祈祷 | `scripts/psnine.py` | `python3 scripts/psnine.py` | `0 8 * * *` |
| PT 多站签到（SafeLine 兼容维护版） | `scripts/pt_sign_v5.js` | `node scripts/pt_sign_v5.js` | `0 8 * * *` |
| Qoder每日签到 | `scripts/qoder_airscript.js` | `node scripts/qoder_airscript.js` | `17 8 * * *` |
| 夸克网盘每日签到 | `scripts/quark_signin.py` | `python3 scripts/quark_signin.py` | `13 18 * * *` |
| 小浣熊每日积分 | `scripts/raccoon_daily.py` | `python3 scripts/raccoon_daily.py` | `0 9 * * *` |
| 雨云服务器签到 | `scripts/rainyun.py` | `python3 scripts/rainyun.py` | `0 2 * * *` |
| Rousi 签到 | `scripts/rousi_checkin.js` | `node scripts/rousi_checkin.js` | `0 9 * * *` |
| 顺丰快递积分任务 | `scripts/sf.py` | `python3 scripts/sf.py` | `1 1 1 1 1` |
| 顺丰速运签到 | `scripts/sfsu_checkin.py` | `python3 scripts/sfsu_checkin.py` | `9 15 * * *` |
| 申工社每日任务 | `scripts/sgs.py` | `python3 scripts/sgs.py` | `0 8 * * *` |
| 书亦烧仙草签到 | `scripts/shuyi.py` | `python3 scripts/shuyi.py` | `0 9 * * *` |
| 看雪论坛签到 | `scripts/sign_in.py` | `python3 scripts/sign_in.py` | `1 1 1 1 1` |
| 森空岛每日任务 | `scripts/skland_daily.py` | `python3 scripts/skland_daily.py` | `0 8 * * *` |
| 森空岛双游戏签到 | `scripts/skland_demo.py` | `python3 scripts/skland_demo.py` | `0 8 * * *` |
| 森空岛签到 | `scripts/skyland.py` | `python3 scripts/skyland.py` | `0 8 * * *` |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `node scripts/smzdm_checkin.js` | `31 8 * * *` |
| SSL证书检查 | `scripts/ssl.py` | `python3 scripts/ssl.py` | `0 0 * * *` |
| 33台词每日签到 | `scripts/sudojia_33agilestudio.js` | `node scripts/sudojia_33agilestudio.js` | `1 11 * * *` |
| 所有女生会员签到 | `scripts/sudojia_allgirls.js` | `node scripts/sudojia_allgirls.js` | `19 16 * * *` |
| 安慕希每日签到 | `scripts/sudojia_amx.js` | `node scripts/sudojia_amx.js` | `33 14 * * *` |
| 多合一账号失效检测 | `scripts/sudojia_authcheck.js` | `node scripts/sudojia_authcheck.js` | `10 12,21 * * *` |
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
| 微博超话签到 | `scripts/supertopicsign.py` | `python3 scripts/supertopicsign.py` | `0 8 * * *` |
| 所有女生会员服务中心积分版 | `scripts/synspoint.py` | `python3 scripts/synspoint.py` | `8 8,12 * * *` |
| 腾讯视频签到 | `scripts/tencent_video_checkin.py` | `python3 scripts/tencent_video_checkin.py` | `45 9 * * *` |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` |
| 塔吉多每日任务 | `scripts/tjd_daily.py` | `python3 scripts/tjd_daily.py` | `30 9 * * *` |
| Trae 每日签到与积分查询 | `scripts/trae_checkin.py` | `python3 scripts/trae_checkin.py` | `7,23,37 * * * *` |
| 塔斯汀汉堡签到 | `scripts/tsthb_checkin.py` | `python3 scripts/tsthb_checkin.py` | `55 9 * * *` |
| 天翼云盘签到 | `scripts/ty_netdisk_checkin.py` | `python3 scripts/ty_netdisk_checkin.py` | `1 16 * * *` |
| 统一茄皇集市抽奖 | `scripts/tyqhdraw.py` | `python3 scripts/tyqhdraw.py` | `0 0 0 * * *` |
| 掌瓦每日商店推送 | `scripts/valorantstore.py` | `python3 scripts/valorantstore.py` | `15 8 * * *` |
| Vortexa 免费主机检查与领取 | `scripts/vortexa_free_claim.js` | `node scripts/vortexa_free_claim.js` | `1,11,21,31,41,51 * * * *` |
| 望潮阅读有礼 | `scripts/wangchao.py` | `python3 scripts/wangchao.py` | `2 8 * * *` |
| 华润通文体未来荟签到 | `scripts/wentiweilaihui.py` | `python3 scripts/wentiweilaihui.py` | `1 1 1 1 1` |
| WorkBuddy签到 | `scripts/workbuddy.py` | `python3 scripts/workbuddy.py` | `30 8 * * *` |
| WorkBuddy 国内版日常维护 | `scripts/workbuddy_daily.py` | `python3 scripts/workbuddy_daily.py` | `0 7,12 * * *` |
| WPS打卡活动信息 | `scripts/wps_clock_in.py` | `python3 scripts/wps_clock_in.py` | `10 9 * * *` |
| 益禾堂手机点单 | `scripts/yht.py` | `python3 scripts/yht.py` | `8 6 * * *` |
| 有道云笔记每日空间奖励 | `scripts/youdao.py` | `python3 scripts/youdao.py` | `0 8 * * *` |
| 阴阳师绘卷时间获取 | `scripts/yyshuijuantime.py` | `python3 scripts/yyshuijuantime.py` | `0 0 * * *` |
| ZCode 国内版领套餐 | `scripts/zcode_cn_daily.py` | `python3 scripts/zcode_cn_daily.py` | `0 9 * * *` |
| Zippo会员中心 | `scripts/zippo.py` | `python3 scripts/zippo.py` | `9 9 * * *` |
| Zodgame签到与广告任务 | `scripts/zodgame_test.py` | `python3 scripts/zodgame_test.py` | `0 8 * * *` |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 脚本功能

- `scripts/139_yunduo.py`：标准库实现完整SSO与JWT认证链，展示官方返回的非敏感账号身份；获取执行前后AI豆余额；检查当日签到状态并执行每日签到，验证返回结果；列出云朵任务与奖励说明，完成小云互动礼319、问卷118及605、606、431点击任务并复查FINISH；显式启用后尝试其他未完成任务的点击接口；显式启用后上传随机小文件完成任务106，完成后可选择移入回收站；按最新AI豆余额展示可兑换奖品、分类、价格与今日余量，不执行兑换；逐行多账号及旧版单账号参数兼容，失败闭合；完全断网预演、时间轴日志、阶段统计和单行结构化任务汇总；青龙通知及PushPlus、Server酱通知回退，通知故障保留业务退出码。
- `scripts/2cycdx.py`：获取论坛签到页面及 formhash 登录参数。；每天 08:00 签到领取贡献，明确识别签到成功和今日已签到。；逐行多账号独立处理，任一账号失败返回非零退出码。；使用一言 HTTPS 随机签到文案，解析文本、作者和来源并保留署名格式；失败时使用本地文案，不向文案服务发送凭据。；保留页面编码识别、中文表单编码和 XML CDATA 业务结果解析。；返回官方非敏感用户名时显示，凭据、原始响应和敏感身份不输出。；提供完全断网预演，模拟签到、文案获取和通知。；青龙通知覆盖成功、部分失败、失败、配置错误及预演；不可用或失败时保留业务退出码。；输出时间轴阶段日志、账号和任务统计及单行 TASK_SUMMARY JSON。；独立标准库 HTTP 实现，带超时、响应大小限制及跨站重定向保护。。
- `scripts/51cto_sign.js`：账号密码登录并同步博客会话；获取签到Token并沿用原始MD5接口签名；查询每日签到状态，已经签到时避免重复提交；未签到时执行签到并重新查询验证完成；每行一个账号，兼容单行旧式用户名@密码；完全断网预演、阶段日志、账号及任务统计和结构化汇总；青龙通知及全局开关，通知失败保留业务退出码。
- `scripts/999.py`：按原接口获取华润通999题目；展示题目、选项和接口标记的正确答案；支持单选或多选正确选项并提交答案；按上游 resultCode 字符串 0 验证获取和提交成功，不推断积分到账；多账号独立处理和失败退出；本地模拟完整答题流程的断网预演；按时间轴记录阶段耗时、账号和任务统计，并输出单条结构化汇总；正式执行通过青龙通知发送脱敏摘要，断网预演在本地输出摘要；展示官方接口返回的非敏感昵称、用户名、显示名称或公开标识。
- `scripts/acfun.py`：手机号密码登录及多账号独立执行；每日签到及等级、香蕉余额查询；显示官方返回的非秘密昵称、用户名或公开用户标识；排行榜选择视频，支持显式点赞、点赞后取消和投一根香蕉；读取实际视频及分区信息后显式发布弹幕；禁止硬编码目标回退；弹幕优先使用独立无凭据的一言请求，保留正文与作者、来源署名；各类失败均回退本地文案；使用配套 App 登录凭据显式上报分享任务；完全断网预演、通知入口、带时间戳的分阶段统计和单行机器可读汇总。
- `scripts/agentrouter.py`：通过 GitHub OAuth 重新登录触发每日签到，以服务端 checked_in 严格确认为成功。；查询并展示官方账号身份、当前余额美元换算及已用额度。；保留站点公开客户端配置、已知客户端编号和额度换算比例兜底。；支持每行一个账号、原 JSON 配置格式、账号站点与用户编号配置、代理与可信 CA 证书。；支持显式启用首次 GitHub OAuth 授权；默认要求浏览器手动授权。；每天 09:20 运行，多账号间隔五秒。；完全断网预演、分阶段日志、账号与子任务统计、单行 TASK_SUMMARY 汇总及青龙脱敏通知。。
- `scripts/airport.py`：使用邮箱和密码登录速鹰666，保留原有登录地址与表单字段。；每日签到并核验明确的业务成功结果；明确已签到结果视为已完成。；查询剩余流量，保留原 XPath 与 originBody Base64 页面解码及原始页面回退。；逐行多账号及旧版单账号参数兼容，失败账号不阻止后续账号执行。；脱敏的逐账号报告、统计、单行 TASK_SUMMARY 和青龙通知。；完全断网预演验证参数与执行计划，预演不代表真实账号业务成功。。
- `scripts/akile_checkin.py`：AK 币签到，先查今日流水以避免重复提交，提交后复核实际流水。；查询余额、今日所得、连续天数与累计签到收益，分页校准及增量同步。；显式开启 Token 保活，验证新凭据后唯一匹配回写青龙多行变量。；支持 --check-only 只读查询、08:45 合集调用和每天 22:00 独立定时。；多账号独立执行、完全断网预演、脱敏日志、官方公开身份展示、合集 JSON 与单行任务汇总。；按通知开关发送脱敏总结，通知故障保留业务退出码；缺参及未确认结果失败闭合。。
- `scripts/aliyundrive_checkin.js`：通过刷新令牌获取访问令牌并展示官方返回的昵称、用户名或公开用户标识；每日签到并展示本月累计签到天数；领取当日奖励并识别已领取状态；查询并展示本月签到日历；展示当日签到奖励和任务奖励概览；每行一个账号，独立执行并汇总失败；完全断网预演，模拟通知并明确未验证真实业务；青龙脱敏通知及可选 HTTPS PushPlus 推送，支持全局关闭；分阶段时间轴日志、逐账号统计和单行 TASK_SUMMARY 结构化汇总。
- `scripts/aliyunpan_checkin.py`：刷新登录凭据并识别令牌轮换，全程不输出凭据；查询官方公开身份与存储容量；查询失败继续签到与领奖，最终非零退出；每日签到并输出本月累计签到天数；输出逐日签到状态、奖励名称及说明、已领奖与待领奖天数；默认领取当日奖励并识别已领取状态，支持显式关闭领奖；显式开启后补领本月全部已签到未领奖励，单日失败仍继续其余奖励，最终失败退出；保留可选设备会话及设备签名；ecdsa 仅在正式启用时导入；保留随机延迟、新旧参数兼容和多账号独立执行；显式开启时安全持久化轮换令牌文件；完全断网预演、青龙脱敏总结通知、分阶段时间轴日志及原机器汇总。
- `scripts/aolaxing.py`：查询每日任务列表、今日任务总数及完成数。；按显式指定任务 ID 执行未完成任务，执行后重新读取列表核验已完成状态；已完成任务不重复执行。；查询当前积分、累计获得积分和累计签到次数。；官方响应返回昵称、用户名、显示名称或公开 UID 时显示非敏感身份；抑制手机号和凭据。；逐行多账号、上游配置键名兼容、断网预演、独立 HTTPS 请求、超时和失败非零退出。；时间轴阶段日志、账号与任务统计、单行机器汇总和青龙脱敏通知。。
- `scripts/api_hax.py`：查询并按地区汇总 Hax 开通数量。；按虚拟化类型分组展示 Hax 可开通区域及开通页面链接。；展示 Woiden 可开通区域及开通页面链接。；保留 HAX 启用开关和每六小时第 21 分钟定时。；完全断网预演、独立查询失败隔离、页面校验及结构化汇总。；通过青龙通知模块发送公开结果和统计，通知失败保留业务退出码。。
- `scripts/arknightsbanner.py`：每天 10 点监控明日方舟官方寻访公告，无需游戏账号；无第三方业务依赖。；扫描 LATEST 至末页或最多 50 页；ACTIVITY 前 5 页兜底，整页已知时停止，按公告标识去重并按发布时间排序。；逐条抓取公告正文，不依赖标题或摘要预筛；移除脚本与健康提示页脚后识别卡池出率关键词。；提取寻访名称、类型、活动时间、六星与五星 UP 干员、出率、保底规则、寻访数据契约兑换所及公告链接。；首次记录全部扫描公告，仅推送最新一期卡池；后续增量处理新公告，未知详情或通知失败保留重试，损坏状态文件不会静默重置。；通过青龙通知发送分段文字；有封面时附封面链接，并可通过自己实现的 Telegram HTTP 接口发送图片至多个换行配置目标。；兼容原状态字段与原定时安排，原子写入状态；请求有超时、体积限制、HTTPS 约束和业务结构检查。；完全断网预演验证正文、结构化解析、封面与报告，不读写状态、不请求公告、不加载通知或发送图片。；输出中文时间轴、阶段耗时、监控源统计、最终状态及唯一 TASK_SUMMARY JSON；每次运行尝试脱敏总结通知，通知故障保持业务退出码。。
- `scripts/atxyq.py`：查询并直接展示官方昵称，查询学校启用状态与积分任务列表。；每日签到，核验连续天数与获得积分。；领取普通任务奖励，保持上游排除新用户奖励、集赞有奖、发布任务和邀请有奖。；查询当前可用积分。；显式开启最多两篇校园文章的点赞与取消点赞。；显式发布动态，优先一言正文及作者来源署名，所有声明失败情形回退本地文本；可登记本人已有图片。；显式查询并清理本人最近十篇列表内帖子，删除后重新查询核验。；使用本地明确指定的目标执行助力点赞或邀请绑定，不读取远程默认助力配置。；逐行多账号、失败隔离、完全断网预演、脱敏通知、编号阶段日志与唯一 TASK_SUMMARY 汇总。。
- `scripts/auto_buy.py`：按任务开关独立运行商城定时抢购或积分任务，保留商城默认入口、参数和计划；指定商品、数量、活动编号和促销类型抢购，支持完整日期、时分秒或立即执行；商城明确业务拒绝后按配置次数和间隔重试，未知结果停止重试并提示核对订单；查询积分、今日积分、签到状态、任务列表和已完成或未完成任务进度；不自动签到；显式开启后按服务端剩余进度执行阅读、视频、收藏、评论和分享积分任务；评论获取两页文章并随机选择不重复内容，一言优先，保留作者及来源署名，全部规定失败回退本地短句；默认保留收藏，可显式开启收藏后取消收藏；动作保留原始等待区间；积分动作逐步核对业务码并刷新任务状态确认完成；缺失任务、未知响应或未确认完成均失败闭合；按行多账号、独立处理、任一失败非零退出，配套凭据集中配置；无网络预演、脱敏时间轴日志、账号与任务统计及唯一结构化汇总；真实运行通过青龙通知汇总；所有结果含配置错误均通知，预演生成摘要，支持全局开关；展示官方明确返回的非敏感昵称、用户名、显示名或公开用户编号。
- `scripts/autoclaw_cn_daily.py`：国内版每日签到及积分奖励结果显示，明确业务码及成功标记校验；登录态过期后自动续期并重试签到，签名校验失败时使用 agent-refresh 备用接口；无明确领取结果时只读查询任务清单用于诊断，不将诊断冒充领取成功；支持 --refresh-only 仅续期、--only N 选择账号和 --no-notify 关闭通知；显式启用的私有凭据缓存读取和安全原子保存；默认不落盘登录态；换行多账号独立执行，任一失败整体非零退出；断网预演、分阶段脱敏日志、账号与任务统计和单行 TASK_SUMMARY 汇总；官方返回昵称、用户名、显示名称或公开 UID 时显示该非秘密身份；青龙通知组件优先，兼容 PushPlus、Bark、企业微信、钉钉和显式青龙 API 备用推送；显式 --region intl 或 AUTOCLAW_REGION=intl 使用国际版官方接口及独立凭据；保留国内版默认行为；显式 --region both 按同一每日时机独立执行两地区账号，缓存按地区配置；某地区缺配置仍处理另一地区账号并整体失败。
- `scripts/autosignin.js`：刷新并验证登录令牌，显示官方返回的非凭据账号身份。；每天 9 点执行签到并显示当月累计签到天数。；领取当天已完成的每日签到奖励和每日任务奖励，展示领取结果；未完成及已结束奖励明确跳过。；保留维护候选的业务状态及结构核验；未知奖励结构、状态和类型按失败处理。；逐行多账号及旧变量兼容，账号独立执行，任一失败整体非零退出。；完全断网预演、请求超时、响应大小限制、脱敏时间轴日志、每账号及任务统计和唯一 TASK_SUMMARY 汇总。；所有运行结果生成脱敏通知总结；正式运行使用青龙 sendNotify.js 投递，预演仅生成不联网投递。。
- `scripts/autosignin.py`：访问 E-Hentai 新闻页完成签到，并核验事件区明确奖励或今日已完成提示；识别随机遭遇，提示手动处理或等待结束；未确认签到时非零退出；保留默认 TLS 三次请求及 TLS 1.2 三次回退，设置超时、响应大小限制与证书校验；兼容 E_COOKIE、E_PROXY、E_USER_AGENT，多账号按非空行独立运行；解析服务端 Cookie 到期时间并提醒更新，不输出或写回 Cookie 值；显示官方返回的公开账号身份；其他响应内容保持脱敏；完全断网预演、时间轴阶段日志、账号统计、任务统计和单行 TASK_SUMMARY 汇总；正式运行通过青龙通知模块发送脱敏汇总，通知不可用不改变业务退出码；预演生成摘要并禁止外部投递。
- `scripts/baidu.py`：下载并校验本站 UTF-8 URL 清单；调用百度站点提交接口并核验 success 与 remain，输出成功条数和剩余配额；支持显式设置重复提交次数，默认仅提交一次；按行配置多个站点，逐账号隔离错误并汇总业务退出码；完全离线预演、分阶段时间轴日志和唯一 TASK_SUMMARY 结构化结果；通过青龙通知发送脱敏结果，支持全局关闭，通知故障不改变业务退出码。
- `scripts/baiduwangpan_checkin.py`：每日百度网盘会员签到，明确验证积分或已完成状态；获取并提交每日会员成长问题答案；读取并报告脱敏用户名、会员等级、成长值和会员类型；逐行多账号独立处理与结构化 JSON 汇总；完全断网的配置预演；成功、部分失败、失败、配置错误和预演状态的青龙脱敏汇总通知。
- `scripts/baiduwp.py`：会员成长值签到并报告获得成长值；获取每日题目并提交官方返回的答案，报告答题成长值；查询当前会员等级和成长值；展示官方返回的非敏感账号身份；可选择单项或组合任务，支持每行一个账号；完全断网参数预演、独立账号失败统计及单行结构化任务汇总；正式执行结束后调用青龙通知，通知失败不改变业务退出码。
- `scripts/bilibili.py`：验证登录并显示官方返回昵称、公开 UID 和硬币余额；漫画签到及重复签到识别；热门视频来源和排行榜备用来源；关注 UP 主投稿作为投币优先来源，保留热门补充；按每日目标投币并核对今日经验和余额，支持显式选择同时点赞；上报视频观看进度 300 秒；显式开启视频分享接口上报；可选银瓜子兑换硬币；查询直播硬币、金瓜子和银瓜子余额；查询今日与当前经验并估算达到六级所需天数；逐账号独立执行与整体失败退出；完全断网预演、分阶段日志、结构化汇总和青龙脱敏通知。
- `scripts/bsly_draw.py`：百事乐元抽奖，保留原 GET 接口、Token、User-Agent 和微信 Referer 请求头。；每行多账号及旧账号字段兼容，保留 User-Agent 内的 #，账号独立处理。；显式开启抽奖及每账号可配置次数上限，数字业务码 0 和有效奖品名称双重校验。；超时、限制响应大小、禁止重定向和副作用请求重试，网络与业务失败均非零退出。；完全断网预演、脱敏时间轴日志、编号阶段与耗时、逐账号及全任务统计、单行 TASK_SUMMARY。；官方返回昵称、用户名、显示名称或公开 UID 时展示非凭据身份，抑制手机号及凭据。；通过青龙 notify.py 或 sendNotify.js 发送脱敏任务总结，支持全局关闭，通知失败保留业务退出码；预演仅本地模拟。。
- `scripts/bugutv.py`：使用用户名及密码登录布谷TV，校验官方登录成功消息；每日签到，区分签到成功与今日已签到，拒绝未确认的业务结果；查询签到前后积分并展示本次增量与累计积分，支持小数积分；默认完成后退出登录并核验退出结果，允许单独关闭退出动作；官方返回公开昵称、用户名或公开UID时直接显示，敏感值不输出；多账号隔离执行、失败汇总与非零退出码；完全断网预演、分阶段耗时日志及唯一TASK_SUMMARY结构化汇总；按青龙全局通知开关发送脱敏总结，保留可选Server酱通知。
- `scripts/bwcj.py`：读取并展示官方非秘密账号身份，禁止输出手机号和凭据。；读取积分流水获取签到用户 ID，支持同账号手动补充用户 ID 并核验一致性。；查询新版签到天数，使用上游签名算法执行新版签到并核验业务状态和奖励明细。；显式开启旧版签到后查询旧版活动及连续天数并执行旧版签到。；保留每天 9 点和 18 点定时及 bwcjCookie 变量名，换行多账号独立执行。；完全断网预演、脱敏分阶段日志、账号及任务统计、唯一 TASK_SUMMARY 结构化记录。；青龙通知发送脱敏总结，支持全局开关，通知失败不改变业务退出码。。
- `scripts/caigamer.js`：每日签到，保留原有每天 11:20 调度和 Cookie 参数名；显示官方非敏感账号身份及签到名次、连续签到天数和奖励的安全字段；明确成功及今日已签到判定，未知业务结果失败闭合；多账号独立运行与失败退出码；完全断网预演、时间轴日志和结构化统计；青龙脱敏通知，通知失败保留业务退出码。
- `scripts/cdrail.py`：每日签到与积分增量展示；基于明确业务码确认签到成功或今日已签到；每行一个账号，支持 JSON、查询字符串及自定义请求头；签到前随机等待、账号间间隔及超时控制；完全断网预演、青龙脱敏通知及单行结构化汇总；展示接口返回的非敏感昵称、用户名、显示名或公开账号标识。
- `scripts/cfmoto_checkin.py`：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。
- `scripts/chevrolet.js`：雪佛兰 APP 每日签到，保留上游接口、POST 方法及 cpctoken 请求头参数。；每行一个账号，兼容上游 xflCookie，独立处理并汇总账号结果。；完全断网预演，检查参数及执行流程，不把预演标为业务签到成功。；请求超时及响应大小限制，严格检查 HTTP 状态和明确业务成功标记。；显示官方返回的非秘密昵称、用户名、显示名称或公开 UID，同时抑制凭据、手机号和原始响应。；脱敏时间轴日志、账号及任务统计、单行 TASK_SUMMARY 汇总。；通过青龙 sendNotify.js 通知成功、部分失败、失败、配置错误及预演结果，通知异常不改变业务退出码；断网预演中通知网络被禁止。。
- `scripts/ck_2nzz.py`：使用登录 Cookie 获取签到令牌，保留原签到接口路径、请求方法和表单字段。；查询并直接显示官方页面返回的公开 UID。；执行每日签到，区分明确成功、明确已完成与失败；混合已签到或时间未开始提示不判成功。；支持每行一个账号、独立错误处理及任一失败非零退出。；完全断网预演、分阶段脱敏日志、账号和任务统计及单行 TASK_SUMMARY 记录。；成功、部分失败、失败、配置错误发送青龙脱敏通知；预演只展示通知摘要，关闭开关受支持。。
- `scripts/ck_acfun.py`：独立实现手机号密码登录及多账号处理，不依赖原仓库工具。；保留每天 7:31 调度，默认签到与等级、香蕉余额查询。；按需获取排行榜视频和互动令牌。；显式启用点赞后取消，两步分别检查业务结果。；显式启用公开弹幕，动态提取视频和分区，一言优先并保留作者、来源署名，失败回退本地文本。；显式启用对排行榜视频投一根香蕉。；官方返回的非秘密昵称、用户名和公开用户标识直接显示。；支持完全断网预演、分阶段脱敏日志、账号及任务统计和单行结构化汇总。；正式执行的成功、部分失败、失败及配置错误均尝试青龙通知，通知不可用或失败保留业务退出码；断网预演模拟通知。。
- `scripts/codearts_daily.py`：读取和只读预览福利活动（--preview 不续期、不写台账）；领取 USER_LOGIN 信用积分与一次性 NEW_USER_REGISTER 注册礼；领取、确认后同源回读，仅 CONFIRMED/CONSUMED 且不可再领取算到账；华为云 SDK-HMAC-SHA256 签名和临时凭据自动续期；持久化幂等台账、北京时间每日六次及十分钟间隔限制，--force 显式绕过；--only 按原始账号序号选择、多账号独立执行和失败退出；青龙通知总开关、原有备用推送渠道、脱敏日志及单行任务总结；完全断网预演，不读写状态、不发送通知。
- `scripts/comicai_ai_cookie.py`：可选 Cookie 登录页访问，保留原流程但不将页面 HTTP 200 当作认证成功；查询签到前积分并展示签到成功响应中的签到后积分；每日签到与已签到业务码识别；展示接口返回的非敏感昵称、用户名、显示名称或公开 UID；逐行多账号及旧环境变量兼容，账号独立执行且任一失败整体失败；完全断网预演及配置校验；分阶段时间轴日志、账号及子任务统计、单行 TASK_SUMMARY JSON；向青龙 notify.py 发送脱敏总结，通知不可用或失败时保留业务退出码。
- `scripts/crealitycloud_checkin.py`：国内站手机号或邮箱密码登录，手机号自动补 86 区号；直接登录态失效后的 OAuth 授权码登录回退；查询今日签到状态，已签到时避免重复操作；每日签到，展示连续签到天数和积分、经验奖励；查询官方非敏感身份、总积分、经验及创想币余额；默认整体随机延时和多账号间随机等待，保留每日 09:00 定时；每行一个账号、账号独立处理及失败非零退出；断网预演、逐阶段脱敏日志、账号统计和单行 TASK_SUMMARY 记录；通过青龙 notify.py 尝试发送脱敏任务总结，支持全局开关和失败隔离。
- `scripts/dachao.py`：账号密码登录及官方昵称展示；动态发现签到和阅读活动；签到及已签到状态判断；阅读任务、实际等待及阅读时长上报；阅读滑块验证码三种算法求偏移并重试；显式开启签到抽奖和阅读抽奖；显式开启现金红包兑换及无效兑换码短暂重试；多账号隔离、失败闭合及单行结构化汇总；青龙通知与完全断网配置预演。
- `scripts/daily_benefits.py`：按优先级合并双营销渠道，自动发现福利中心入口并查询活动页面；免费会员打卡、服务端签到日期和连续签到天数核对，提交后刷新核验今日状态；显式开启后可在服务端明确返回系列失效时重开签到系列一次；查询并按可用机会申请未参与的会员试用，逐项检查业务成功；显式开启后执行天天抽奖并逐次检查业务成功；先领取已有七日系列奖励，再签到；刷新签到及抽奖后检查七日领奖条件，防止同系列重复领取；可选合并同排期任务中心的官方公钥获取、加密签到、积分和即将过期积分查询；可选任务中心抽奖，使用官方页面返回的有效场次，保留单账号 max_lottery_limit 默认上限五次及抽奖后积分刷新；支持换行多账号和原 JSON 账号字段，显示官方非秘密昵称、用户名或公开用户编号；完全断网预演、独立账号失败处理、非零失败退出、脱敏日志、阶段耗时及唯一结构化任务汇总；所有运行结果均生成脱敏通知；正式运行发现并调用青龙通知，通知失败保持业务退出码。
- `scripts/dailynewscn.js`：DAILYNEWSCN_TASK=dailynewscn：获取、校验、输出并通知中国日报；保留 DAILYNEWSCN_LIST、DAILYNEWSCN_SUCCESS；同文件另建任务，定时 0 15 9 * * *。；DAILYNEWSCN_TASK=bdhot：获取、校验、输出并通知百度热搜榜；保留 BDHOT_LIST、BDHOT_SUCCESS；同文件另建任务，定时 0 0 9 * * *。；DAILYNEWSCN_TASK=chouq：获取、校验、输出并通知随机抽签；保留 CHOUQ_LIST、CHOUQ_SUCCESS；同文件另建任务，定时 0 10 9 * * *。；DAILYNEWSCN_TASK=day60s：获取、校验、输出并通知每天60秒读懂世界；保留 DAY60S_LIST、DAY60S_SUCCESS；同文件另建任务，定时 0 20 9 * * *。；DAILYNEWSCN_TASK=dyhot：获取、校验、输出并通知抖音热搜榜；保留 DYHOT_LIST、DYHOT_SUCCESS；同文件另建任务，定时 0 25 9 * * *。；DAILYNEWSCN_TASK=jitang：获取、校验、输出并通知鸡汤；保留 JITANG_LIST、JITANG_SUCCESS；同文件另建任务，定时 0 30 9 * * *。；DAILYNEWSCN_TASK=kfc：获取、校验、输出并通知KFC疯狂星期四；保留 KFC_LIST、KFC_SUCCESS；同文件另建任务，定时 0 35 9 * * *。；DAILYNEWSCN_TASK=meiju：获取、校验、输出并通知随机美句；保留 MEIJU_LIST、MEIJU_SUCCESS；同文件另建任务，定时 0 40 9 * * *。；DAILYNEWSCN_TASK=miyu：获取、校验、输出并通知谜语；保留 MIYU_LIST、MIYU_SUCCESS；同文件另建任务，定时 0 45 9 * * *。；DAILYNEWSCN_TASK=oilprice：获取、校验、输出并通知今日油价；保留 OILPRICE_LIST、OILPRICE_SUCCESS；同文件另建任务，定时 0 50 9 * * *。；默认日报及原九模式接口、参数、格式、成功校验和调度保持不变；抽签保留签等级颜色、卦象、全角空格换行、典故首句及省略号。；油价保留地区、日期、92/95/98号汽油、0号柴油和其他数字油号的图标及元/L格式；多地区独立处理，任一失败整体非零退出。；Node.js 标准库独立 HTTP；十秒总超时、128 KiB 限制、HTTP 200 与数据校验；无私有适配器或安装引导。；完全断网预演使用本地样本且模拟通知，不宣称真实接口成功。；统一通知开关、模块发现、十五秒超时和输出隔离；所有运行结果均汇总，通知失败不改变业务退出码。；保留时间轴横幅、起止时间、编号阶段、任务耗时统计和旧成功标记，追加唯一单行 TASK_SUMMARY；隐藏凭据与敏感字段。；无需账号；九种原任务多行标记仅作兼容输入，油价多行对应不同地区，标记不发送给接口。。
- `scripts/ddnsto.py`：申请 product_id=2 七天免费套餐并查询订单；把新套餐绑定到指定路由器；重新读取官方套餐并确认到期时间延长后才报告续费成功；识别本周免费套餐申请次数限制；只有现有套餐尚未过期才视为已完成；显示北京时间到期时间；官方返回非敏感昵称或用户名时原样显示；保留每天 09:30 的上游计划和 ddns_cookie、ddns_userid 单账号兼容参数；多账号按行独立执行，失败账号不阻断其他账号；任一失败整体非零退出；无网络预演、青龙脱敏汇总通知和带时间戳的分阶段日志；输出唯一 TASK_SUMMARY 单行 JSON 汇总。
- `scripts/deepflood_checkin.py`：执行 DeepFlood 每日签到并验证接口业务结果，支持识别已完成签到；查询并汇总可配置时间窗口内的签到鸡腿收益，保留总量、次数及平均收益；支持换行分隔的多账号独立执行和汇总状态；可选的随机延迟执行，保持原每日计划及既有参数兼容；完全断网且无等待、无副作用的预演；正式运行通过青龙 notify.py 发送脱敏汇总，支持全局通知开关，预演显示同内容通知预览；显示官方返回的非敏感账号身份、编号阶段、耗时与账号及任务统计；保留 SUMMARY_JSON 并追加唯一单行 TASK_SUMMARY，配置或业务失败非零退出。
- `scripts/durex.py`：查询并直接显示官方昵称与当前积分；每日签到；显式开启活动分享记录上报（不发布文本）；显式开启活动抽奖并验证奖品结果；每行一个账号、独立执行与失败退出；完全断网预演及本地通知预览；青龙脱敏通知、时间轴日志、账号统计与单行结构化汇总。
- `scripts/enshan_checkin.py`：使用 Cookie 验证登录，保留签到页 WAF 解码、论坛页回退和响应 Cookie 更新。；获取隐藏字段、退出链接或 JavaScript 中的 formhash，提交每日签到，严格识别成功及今日已签到。；在已验证的签到响应提供连续签到天数时展示天数，并在结构化账号结果中输出；未提供时不推测。；签到前后查询恩山币和积分，保留四个积分页地址回退与临时错误重试，展示余额变化。；展示官方公开用户名、用户组及贡献，隐藏 Cookie、会话及原始响应。；每行一个账号独立执行，任一失败非零退出，配置错误同样非零退出。；保持每日 12:39 定时、兼容旧参数及可选随机启动延迟，默认无等待。；完全断网配置预演，跳过登录、查询、签到和通知网络发送，不宣称真实业务成功。；带时间戳的分阶段日志、账号及任务统计，保留 SUMMARY_JSON 并输出唯一单行 TASK_SUMMARY。；按全局开关生成或发送青龙脱敏通知，通知不可用或失败不改变业务退出码。；已验证签到后，按上游移动签到页与既有桌面签到页顺序读取今日签到积分和总签到天数；连续签到天数优先保留签到响应的值，缺失时补充页面值。；仅展示明确提供的非负签到统计，缺失项显示未知；可选统计读取失败不覆盖已验证签到结果。；兼容 EST_cookie 和 EST_ENABLE_RANDOM_WAIT，不再依赖浏览器可执行文件或本地凭据配置文件；Cookie 中自动获取登录身份。；正式通知增加各成功账号的余额、贡献及签到统计；配置错误、失败和断网预演也生成或发送摘要。。
- `scripts/epicfreegames.py`：查询 Epic 本周及即将免费游戏，仅筛选有效基础游戏和零价促销。；展示游戏标题、原价、促销起止北京时间及商店链接，兼容语言地区和国家设置。；合成含封面、标题、原价及免费时间的图片并发送到 Telegram；封面失败保留资料卡片，图片生成或发送失败降级完整文字报告。；保留每周六 08:00 调度及 TG_BOT_TOKEN/TG_USER_ID 单账号兼容输入，支持每行一个 Telegram 通知账号。；通过本地样例断网预演，记录带时间戳的分阶段日志、账号统计及唯一 TASK_SUMMARY JSON；业务失败返回非零退出码。；成功、部分失败、失败、配置错误和预演均生成脱敏青龙通知汇总；实际通知失败保留业务退出码，预演仅模拟。。
- `scripts/erke.py`：查询积分明细第一页五条，展示累计积分、冻结积分、可用积分和积分记录数；会员签到及明确已签到状态识别；每行一个账号，保留上游账号字段兼容，逐账号与逐阶段统计；展示接口返回的非敏感官方账号身份；完全断网预演、阶段耗时日志及单行 TASK_SUMMARY 结构化汇总；青龙脱敏通知，通知失败不覆盖业务退出码。
- `scripts/f1owkang_qingskyland_skyland.py`：鹰角登录 token 换取森空岛认证凭据，独立实现设备认证与 HTTP 签名；查询明日方舟与终末地绑定账号，逐一签到全部角色并显示官方昵称或公开 UID、渠道及奖励；支持每行一个账号、官方 JSON 凭据、可选凭据文件与合并去重；保留青龙与 Hermes 模式、Hermes 成功正文静默、通知标题与显式代理开关；完整时间轴日志、账号与子任务统计及唯一 TASK_SUMMARY 机器记录；完全断网预演，检查凭据解析、签名及两种游戏请求契约；任意账号失败非零退出；成功、部分失败、失败或配置错误后生成脱敏通知，实际运行通过青龙 notify.py 投递并支持发现位置回退。
- `scripts/fnnasclub.py`：显示论坛提供的公开昵称；获取签到参数并执行每日签到；识别今日已打卡并避免重复签到；读取并脱敏显示我的打卡动态；每行一个账号，独立执行与失败汇总；完全断网预演、时间轴日志和单行结构化汇总；正式运行后发送青龙脱敏通知，通知失败保留业务退出码。
- `scripts/forum_download.py`：读取指定版块的主题列表，并按上游顺序读取前三个帖子的附件；下载显式启用，不保存文件，间隔两秒。；访问论坛首页并验证登录状态，不把首页访问成功推断为奖励到账。；提供 dsu_paulsign 和 qiandao.php 两种显式签到开关，保留原端点、方法、签到参数和已签到判断。；独立解析 Discuz 积分页面并显示可验证的积分项目，替代私有 get_coin 导入；页面不兼容时明确失败。；官方首页返回用户名时显示该非敏感身份，账号日志不输出 Cookie、表单令牌、地址参数或原始响应。；多账号独立运行、请求超时、同站重定向限制、明确业务成功检查、断网预演、脱敏通知和单行结构化任务汇总。；显式 work 动作访问打工插件，最多点击八次，遇间隔限制停止点击，再领取奖励；只接受 messagetext 中明确成功或今日已完成提示。；保留默认 visit,credits、账号 JSON 参数及每日 08:20 计划；与现有动作在同一规范脚本运行。。
- `scripts/fwxs_checkin.js`：登录有效性检查并展示官方公开 UID；废文网每日签到；以个人中心总签到天数增长确认成功；查询总签到天数与连续签到天数；明确的北京时间当天签到记录支持已签到判定；每行一个账号独立执行，兼容原 fwxs 变量与首个 # 后的昵称备注解析；完全断网预演及参数检查；青龙通知、分阶段脱敏日志、逐账号统计与单行结构化任务汇总。
- `scripts/fxh.js`：每日查询当前积分；每日执行芬享汇签到，显示可解析的奖励积分与已签到状态；官方返回非敏感昵称、用户名、显示名称或公开 UID 时直接展示；逐行多账号独立执行和失败退出；完全断网预演、时间轴日志、账号及任务统计、单行 TASK_SUMMARY 汇总；实际执行通过青龙通知模块发送脱敏总结；预演只模拟通知，不联网。
- `scripts/get_yys_cgvideo.py`：官网 CG 视频目录解析、按标题去重；显式开启后的媒体下载和校验清单；新增下载数量限制及视频下载成功后两秒间隔；可选官网原画首分组六链接条目的第三链接下载；已有文件经大小及摘要验证后跳过；安全文件名和链接摘要防碰撞、拒绝覆盖文件；断网预演、超时、媒体签名和传输完整性校验；任务独立处理，任一资源失败均非零退出；时间轴日志、结构化统计和脱敏青龙通知。
- `scripts/get_yys_imagelinks.py`：读取阴阳师官网原画页面，保留首个 tab-cont 内六个链接的第三个原画链接选择规则。；默认仅核验并列出素材；显式开启后保存原画，保留数字路径命名与原画目录默认值，修复未知文件名及同名碰撞。；通过任务开关读取全部官网 CG 视频分组，保存标题命名的 MP4 视频并记录 downloaded_videos.txt 标题历史。；校验已有素材文件格式并跳过下载；视频新下载数量限制与默认两秒间隔均保留。；独立实现带超时和 HTTPS 重定向校验的 HTTP 请求；检查状态码、页面结构、素材格式、大小及已知响应长度；原子落盘且不覆盖已有文件。；每种素材及每个下载项独立处理，任一失败即整体非零退出；输出中文分阶段耗时、子任务统计和唯一 TASK_SUMMARY JSON。；提供无账号、无网络、无文件写入的断网预演，覆盖原画和视频解析。；所有结果发送脱敏青龙通知；预演输出通知摘要且不调用通知服务，通知失败保留业务退出码。。
- `scripts/hellogithub.py`：每月 1 日 08:00 查询 HelloGitHub 最新月刊及发布时间；比较持久化期号，跳过已经提醒的月刊；动态提取页面构建标识并读取完整分类项目内容；展示刊名、简介、发布时间、期号、项目与分类数量、项目名称、语言、描述、星标、复刻、关注数及项目链接；按最多 3900 字符分段推送全部内容，保留在线阅读和上游 GitHub 链接；支持旧版期号状态文件迁移、断网预演、时间轴日志和结构化总结；通过青龙通知助手发送月刊和脱敏任务总结。
- `scripts/hifiti_checkin.py`：HiFiTi 每日签到与明确业务结果核验；HiFiHi 每日签到与明确业务结果核验；兼容原凭据参数和旧版值格式，完整 Cookie 不截断；每行一个账号，两个站点与不同账号之间隔离会话；保留每天 06:30 的计划、随机启动等待和同站点账号间等待；读取官方非敏感昵称、用户名或公开身份字段并显示，禁止凭据片段充当身份；完全断网预演、配置检查、按账号阶段日志与单行结构化任务汇总；成功、部分失败、失败、配置错误和预演均生成脱敏通知摘要，真实模式通过可用青龙通知模块发送，预演仅模拟发送。
- `scripts/hlyl.py`：查询账号信息，展示接口提供的非敏感公开身份，屏蔽手机号和凭据；查询当日签到状态、周任务进度和月签到天数；每日签到，已签到时跳过；签到后复查状态并显示可用积分和成长积分奖励；显式开启的有界活动抽奖，显示安全奖品名称，单次失败即停止后续抽奖；查询积分余额；逐行多账号独立执行、超时及明确业务核验、任一账号失败时非零退出；完全断网预演、时间轴阶段日志、账号及任务统计、单行 TASK_SUMMARY 记录；通过青龙通知组件发送脱敏总结，通知失败保持业务退出码；断网预演禁止远程通知。
- `scripts/hsay.py`：查询并显示官方返回的用户昵称，隐藏手机号及凭据；从积分流水获取签到所需的公开用户 ID；查询连续签到天数；按原活动和门店参数生成签名并签到，显示奖励名称、数量和计算的连续签到天数；逐行多账号独立运行，失败闭合与断网预演；青龙脱敏通知、阶段耗时、账号及任务统计和唯一 TASK_SUMMARY 输出。
- `scripts/huaruntong_wx.py`：华润通微信版加密签到，仅以官方业务码 S0A00000 确认成功；兼容原签到请求全部可配置参数及默认值，保持原 cron；逐行多账号独立执行、参数校验和失败非零退出；展示官方返回的非敏感昵称、用户名、显示名称或公开身份；完全断网预演、逐阶段耗时和脱敏结构化统计；青龙通知汇总，通知不可用不影响业务退出码。
- `scripts/hykb_gamesign.js`：发现官方游戏签到集合中未结束的活动并去重，无法解析时失败闭合。；逐活动登录并每日签到，明确识别签到成功及今日已签，返回累计签到天数时显示。；可选择记录试玩前置动作，真实运行等待 65 秒后重新登录、签到并核验结果。；可选择记录分享前置动作，重新登录、签到并核验结果，不发布公开文字。；识别失效凭据，显示官方返回的非敏感昵称、用户名、显示名或公开 UID。；多账号独立执行，失败非零退出，完全断网预演、时间轴日志、逐账号统计和单行 TASK_SUMMARY 汇总。；真实执行后使用青龙通知模块发送脱敏汇总，通知失败不改变业务退出码；预演仅展示通知内容。。
- `scripts/ikuuu_checkin.py`：保留邮箱密码登录与官方 ret=1 核验，兼容 IKUUU_ACCOUNT 和旧 ikuuu 参数；新增 Cookie 会话签到，支持 IKUUU_COOKIES、备注前缀及同一规范账号变量中的 Cookie 输入；每日签到要求官方 ret=1 或明确的今日已签到证明，成功说明中提取流量奖励；保留可选个人资料读取与非空响应核验；资料失败继续签到但账号整体失败；新增剩余流量查询，解析官方 /user 页面及 originBody 编码页面中明确的剩余流量字段；保留安全官方昵称、用户名、显示名称或公开 UID 的原值展示；凭据、手机号和会话值不输出；支持官方主机名配置，未设置时保留邮箱模式原域名及 Cookie 模式上游域名；换行多账号独立处理、凭据字段仅首次分割、失败非零退出；保留每天 21:00 调度、可选随机错峰和云函数 handler 入口；保留分阶段时间轴日志、耗时、账号与任务统计、IKUUU_SUMMARY 及唯一 TASK_SUMMARY；使用青龙 notify.py 发送脱敏摘要，保留上游可选 PushPlus 通知，通知故障不改变业务退出码；完全断网预演参数、各模式请求计划及通知摘要，不导入通知模块、不等待、不修改账号状态。
- `scripts/imaotai.py`：查询官方应用版本、当日北京时间场次及门店资源；按经纬度选择最近有库存门店，或按省市选择库存最多门店；支持多个商品，保留原默认商品列表；显式开启后以原 AES 协议提交申购，仅业务码 2000 判定请求成功；领取耐力，仅业务码 200 判定成功；多账号独立执行及失败闭合退出码；完全断网预演、阶段日志及唯一结构化汇总；显示官方返回的非秘密账号身份；正式任务结果通过青龙通知，通知故障不改变业务退出码。
- `scripts/index.js`：通过官方收藏页跳转获取并原样显示公开 UID，也支持手动指定公开 UID；分页获取全部公开收藏，校验明确业务成功、总数稳定、无重复以及分页完整性；读取每个作品全部原图页；图片页查询与图片下载分别限制为三个并发任务；以标题加作品 ID 建目录、标题加页码命名图片，保留规范候选保存路径及旧目录兼容检查；跳过已有有效图片，修复无效普通图片文件；原子创建下载结果以避免并发覆盖；原图仅接受 HTTPS 图片域，隔离账号 Cookie，校验图片类型、文件头、大小和完整性，设置请求超时；支持逐行多账号、旧版 cookie/output/proxy 配置和完全断网预演，逐账号隔离失败；按编号阶段打印带时间戳的脱敏结果及耗时、账号和任务统计，保留收藏成功日志并输出唯一单行 TASK_SUMMARY；调用青龙通知组件发送脱敏总结，支持全局通知开关；预演禁止外部投递，通知失败或缺失不改变业务退出码。
- `scripts/iqiyi_checkin.py`：VIP信息、官方身份、会员等级、到期时间及成长值查询；自然月签到、连签天数及已签到识别；网页积分签到及逐项业务确认；可选普通抽奖次数查询，保留单次会员抽奖并支持全部机会抽奖和奖品展示；保留单次摇一摇并支持显式连续摇一摇、奖品展示和机会耗尽识别；显式领取白金任务次数及五次白金抽奖，逐次验证结果；显式领取V7免费升级星钻权益，变更后查询会员状态；逐行多账号、旧 Cookie 参数兼容和每日10:05调度；完全断网预演、阶段日志、账号统计及单行 TASK_SUMMARY；青龙通知、PushPlus与Server酱后备及总开关，通知失败保留业务退出码；显式启用 VIP 自动签到并展示当月成长值，不误报为本次新增成长；显式启用每日成长任务查询、任务参与、完成通知和奖励领取，逐项检查业务代码并刷新状态，最多六轮；兼容上游 dfp Cookie 字段，保留 __dfp 优先级及字段值中的等号。
- `scripts/jc_checkin.py`：初始化会话并使用邮箱密码登录机场面板；每日签到及严格业务结果校验；逐行多账号及上游单账号参数兼容；返回非敏感官方账号身份时显示原值；HTTPS 证书校验、请求超时、响应大小限制和拒绝重定向；断网预演、阶段统计及单行 TASK_SUMMARY 汇总；青龙脱敏通知及显式开启的 HTTPS PushPlus 兼容推送。
- `scripts/jcqd.py`：默认 ikuuu 官方导航域名发现、登录及每日签到；通过明确任务开关保留上游可选 v2free 和 gw树洞登录签到，各站独立会话；多账号逐行配置、旧单账号参数兼容、账号及站点失败隔离；HTTPS 证书校验、超时、响应大小限制、拒绝重定向和登录失败闭合；官方非凭据昵称、用户名、显示名称或公开 UID 核对；断网预演、逐阶段日志、账号统计、单行 TASK_SUMMARY 汇总及青龙通知。
- `scripts/jingyiluntan_sign.py`：读取登录页面与表单令牌，显示官方返回的昵称；每日签到并区分成功和今日已签到；显式开启后按上游流程读取热门帖、逐帖评分 +1 和显示积分，保持两秒间隔；评分附言优先从一言读取文字、作者及出处，按策略格式注明出处；所有提供方失败回退本地文字；多账号独立执行、超时和明确业务成功校验；完全断网预演、脱敏时间轴日志和单行 TASK_SUMMARY 结构化统计；成功、部分失败、失败、配置错误及预演均生成脱敏通知摘要；预演仅模拟通知。
- `scripts/jissbon.py`：查询官方昵称与当前积分；每日签到；分享奖励登记，不发布分享文字；显式开启后最多执行十次活动抽奖；换行多账号独立处理与失败非零退出；完全断网预演、脱敏通知和时间轴任务统计。
- `scripts/jyj.py`：查询官方昵称及可用积分、历史使用和历史总积分；每日签到和每日水滴领取；显式开启三轮拍一拍实际计时游戏和三次幸运转盘；显式开启文章点赞、订阅、调研、分享任务奖励；分享接口不发布文本；兼容jyjRun健康运动领取开关，默认关闭；查询庄园种植状态及可种植药材，显式指定种植和浇水上限；独立活动开关支持本人照片上传、AI识别、春日活动拍照打卡及打卡查询；独立活动开关支持酒柜抽奖和红包雨；显式提供本人真实成绩后执行一轮药材游戏；换行多账号、断网预演、脱敏日志、业务失败退出与青龙通知。
- `scripts/kgqq.py`：查询并显示官方返回昵称及签到前后鲜花余额、计算本轮鲜花增量。；领取上游六类签到入口奖励：1、2、4、16、128、512。；显式开启后执行四类抽奖：入口 1 的类型 1、2，入口 4 的类型 104，以及类型 103。；显式开启后使用同账号真实鉴权参数查询音乐卡片，选择最高鲜花卡片，按上游大于 10 或大于 1 且小于 10 的档位领取对应互动奖励。；查询 VIP 状态，VIP 用户领取日奖励并显示福利道具数量，非 VIP 用户跳过领取。；每行独立多账号、完全断网预演、请求超时、固定主机及拒绝重定向、响应大小限制和明确业务成功判定。；时间轴分阶段日志、账号与子任务统计、单行 TASK_SUMMARY 汇总、青龙脱敏通知及通知失败保留业务退出码。。
- `scripts/kjwj.py`：使用邮箱密码登录科技玩家，获取签到令牌；查询当日签到状态、当日获得积分和总积分；未签到时自动签到，并复查当日状态确认完成；已签到时跳过写操作并显示积分；显示官方返回的非秘密账号身份，屏蔽凭据和手机号；每行一个账号独立执行，失败返回非零退出码；完全断网预演、分阶段日志、每账号统计和单行结构化任务总结；正式执行后通过青龙通知发送脱敏总结，预演时显示通知摘要；通知失败保留业务退出码。
- `scripts/kuaishou_reward_status.py`：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。
- `scripts/kuku_daily.py`：查询每日积分任务面板并验证业务登录状态；领取每日登录 LOGIN 奖励；领取对话 CHAT 任务奖励，不实际发送对话；明确 SUCCESS 且奖励为零时识别幂等已完成；逐行多账号及旧 Cookie 请求头、编辑器 JSON、对象格式兼容；使用 --only 序号选择一个账号；可选 HTTP/HTTPS 代理；显示官方响应中的昵称、用户名、显示名称或公开 UID；带阶段耗时、账号与任务统计的脱敏日志及单行 TASK_SUMMARY；青龙通知及全局关闭开关，通知失败保留业务退出码；完全断网参数预演及拟发送通知摘要。
- `scripts/kurobbs_sign.py`：查询社区每日任务完成进度；查询鸣潮默认绑定角色并展示官方公开身份；库街区每日签到及连续天数、累计天数和奖励展示；鸣潮每日签到、已签到识别及签到后状态核验；展示当月普通签到奖励和响应提供的限时循环签到奖励；浏览鸣潮今州茶馆帖子并核验进度；显式开启后点赞不同帖子并核验进度，不取消原有点赞；显式开启后提交帖子分享进度并核验完成，不发布文字；逐行多账号及旧单账号变量兼容；完全断网预演、时间轴日志、脱敏统计和青龙通知。
- `scripts/l.py`：Cookie 登录身份校验并显示官方返回的公开用户名和信任等级；按原有浏览开关与数量参数，从首页发现并随机读取话题，校验标题及帖子正文；查询访问天数、浏览话题、已读帖子、阅读时长、给出点赞、收到点赞及发帖数；显示上游 TL0 至 TL1、TL1 至 TL2 的参考升级要求和达标情况；每行一个账号，账号互相隔离，任一账号失败返回非零退出码；完全断网预演、按阶段记录脱敏结果、账号与任务统计及单行结构化汇总；通过青龙通知模块发送脱敏汇总，失败或不可用不改变业务退出码。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：使用 Cookie 执行 Leaflow 每日签到；自动识别 CSRF 隐藏字段并提交签到表单；明确识别成功、今日已完成、会话失效和失败结果；在服务返回时提取当日签到奖励；支持换行多账号独立处理并生成结构化汇总；提供有限重试、请求超时和可选随机执行窗口；提供完全断网的预演配置校验；在官方页面明确返回昵称、用户名、显示名称或公开 UID 时显示可安全核对的账号身份；支持青龙通知模块发现及全局通知开关，发送脱敏任务汇总，通知失败保留业务退出码；输出时间轴阶段、账号及子任务统计，并保留 ACCOUNT、SUMMARY 输出及追加单行 TASK_SUMMARY；兼容上游非敏感配置参数，排除历史奖励区域并限制跨源重定向和响应大小。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：Cookie 登录配置检查，支持每行一个账号并保留 Cookie 值中的等号；从本站页面读取当前登录公开 UID 并按返回值显示，获取签到令牌；咔叽网单每日签到，明确区分签到成功、明确今日已签到和未确认成功；HTTPS 证书验证、请求超时、响应大小限制和同站安全跳转检查；完全断网预演，不验证真实业务成功，不产生签到动作；按账号及编号阶段输出带时间戳的脱敏日志、耗时和统计，保留账号信息及签到信息输出，追加单行 TASK_SUMMARY JSON；成功、部分失败、失败、配置错误和预演后尝试青龙脱敏通知；通知失败保留业务退出码。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：每日签到，支持随机奖励或固定奖励模式。；随机时间窗口、多账号计划排序和带时间戳的等待倒计时；保留每天 04:23 的调度。；近 30 天签到收益分页查询，显示签到天数、鸡腿总数及日均收益；覆盖不完整或字段异常时明确失败。；按官方接口返回原值显示非敏感昵称、用户名、显示名称或公开 UID。；每行一个账号，独立执行并汇总失败退出码。；完全断网预演、参数检查、分阶段时间轴日志、账号统计及单行 TASK_SUMMARY JSON。；所有任务结果均尝试发送脱敏青龙通知；支持全局开关和通知目录发现，通知故障保留业务退出码。。
- `scripts/lizhixu_ql_script_hub_youdao.py`：HTTPS 会话刷新；同步奖励并核验 rewardSpace 字段；每日签到并核验 space 字段；三次广告空间奖励及独立关闭开关；汇总已核验的空间奖励；显示官方返回的非敏感账号身份；换行多账号独立执行与失败退出码；完全断网预演及参数检查；分阶段计时、账号与任务统计及单行结构化汇总；青龙脱敏通知，兼容 notify.py 和 sendNotify.js，失败不影响业务退出码。
- `scripts/lobsterai_checkin.py`：每天签到：查询活动、查询状态、幂等提交和独立复核；明确已签到时不重复提交。；显示积分、连续签到和活动领取天数。；自动查询官方客户端版本，一次运行内共用版本；失败保留上游兜底版本，支持 --version 覆盖。；AT 临近到期时通过 RT 自动续期，以私密原子缓存支持滚动续期。；换行多账号和 --only UID 筛选；环境变量优先，可用 --auths 显式指定本人 JSON 凭据目录。；保留 --base HTTPS 地址覆盖；凭据请求拒绝重定向。；完全离线预演，不访问业务、版本、推送接口，不读写续期缓存。；青龙通知和可选 PushPlus 微信推送；所有结果生成脱敏总结，通知失败不影响业务退出码。；输出时间轴、编号阶段、账号及任务统计，并输出一个 TASK_SUMMARY JSON 汇总。。
- `scripts/loomy_daily.py`：每日首次登录刷新每日赠送积分，按天幂等，以 HTTP 成功且业务码 000000 核验。；--tasks 查询八项新手任务的分组、标题、积分与完成进度。；显式设置 LOOMY_ONBOARDING=1 批量领取未完成新手任务，--no-onboarding 可关闭；--claim KEY 单独领取一项。；八项任务共 10000 分：首次消息、选择技能、生成 PPT、设置定时、安装技能、远程控制、创建搭子与分享搭子；仅上报领取，不实际执行对应应用操作。；结清后保存凭据指纹与任务进度，避免重复查询；--refresh 忽略本地记录强制核验。；换行多账号独立执行，--only N 筛选；官方响应提供公开身份时显示，凭据和原始响应不输出。；完全断网预演、分阶段时间轴日志、每账号与最终统计、一条 TASK_SUMMARY 结构化汇总。；青龙组件推送脱敏总结，支持全局及 --no-notify 开关，保留四种上游可选推送渠道作为兼容后备；通知故障不改变业务退出码。。
- `scripts/lynkco_qinglong_single.py`：AppCode优先续期、HMAC签名兜底及静态令牌回退；今日签到状态查询、自动签到和签到后复查，已签到时跳过；连续签到天数和签到卡查询；任务前后能量体积分查询；五页动态文章查找及上游备用文章；可选文章分享两步链及完整三步链回退，核验分享前后积分变化；多账号独立处理、官方非秘密身份展示、任何账号失败非零退出；青龙及可选Bark脱敏通知，通知失败保留业务退出码；完全断网预演、分阶段日志和单行结构化总结；旧账号变量及显式只读本地配置兼容。
- `scripts/main.py`：抓取 Wallhaven 最新列表，默认保留第 1 至 5 页。；按上游 thumb-info 中的六位壁纸编号及 PNG 标记下载 JPG 或 PNG 原图。；按当天日期归档壁纸，校验图片格式；已有有效图片跳过，跨页重复去重。；支持显式设置保存目录和抓取页数；请求设定超时、响应类型与大小限制。；各页面及图片独立处理，任何失败使整体非零退出。；完全断网预演、分阶段时间轴日志与单行 TASK_SUMMARY 汇总。；通过青龙 notify.py 发送脱敏任务总结；支持全局通知开关，通知不可用保持业务退出码。。
- `scripts/mifan_optimized.py`：用户名和密码登录及登出，保留上游gid与MD5密码协议；查询米粒余额及展示官方非凭据账户身份；每日签到与已签到识别；显式动态点赞，每次最多20条并保存成功进度；显式自动评论，每次最多10条并保存成功进度；无奖励时停止；评论优先一言，保留作者与出处，所有声明故障回退本地文本；显式查询最近签到记录并补签；多账号逐行配置与账号隔离进度；完全断网预演、分阶段脱敏日志、机器汇总及青龙通知。
- `scripts/mimotion.py`：手机号或邮箱及密码登录 Zepp Life，核验授权与完整登录凭据，显示官方非敏感账号身份。；显式开启后在设定的随机范围内修改本人当天运动记录的步数并上传，要求接口 code=0 且 message=success。；优先获取远程时间戳，失败使用本地毫秒时间；HTTP 表单编码、超时、响应大小限制及禁止凭据重定向。；多账号独立执行、失败非零退出、断网预演、脱敏分阶段日志、单行 TASK_SUMMARY 汇总及青龙通知。。
- `scripts/netease_task.py`：登录确认并显示官方非敏感昵称或公开 UID；手机签到与网页签到，识别业务码 -2 的今日已完成；可选官方 weapi 网页签到，显示返回积分；云贝签到与已完成任务奖励领取；VIP 成长值批量领取，保留任务查询与按任务 ID 领取备用接口；显式开启的模拟听歌，保留四个榜单获取链路及 300 首成功判定；等级与累计听歌数量查询；每行多账号、旧 Cookie 变量、注释与整行引号兼容；青龙通知失败后依次尝试 PushPlus 与 Server酱，保留独立 Bark 通知；完全断网预演、编号时间轴日志、逐账号统计与唯一结构化任务汇总。
- `scripts/nga_checkin.py`：每日签到，明确识别签到成功与今日已签到；兼容原 UID|Token 凭据与 iOS 校验码、旧版小写环境变量；展示官方返回的非敏感身份及签到连续天数、累计天数；登录失效和 iOS 客户端校验异常提示；可选日常任务 2、131、30；可选免广告及 N币视频任务；可选五次分享记录与分享奖励；默认查询资产统计；保留随机启动延时、动作间隔与请求超时设置；多账号独立执行与整体失败退出码；完全断网预演、时间轴日志、结构化汇总、青龙脱敏通知。
- `scripts/nodeseek.py`：每日零点签到，支持随机奖励或固定奖励。；保留 curl_cffi 指纹模拟及默认 chrome110。；保留签到前随机延迟 0～5 分钟。；完整 Cookie 按行配置多账号，各账号独立执行。；完全断网预演、分阶段脱敏日志和单行结构化统计。；显示接口返回的非敏感昵称、用户名、显示名称或公开 UID。；正式运行通过青龙通知助手发送成功、部分失败、失败或配置错误摘要；预演只输出摘要。。
- `scripts/nodeseek_checkin.py`：NodeSeek 每日签到；已签到状态识别；近 N 天签到鸡腿收益统计；可选随机奖励模式与多账号错峰执行；多账号独立处理与脱敏汇总通知；断网预演配置验证。
- `scripts/nte.py`：刷新用户中心令牌，保留 1.2.5 客户端请求头及 ds 签名。；塔吉多社区签到及经验、金币结果显示。；自动发现游戏角色，支持各账号角色配置与兼容全局角色配置。；游戏角色签到，保留游戏编号回退链；重复签到要求官方状态明确确认 todaySign。；查询签到累计天数和今日道具奖励；查询失败给出警告，不替代签到业务状态。；查询云异环剩余、免费、充值时长，展示每日首登、首次游戏赠送、VIP剩余和待领取消息数量。；多账号独立执行、断网预演、阶段日志、官方非敏感身份展示、结构化汇总与青龙脱敏通知。。
- `scripts/officeace_daily.py`：默认领取每日签到奖励和一次性新人礼，保留 V11-HMAC-SHA256 签名接口；--query 只读查询奖励额度积分；--only 指定账号，支持换行多账号和兼容单账号参数；配套凭据及 HTTPS 地址检查和凭据获取说明；业务码、奖励列表与积分读数校验；任一账号失败非零退出；完全离线预演配置、签名及执行计划；阶段时间轴日志、官方非敏感身份、账号统计和 TASK_SUMMARY 汇总；青龙脱敏结果通知与企业微信、PushPlus 兼容推送，通知失败保留业务退出码。
- `scripts/ole.py`：Ole 微信小程序账号签到；保留原账号字段、门店与城市默认值及定时表达式；多账号独立执行与失败闭合退出；完全断网预演及参数检查；脱敏分阶段日志、账号统计与单行任务汇总；青龙通知摘要与全局开关；断网预演模拟通知。
- `scripts/passnat_checkin.py`：PassNAT 每日签到；今日已签到的幂等成功识别；查询并显示套餐、流量、隧道、状态和到期时间；显示最近登录地区、运营商和 IP；可选随机错峰执行；换行分隔的多账号独立处理；青龙脱敏汇总通知；完全断网预演。
- `scripts/psnine.py`：每日 PSNINE 祈祷签到；识别当天已经签到并展示累计祈祷天数；保留上游 do 接口及 psnid、shell 配套凭据；多账号独立执行和失败非零退出；完全断网预演、分阶段日志和单行结构化总结；实时任务结束时发送脱敏青龙通知，预演展示本地通知摘要；响应提供公开用户名时展示账号身份。
- `scripts/pt_sign_v5.js`：蝴蝶、CARPT、AFUN 三站每日签到，支持站点选择与签到页地址覆盖；按站点分别配置多账号完整 Cookie，维护独立的服务器 Cookie 罐并识别登录失效；兼容 SafeLine 云端挑战、上游本地计算及验证后重放签到页；解析今日已签到状态、连续签到天数、本次奖励和累计奖励；仅明确业务证据判定成功；稳定浏览器请求头、表单编码、同域重定向、可选代理、超时、受控重试及额外请求头；保留飞书、Bark、Server 酱、钉钉、企业微信和自定义 Webhook 推送载荷，并增加青龙统一脱敏通知；显示站点响应中的用户详情链接所提供的用户名与公开 UID，不输出凭据或手机号；完全断网预演、分账号阶段日志、任务统计和单行 TASK_SUMMARY 结构化汇总。
- `scripts/qoder_airscript.js`：逐账号显式开关，兼容原账号 JSON 及两种访问、刷新令牌字段命名；优先使用访问令牌，缺少时刷新；活动查询 401 后刷新并重试一次；中国区和国际区活动强制刷新查询，支持同批账号指定不同地区；逐项领取全部可领 Credits 活动，累计额度并显示响应提供的有效期；识别有效窗口内今日已领取、明确的幂等重放、活动未开放及待下发；支持仅刷新令牌和指定账号的环境变量及兼容命令行开关；兼容标准及 data 包装响应、device_token 字段、jobToken 刷新路径和 campaignKey 标识；保留 Server酱、PushPlus、企业微信逐账号通知以及青龙汇总通知，全局开关控制；显式配置私有账号文件时原子写回轮换令牌，仅环境变量时只保存于内存；显示官方返回的非敏感身份，提供分阶段日志、逐账号统计及唯一 TASK_SUMMARY；完全断网预演，配置校验，多账号独立执行及失败非零退出。
- `scripts/quark_signin.py`：验证夸克账号 Cookie 并显示官方返回的昵称或公开身份；查询当日签到状态，识别今日已签到；领取每日存储空间奖励并展示奖励和连签进度；换行配置多账号，独立处理并汇总失败；可选随机延迟、请求超时、完全断网预演；脱敏时间轴日志、账号及任务统计、结构化汇总和青龙通知；失败时输出固定响应字段的类型及有限数字业务码，辅助定位问题且不输出原始响应。
- `scripts/raccoon_daily.py`：每日触发积分发放，以北京时间今日正积分账单核验签到成功。；分别领取首次电脑端、手机端登录奖励，检查业务码和 granted，哈希台账避免重复探测。；--query 只查询今日入账，不触发发放、不领取奖励、不写台账。；--skip-onboarding 跳过新手奖励、--only N 筛选账号、--no-notify 关闭通知。；每行一个账号，支持备注|令牌与 Bearer 格式，各账号和奖励独立处理。；支持配置 HTTPS 站点和本地台账路径。；优先青龙通知，保留 PushPlus、Bark、企业微信、钉钉和面板通知兼容渠道。；完全断网预演、时间轴日志、官方非秘密账号身份及单行 TASK_SUMMARY 汇总。。
- `scripts/rainyun.py`：使用雨云用户名和密码登录，保持登录 Cookie 与 CSRF 令牌。；执行每日签到并领取积分，仅以 HTTP 状态和结构化业务码确认成功。；查询并展示账号积分，展示接口返回的非敏感昵称、用户名或公开 UID。；业务步骤完成或失败后，在已成功登录的情况下执行退出登录并核验结果。；支持每行一个账号的独立会话和失败隔离。；提供完全断网预演、分阶段脱敏日志、账号与任务统计及单行 TASK_SUMMARY 汇总。；通过青龙 notify.py 发送脱敏统计通知，支持全局开关；配置错误和部分失败同样汇总，预演跳过实际发送。。
- `scripts/rousi_checkin.js`：普通模式每日签到，并按服务端今日日期识别已签到，避免重复操作；读取积分余额，保留站点自定义积分名称；展示分享率、当前魔力值及累计上传下载量；展示连续签到、已返回签到日期累计天数、本次奖励及连续签到奖励；兼容 Token、Bearer 前缀、Cookie、小写变量和编号变量的逐行多账号认证；可选 PushPlus HTTPS 汇总通知，保留渠道参数兼容；成功、部分失败、失败、配置错误均尝试青龙脱敏通知，预演仅模拟通知；完全断网预演、带阶段耗时的时间轴日志、账号与任务统计、单行 TASK_SUMMARY 输出。
- `scripts/sf.py`：使用分享登录凭据获取账号会话并显示官方返回的昵称、用户名或公开用户编号；自动签到、统计连续签到天数并显示签到礼包名称与有效期；查询积分任务列表并解析直接任务代码或跳转链接内任务编号；执行明确允许的日常积分任务，跳过非日常任务及已完成任务；领取已执行任务的积分奖励并统计获得积分；查询当前可用积分；支持换行多账号、旧账号字段及显式旧配置文件输入；完全断网预演、分阶段脱敏日志、账号统计及单行结构化任务汇总；正式运行向青龙通知模块提交脱敏汇总，通知失败保持业务退出码。
- `scripts/sfsu_checkin.py`：验证顺丰速运登录会话；每日签到并识别已签到状态；查询积分、完成安全的积分任务并领取奖励；查询丰蜜、完成丰蜜任务、执行大冒险和容量扩充并领取奖励；经显式授权后领取生活特权券；每月 26 至 28 日执行会员日非消费任务、免费抽奖、红包合成和 8 级红包提取；支持多账号独立执行、完全断网预演、脱敏汇总和青龙通知。
- `scripts/sgs.py`：获取官方账号姓名与积分，展示非秘密身份；每日签到并检查业务成功；显式开启后随机检索未读文章并阅读最多五篇，限制分页次数；显式开启后执行五次工社服务访问计数；显式开启后执行五次热门活动浏览计数；换行多账号、失败非零退出；完全断网预演、青龙脱敏通知与单行结构化汇总。
- `scripts/shuyi.py`：获取书亦烧仙草滑块验证码；使用 OpenCV 模板匹配识别滑块位置；使用 AES 加密并校验滑块，校验成功后签到；展示签到天数和所得积分；显示官方返回的非敏感昵称、用户名或公开账号标识；保留 sysxc_auth 参数名，支持每行一个账号独立执行；完全断网预演，不导入通知模块或发送任何推送；青龙通知和可选 PushPlus 脱敏推送；带时间戳的分阶段日志、账号统计和单行 TASK_SUMMARY 汇总。
- `scripts/sign_in.py`：多账号看雪论坛签到，支持同账号 Cookie、CSRF token 和可选 User-Agent；兼容显式指定的旧配置文件及嵌套账号结构；使用独立标准库 HTTP 请求，固定原签到端点，限制超时及响应大小并核验业务码 0；显示官方返回的非敏感昵称、用户名、显示名称或公开 UID，并展示纯数字奖励积分；完全离线参数预演、按阶段脱敏日志及单行结构化任务汇总；青龙通知及全局通知开关，通知不可用不改变业务退出码。
- `scripts/skland_daily.py`：通行证 Token、森空岛 cred/token 和手机号密码登录，保留官方授权换取及请求签名；自动获取临时设备标识或使用用户指定标识；获取版区及今日检票状态、版区筛选、每日检票及避免重复检票；配置数量的帖子浏览、显式开启的点赞和分享任务，保留帖子分页；保留 --dry-run、--actions、--zones、--version 命令行参数及旧序号账号输入；多账号独立执行、HTTP 超时、禁止重定向、业务码核验和失败闭合退出；完全断网配置预演、时间轴阶段日志、账号及任务统计、单行 TASK_SUMMARY JSON、脱敏通知；显式 attendance 动作获取明日方舟所有绑定角色，逐角色签名签到并展示奖励名称与数量；游戏角色官方昵称与公开 UID 原样展示，单角色失败继续其他角色，任一失败整体非零退出；保留维护候选每日 08:00 调度；原始游戏签到为每日 08:30，可单独配置 attendance 并设置 30 8 * * *；显式 endfield 动作获取终末地全部绑定角色，逐角色空请求体签名签到，按资源映射展示奖励名称与数量；终末地官方角色昵称和返回的公开 UID 原样展示；单角色或绑定记录失败继续其余角色，任何失败导致账号及进程失败；独立标准库 HTTP 实现，无需 SecuritySm、utils、notifier 或私有工作流仓库；青龙通知组件为可选运行环境集成。
- `scripts/skland_demo.py`：鹰角通行证登录，兼容旧版 TOKEN 和官网单行 JSON 响应输入；手机号密码或已有短信验证码登录；显式动作发送登录验证码；内置数美设备标识计算，也可使用同账号显式提供的设备标识；读取绑定角色，显示官方昵称或公开角色编号；明日方舟所有绑定角色签到并显示奖励；终末地所有绑定角色签到并显示奖励；可选游戏任务开关和签名令牌刷新；多账号独立处理、超时和严格业务成功码校验；完全断网预演、分阶段日志、账号及任务统计、单行结构化汇总；通过青龙通知模块发送脱敏总结，通知失败保留业务退出码。
- `scripts/skyland.py`：保留数美设备指纹协议及进程内设备凭据缓存；服务器时间校准，失败时使用本地时间；鹰角 Token 授权并登录森空岛；查询账号绑定的明日方舟与终末地角色并显示官方昵称或公开角色标识；遍历全部明日方舟绑定角色每日签到并显示奖励；遍历全部终末地角色每日签到并显示奖励；每行一个账号，独立处理账号与角色，汇总失败并非零退出；完全断网预演、分阶段耗时日志与唯一 TASK_SUMMARY 结构化汇总；通过青龙通知模块发送脱敏统计，支持全局关闭及通知失败保持业务退出码。
- `scripts/smzdm_checkin.js`：校验账号的 sk 与 sess 配套凭据；执行什么值得买每日签到并识别今日已签到状态；查询签到奖励与连续签到状态；满足条件时领取连续签到额外奖励；查询并显示接口可取得的账号身份、等级、金币和碎银概览；统计当月经验变动；支持逐行多账号独立处理与失败汇总；提供完全断网的离线预演；输出时间轴日志、兼容结果记录和单行 TASK_SUMMARY JSON；按青龙通知策略发送脱敏汇总；展示签到天数、补签卡、普通奖励和礼包明细；查询值会员总经验、等级经验及有效期；通过显式任务开关查询两处会员转盘活动并各执行一次抽奖；可显式启用原上游未默认运行的生活频道转盘入口；仅抽奖模式兼容逐行 SMZDM_COOKIE，无需签到 sk；保留原抽奖独立调度说明及请求间等待；可显式选择上游 Robot Token 签到流程，严格验证获取、签到及普通奖励响应；兼容旧 Cookie 与配套 sk 环境变量，不使用共享默认 sk；按青龙、PushPlus、Server酱顺序发送脱敏汇总并验证回退推送结果；通过显式开关执行好价点值与好文点赞，每类最多七条且逐项验证业务结果；互动前后查询账号身份、签到状态、积分、金币、碎银及未读消息，并展示资产变化；查询互动前后总经验并展示最近二十条经验记录，提示记录可能延迟；显式网页 Cookie 签到无需 sk，已签到跳过写入，写入后重新核对账号身份、签到状态和天数；网页模式展示官方账号身份、积分、经验、金币、碎银、威望、等级及签到天数；通过独立显式模式保留原固定活动单次 POST 抽奖，不与既有动态会员转盘混跑；兼容逐行 SMZDM_COOKIE_LIST 并保留原固定活动每日 15:00:45 调度说明；固定活动严格核验 HTTP、业务码和结果字段，失败不重试写入。
- `scripts/ssl.py`：支持 Cloudflare API Token 和邮箱配套 Global API Key 两种认证，兼容原有环境变量；按区域分页读取 A 记录，多个区域合并去重，检查业务成功及完整分页，单个区域失败继续检查其余区域；多个账号逐行独立运行，配置错误、区域读取失败、无 A 记录、过期或证书检查失败均返回非零；依次尝试443、8443、4443、4433、9443端口，并保留指定端口检查函数；使用系统信任库校验主机名和证书；输出证书到期时间、剩余天数及颁发者，按正常、警告、过期、失败分类并按主域名报告；保留每日零点计划及默认30天警告阈值；仅到期警告且验证成功时可返回零；完全断网预演、带时间戳的分阶段日志、逐账号与整体统计及单行 TASK_SUMMARY JSON；成功、部分失败、失败及配置错误均尝试通过青龙 notify.py 发送脱敏报告；支持全局开关及通知超时，预演仅记录摘要预览。
- `scripts/sudojia_33agilestudio.js`：邮箱密码登录并获取会话令牌；查询账户信息，显示返回的非敏感昵称、用户名、显示名称或公开 UID；每日签到获得积分；查询当前积分；按换行配置多账号，失败独立统计并非零退出；完全断网预演及配置校验；青龙脱敏通知、分阶段日志和单行结构化汇总。
- `scripts/sudojia_allgirls.js`：获取并显示官方昵称；查询每日签到状态，已签到时避免重复请求；未签到时执行签到并复查已签到状态；查询当前积分；支持逐行多账号、请求超时与账号独立失败统计；支持完全断网预演、青龙通知和单行结构化汇总。
- `scripts/sudojia_amx.js`：查询账号信息并显示接口返回的昵称，不输出手机号；查询今日签到状态，已签到则跳过重复签到；未签到时执行每日签到，并再次查询签到状态核验结果，显示可用的奖励积分；查询当前积分；按非空行支持多账号，逐账号统计，失败时非零退出；完全断网预演、阶段日志和单行 TASK_SUMMARY 结构化汇总；通过青龙 sendNotify.js 发送脱敏总结；支持全局开关、通知超时和失败隔离。
- `scripts/sudojia_authcheck.js`：所有女生账号凭据有效性检查（兼容 ALL_GIRLS_TOKEN）；安慕希账号凭据有效性检查（兼容 AMX_TOKEN）；霸王茶姬账号凭据有效性检查（兼容 BW_TEA_TOKEN）；飞牛私有云账号凭据有效性检查（兼容 FN_NAS_COOKIE）；国乐酱酒账号凭据有效性检查（兼容 GYJ_TOKEN）；厚工坊账号凭据有效性检查（兼容 HGF_COOKIE）；海澜之家-游戏账号凭据有效性检查（兼容 HLZJ_UNID）；媓钻护肤品账号凭据有效性检查（兼容 HZHFP_TOKEN）；玩拍由我俱乐部账号凭据有效性检查（兼容 INSTAX_TOKEN）；金典有机生活+账号凭据有效性检查（兼容 JINDIAN_TOKEN）；嘉立创账号凭据有效性检查（兼容 JLC_TOKEN）；植白说官方商城账号凭据有效性检查（兼容 KOZBS_TOKEN）；开天工作室账号凭据有效性检查（兼容 KTGZS_TOKEN）；库街区账号凭据有效性检查（兼容 KURO_TOKEN）；老板电器服务微商城账号凭据有效性检查（兼容 LAOBAN_OPENID）；龙湖天街账号凭据有效性检查（兼容 LONG_FOR_TOKEN）；欣都龙城账号凭据有效性检查（兼容 MALLCOO_TOKEN）；馬伍旺饮料厂账号凭据有效性检查（兼容 MAWUW_TOKEN）；美的会员账号凭据有效性检查（兼容 MIDEA_COOKIE）；摩托范账号凭据有效性检查（兼容 MOTO_TOKEN）；南方航空账号凭据有效性检查（兼容 NFHK_COOKIE）；胖哥俩肉蟹煲账号凭据有效性检查（兼容 PANG_GE_TOKEN）；皮皮世界账号凭据有效性检查（兼容 PPX_COOKIE）；水费易签到账号凭据有效性检查（兼容 SHUI_FEI_COOKIE）；特步会员中心账号凭据有效性检查（兼容 TEBU_JSON）；贴吧签到账号凭据有效性检查（兼容 TIE_BA_COOKIE）；贴吧任务签到账号凭据有效性检查（兼容 TIE_BA_COOKIE）；V2EX每日签到账号凭据有效性检查（兼容 V2EX_COOKIE）；心喜账号凭据有效性检查（兼容 XINXI_TOKEN）；兴攀农场账号凭据有效性检查（兼容 XPFARM_TOKEN）；智能电视账号凭据有效性检查（兼容 ZNDS_COOKIE）；甄稀冰淇淋账号凭据有效性检查（兼容 ZX_ICE_TOKEN）；完全断网参数预演；逐账号独立处理、失败及未验证非零退出；脱敏时间轴日志与青龙通知。
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
- `scripts/sudojia_jlc_yj.js`：保留开源平台官方昵称查询、每日签到与积分查询，以及维护版默认调度和请求接口；合并原脚本签到前后状态复查、总积分及积分变化、本周签到和本月连续签到统计；已签到避免重复写入；兼容 OSHW_COOKIE 和可选随机签到延迟，保留原脚本调度说明；只读查询网络异常最多重试三次；保留下单助手公开账号标识、签到状态、每日签到、签到复查及金豆余额查询；保留显式授权后领取待选奖励并最多补签一次，未完成则失败闭合；单一规范脚本按 JLC_TASKS 开关运行两套凭据独立的流程，并保留各自调度说明；多账号独立执行、请求超时、响应大小限制、明确业务成功判断和失败非零退出；完全断网预演、脱敏青龙通知、时间轴阶段日志、逐账号统计和唯一单行 TASK_SUMMARY 汇总。
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
- `scripts/sudojia_v2ex.js`：Cookie 登录校验及官方公开用户名显示；每日奖励领取和已领取状态识别；连续签到天数查询；账户余额查询，保留金币、银币、铜币展示；查询最近每日登录奖励账目，展示奖励说明与可识别金额；页面缺失时明确说明；逐行多账号，完整保留 Cookie 字段值；可选全局或账号专属 HTTP/HTTPS 代理；完全断网参数校验与流程预演；青龙脱敏通知、带时间戳的分阶段日志和单行机器汇总。
- `scripts/sudojia_wnna.js`：查询上海时区当日签到状态，仅在明确未签到时提交签到；展示连续签到天数，已签到账号不重复提交；查询并展示官方昵称、等级和当前积分；换行多账号独立执行，失败闭合并汇总退出状态；完全断网预演、分阶段脱敏日志和单行结构化任务汇总；青龙通知摘要，通知不可用不改变业务退出码。
- `scripts/sudojia_xhn.js`：使用抓包表单登录并检查授权令牌；每日签到并核验业务成功码；查询当前可用积分并验证响应字段；逐行多账号独立执行，任一失败整体非零退出；完全断网预演及参数检查；带时间戳的分阶段日志、账号统计和单行结构化总结；通过青龙发送脱敏汇总；预演只输出通知摘要，不联网；显示官方返回的非敏感昵称、显示名或公开账号身份。
- `scripts/sudojia_xiangwan.js`：每日登录并签到，显示本次签到玩豆奖励；查询当前玩豆余额，显示官方返回的昵称；可选受限权限 Token 缓存、有效性验证与密码登录回退；每行一个账号，逐账号隔离处理及失败退出；完全断网参数与流程预演；青龙脱敏通知、分阶段日志及单行结构化任务汇总。
- `scripts/sudojia_xiaomi_community.js`：查询并展示官方返回的公开用户名和用户编号，抑制敏感字段；每天执行微信小程序签到，展示接口确认的增加积分；查询成长值明细并按上游规则汇总展示当前成长值；支持每行一个账号、账号独立处理、失败非零退出；支持无网络预演、分阶段日志、账号统计和单行结构化汇总；通过青龙通知模块发送脱敏结果，通知失败保留业务退出码；失败时输出有限数字业务码、固定错误分类和响应类型，帮助脱敏诊断且不放宽成功条件。
- `scripts/sudojia_xinxi.js`：查询官方昵称并原样显示非凭据身份，查询执行前后喜点；每日签到并显示奖励与连续签到天数，识别今日已签到；显式启用后查询免费次数并最多执行一次免费抽奖，禁止积分抽奖；显式启用分享任务及商城浏览奖励，各最多两次，浏览提交前等待三十秒；逐行多账号独立处理、请求超时、业务状态和响应字段校验；完全断网预演、青龙脱敏通知、分阶段日志及单行结构化汇总；显示官方返回的历史喜点，不显示手机号；显式启用后查询每日任务列表；显式启用后查看会员权益奖励并识别已完成；兼容旧 xx_sso 凭据变量，统一换行多账号，拒绝旧批量删帖设置。
- `scripts/sudojia_xpfarm.js`：获取官方账号昵称并展示以核对账号；每日签到，已签到时跳过；按显式配置的任务编号完成任务并领取奖励；查询当前积分；按显式配置的次数上限施肥和浇水；查询种树类型、成长进度、水滴和肥力；换行多账号独立处理与失败退出码；完全断网预演、分阶段日志、结构化统计和青龙脱敏通知。
- `scripts/sudojia_znds.js`：验证登录状态并显示官方公开 UID；每日签到并区分签到成功和今日已完成；显式配置后访问指定用户空间；查询积分、威望、金币及Z币，要求四项均可解析；逐行多账号独立运行并汇总失败退出码；完全断网预演与通知模拟；青龙脱敏通知、分阶段耗时与单行结构化汇总。
- `scripts/sudojia_zxice.js`：校验账号登录状态并展示官方返回的非敏感昵称；查询今日签到状态，已签到时避免重复操作；每日签到并展示接口确认的奶滴奖励；查询当前奶滴值；支持每行一个账号，独立处理并汇总失败退出码；完全断网预演、分阶段时间轴日志、账号统计和单行 TASK_SUMMARY 汇总；通过青龙 sendNotify.js 发送脱敏结果通知，支持全局开关；完全断网预演生成本地通知摘要。
- `scripts/supertopicsign.py`：读取关注超话完整分页列表，检查分页结构和循环上限；识别已签到状态并跳过重复签到；按超话等级升序、降序或接口原始顺序执行；逐账号限制单次签到请求数量；多账号独立处理、显式业务成功校验与失败非零退出；从官方只读列表响应展示非敏感账号昵称或公开身份；离线凭据格式校验及模拟签到预演；分阶段脱敏日志、账号及任务统计与单行 TASK_SUMMARY 记录；青龙结果通知及全局通知开关。
- `scripts/synspoint.py`：查询官方昵称并显示非敏感身份；查询任务前后积分；执行会员签到；执行浏览会员商城积分任务（任务编号 38）；显式开启上播预约后取消，保留原活动、商品列表和等待时间，可配置活动及商品；按原定时执行，支持每行一个账号及账号间失败隔离；断网预演、脱敏通知、分阶段日志及单行结构化任务汇总。
- `scripts/tencent_video_checkin.py`：每日签到获取 V力值；领取每日观看任务奖励（不自动播放视频）；查询会员积分、等级和 V力值，保留零值展示；查询 VIP 到期时间；多账号逐行处理、兼容旧单账号变量、独立校验与失败汇总；返回官方非敏感昵称、用户名、显示名称或公开 UID 时显示身份；青龙通知及 PushPlus、Server酱顺序回退，支持全局通知开关；完全断网预演、分阶段日志和单行 TASK_SUMMARY 结构化总结。
- `scripts/tieba_checkin.py`：保留登录验证和 TBS 获取、读取关注贴吧、识别当日已签到项目、为未签到贴吧逐吧签到，沿用明确成功码和已签到判断。；直接显示官方接口返回的昵称、用户名或公开 UID，方便核对账号。；显式开启后通过 APP 成长接口验证登录、取得独立 TBS，并执行成长任务每日签到，要求业务码明确为 0。；显式开启后查询当前成长值、贴贝余额、当前等级及距离下一等级所需成长值，保留上游等级差值算法。；沿用 TIEBA_COOKIE，兼容 TIE_BA_COOKIE 的完整 Cookie 或 BDUSS 单值，每行一个账号；成长字段在同一账号 Cookie 中提供。；保留规范任务每日 08:23 计划、逐吧详情开关与可配置请求间隔；成长任务默认关闭。；完全断网预演校验账号必要字段、不加载通知组件、不产生账号副作用，并展示脱敏通知汇总。；正式执行、配置失败、部分失败或成功后尝试青龙脱敏通知，支持全局关闭，通知失败保持业务退出码。；输出逐阶段时间轴、账号及任务统计、最终状态和恰好一个单行 TASK_SUMMARY 结构化汇总。；逐吧流程和成长任务独立处理，任一任务或账号失败返回非零退出码；HTTP 有超时、响应大小限制及同主机 HTTPS 重定向限制。。
- `scripts/tjd_daily.py`：社区每日签到并复核服务端任务进度；浏览推荐帖子，按服务端剩余次数执行和复核；显式启用帖子点赞，跳过已点赞帖子并复核进度；显式启用帖子分享回调，保留平台参数并复核进度；查询绑定游戏角色昵称、等级和服务器；绑定游戏每日签到，保留 H5 鉴权及已签到业务码 5052，执行后查询确认；查询任务进度、今日及累计金币、游戏签到状态；凭据失效时用可选账号密码自动重登一次，内置 AES 加密和签名，凭据仅在内存更新；支持 --only、--account、--config、--no-notify 和 --loop；预演只运行一轮；换行多账号及旧变量兼容、断网预演、阶段日志、青龙脱敏通知和单行机器汇总。
- `scripts/trae_checkin.py`：每日查询签到状态、按需签到，官方已签不重复领取；签到后查询真实积分余额；独立 credits 模式显示总额、已用及余额，保留权益接口到用量接口的回退链；访问凭据复用、过期或鉴权失败自动续期，保留新版设备证明、IDE_PC、SOLO_PC 与旧客户端兼容链；即时安全缓存轮换后的凭据，后续复用最新访问及刷新凭据；多账号独立处理、指定账号筛选、北京时间小时轮签及早窗全签；北京时间当日去重、账号独立限流冷却、可选熔断、启动及账号间错峰；青龙通知、可选企业微信与 PushPlus，通知失败保留业务退出码；完全断网预演、编号时间轴、官方非敏感身份展示、分账号统计和唯一单行 TASK_SUMMARY；兼容显式明文及加密凭据、storage 文件和旧参数，无需桌面端或私有仓库；显式 login 交互登录，自带本机 HTTP 授权回调及隐藏粘贴表单，有限等待并通过续期接口核验；显式兼容 Trae Work auth 文件及 auth 目录，优先使用绑定 claimDeviceId 和同设备 fingerprint；兼容显式 RANDOM_SIGNIN、MAX_RANDOM_DELAY，保留规范脚本默认错峰及上游 8 点、20 点定时配置能力；网页会话换取访问令牌，长效 sessionid 在会话失效时续期并复用安全缓存；领取后复查今日签到状态，明确完成才写入去重状态；使用官方成功响应及安全缓存中的公开 UID 识别多个会话对应同一账号，单列重复配置统计；各条目仍独立核验签到状态和余额，不重复领取已经完成的签到；兼容主来源 account_name、expires_at 字段及显式 TRAE_JITTER_MAX，保留维护默认错峰和主来源 8 点 30 分定时配置能力；网页会话鉴权失效且已显式提供同账号桌面凭据时自动回退，不因网络错误切换账号或设备；领取接口报错后只读复查官方当日状态，确认已完成才能成功，未确认时保持失败及冷却；需更新凭据账号单独统计；逐字引用的 TRAE_ACCESS_TOKEN_2 至 _9 与实际解析一致，修正上次导入失败。
- `scripts/tsthb_checkin.py`：从官方活动列表查询当前签到活动，优先每日签到入口；校验账号并展示官方返回的非敏感身份，隐藏手机号；每日签到并展示奖励名称或积分；每行一个账号，账号独立执行与失败汇总；可配置的随机延迟及倒计时，保留每天 09:55 调度；完整断网预演、分阶段日志、任务统计及单行结构化汇总；青龙脱敏通知及全局开关，通知失败保留业务退出码；每次 HTTP 请求设置 20 秒整体等待时限，覆盖域名解析和慢速响应；签到不自动重试。
- `scripts/ty_netdisk_checkin.py`：使用官方密码登录流程和 RSA 加密建立独立账号 Cookie 会话；每日签到、区分新签到和今日已签到、显示奖励空间并严格校验业务结果；每行配套凭据、多账号独立执行、任一失败整体非零退出；保留每日16:01计划、可配置随机延迟及账号间10～30秒随机间隔；显示官方非敏感昵称或公开身份，抑制手机号、凭据、会话及原始响应；青龙任务汇总通知、时间轴日志、阶段耗时、账号统计及单行 TASK_SUMMARY 记录；完全断网预演、凭据格式检查及旧环境变量迁移提示；兼容密码页字段属性顺序、已抵达密码页的重定向和上游 callbackMsg JSONP 登录响应；脱敏诊断 HTTP 状态、短数字业务码、固定协议字段类型、HTML 或空正文；账号结果及通知保留失败阶段；每账号 HTTP 总时限覆盖域名解析和响应读取；请求开始和耗时日志；无自动重试；Python 3.9+ 标准库自实现 HTTP、Cookie 与 RSA 公钥加密，限制响应大小及官方 HTTPS 重定向；区分域名解析失败、网络连接失败、TLS 验证失败和超时；通过独立开关抽取当天签到奖励和已有相册任务奖励；沿用规范脚本及其每日16:01计划，不建立并行产品任务；奖励抽取明确校验响应字段及业务码，识别50M空间和无剩余机会；未知错误或缺少奖励字段时失败且不自动重试；奖励阶段独立处理失败并保留失败阶段；前置登录或签到未确认时跳过奖励；每账号总时限覆盖启用的奖励请求；保留密码后续分隔符和空格、原有汇总字段；预演覆盖启用的奖励阶段并从HTTP入口禁止网络；通知依次尝试可导入的notify.py、指定或标准青龙目录中的notify.py、sendNotify.js；限制通知耗时并抑制模块输出。
- `scripts/tyqhdraw.py`：登录并校验业务成功码与有效会话；查询调料包和番茄资产；打印官方返回的非秘密账号身份；显式开启后执行活动 58 集市兑换抽奖，每轮最多 10 次并检查奖品字段；使用本地透明掩膜图像匹配识别滑块并验证官方业务成功码；低置信度停止；查询实物礼品名称及非实物礼品数量；每行一个账号，账号独立失败隔离与整体非零退出；完全断网预演、青龙脱敏通知、逐阶段日志及单行任务汇总。
- `scripts/valorantstore.py`：按原每日 08:15 定时查询掌上无畏契约每日商店，不购买商品。；刷新 access_token、client ticket、web ticket 和临时票据；刷新失败仍尝试旧会话查询并以失败状态退出。；查询绑定账号并按官方返回显示昵称；无昵称时使用账号序号。；报告每日皮肤名称、品质、点券价格、点赞数及北京时间刷新时间。；使用背景与商品图片生成商品长图，可选 Telegram 图片推送；图片失败保留文字报告并记录失败。；通过青龙通知发送包含商店报告、账号总数、成功数和失败数的脱敏总结；通知不可用不改变业务退出码。；支持每行一个账号、无网络预演、阶段耗时及账号和任务统计，输出唯一单行 TASK_SUMMARY。。
- `scripts/vortexa_free_claim.js`：账号密码登录，邮箱或用户名字段自动识别与自定义登录字段；访问 Token、刷新 Cookie 登录；授权失效后按原方式重新登录一次。；检查已有免费主机，显示公开服务名称或 ID；官网返回昵称、用户名、显示名或公开 UID 时输出身份以核对账号，不输出邮箱登录凭据。；查询免费主机库存、领取资格，默认完成只读检查；已有免费主机时确认已完成。；独立产品列表模式，列出免费产品名称、slug、产品 ID、套餐 ID、名称、类型和价格。；按产品 ID、slug 或名称选择免费产品；支持指定套餐 ID，未配置时选择首个免费产品及免费套餐。；显式开启免费主机领取，提交后以官方已有主机状态核验成功；未知响应、付费套餐和选定产品缺失时失败闭合。；显式开启有限随机间隔库存轮询；保留原十分钟定时规则、间隔配置、登录重试和请求头配置。；每行一个账号，凭据隔离，逐账号执行，任意账号失败整体非零退出。；完全断网预演、完整时间轴日志、分阶段与账号统计、一条 TASK_SUMMARY JSON；青龙通知及全局开关。。
- `scripts/wangchao.py`：手机号与密码登录，展示官方返回的非敏感昵称或公开账号标识；保留上游随机客户端标识、RSA 密码加密、HMAC 登录认证、应用请求签名和 SM2 阅读参数加密；进入 App，获取每日阅读任务、识别已读文章、浏览未读文章、提交阅读记录并复查完成进度；显式开关控制同应用活动入口浏览，不伪造或重放随机阅读记录；显式开关控制每日一次抽奖，检查会话、阅读进度及官方资格，展示上游奖品名称；查询最近十条抽奖记录及时间；换行多账号、独立失败处理、完全断网预演、业务失败非零退出；限时 HTTP 请求、严格业务码与必要字段校验、禁止携带凭据重定向；时间轴阶段日志、每账号及全局统计、唯一单行 TASK_SUMMARY 汇总、青龙脱敏通知。
- `scripts/wentiweilaihui.py`：查询签到记录及今日签到状态；今日已签到时跳过重复签到，否则执行每日签到；查询并展示当前会员积分；官方响应提供昵称、用户名、显示名称或公开 UID 时展示非敏感账号身份；逐行多账号独立处理，兼容裸 JWT、完整 Wechat 登录令牌及原账号对象字段；完全断网预演和逐阶段脱敏日志、账号与子任务统计、单行结构化总结；正式执行后通过青龙通知发送脱敏总结，通知不可用不改变业务退出码。
- `scripts/workbuddy.py`：每日签到和今日状态查询；主状态接口失败时回退兼容接口，令牌失效不盲目回退。；展示每日积分、签到获得积分、连续签到天数及连签奖励标记。；识别官方确认的活动关闭或今日已签；签到失败后复查，确认已签则视为完成。；可选刷新令牌续期并重试一次，兼容企业、租户、域名及自定义浏览器请求头。；逐行 JSON 多账号和驼峰凭据字段兼容，保留每日 08:30 定时与启动错峰参数。；完全断网预演、逐阶段脱敏日志、账号与子任务统计、单行结构化汇总和青龙通知。；官方返回公开昵称、用户名、显示名称或公开 UID 时显示可核对身份；不打印凭据或原始响应。。
- `scripts/workbuddy_daily.py`：国内版每日签到及服务端签到状态回读，活动关闭正常跳过，区分签到连签与活跃连签；积分套餐总量、余额、用量、等级、能量、活跃连签及成长任务状态查询，显示官方非敏感账号身份；扫描已完成成长任务并领取奖励，回读验证领取状态；领奖保留网页请求头回退；Buddy信息、徽章查询及旅行状态驱动的出发和奖励领取；显式选择抽奖、最多五次盲盒、连签兑换、礼包补偿、昨日补签；未知资源或状态不执行消费；显式选择并允许模拟事件后执行设计/自动化/灵感、专家团、应用/教师助手、主题、资料库、五专家、五模板、GLM/五次对话、轻量云专家和夜猫子成长任务；保留上游HTTP链及服务端终态核验；小程序七环链式成长任务、锁定任务跳过、原请求头与回读目标、45秒节奏及相应回退；明文凭据本地体检、私有缓存轮换续期、--refresh、--query、--only、--gap、--mp-gap和旧过滤参数兼容；每行多账号隔离执行、断网预演、脱敏时间轴、账号及子任务统计、唯一TASK_SUMMARY记录、青龙通知；国际版--intl活动状态探测、每日奖励领取及服务端回读，活动关闭正常跳过，认证或未知错误失败闭合；国际版显式模型保活，四模型按序回退及自定义模型链，核验流式回答和完成标志；签到与保活分别统计；国际版逐行多账号、旧单账号变量、--only与--no-keepalive兼容；显式--refresh与私有缓存续期；国际版断网预演、阶段时间轴、账号统计、唯一TASK_SUMMARY及青龙通知；显式 --credit-report 独立查询国内版或国际版积分日报：聚合周期容量、累计容量、余额、用量及套餐数，结构异常或分页不完整失败闭合；不执行签到或成长任务；--credit-report --json 输出脱敏套餐数值数组，兼容上游总量、余额、用量和套餐字段；--only 按账号序号筛选；显式 --intl --trial 独立领取国际版一次性专家加油包；验证HTTP与业务码0，业务码14051识别已领取；不执行日常奖励、续期或模型保活。
- `scripts/wps_clock_in.py`：查询并显示官方返回的账号昵称，隐藏凭据和手机号。；查询打卡活动首条奖励名称，兼容sku_name与mb_name。；查询持续打卡天数，明确空奖励不能证明今日打卡成功。；保留wps_ck参数与每日09:10调度，支持换行多账号。；支持断网预演、脱敏青龙通知、阶段日志和单行结构化任务总结。。
- `scripts/yht.py`：查询官方账号昵称等非敏感身份，不输出手机号；查询种植活动标题；参与种植活动；连续施肥，保留上游默认最多一百次请求并允许调低上限；查询当前等级、下一等级和剩余施肥次数；施肥接口返回当前不存在进行中的活动时尝试领取奖励，核验奖励名称与数量；可选每日签到及奖励详情查询，默认保持未启用；可选本次配置账号之间互助及互助身份查询；每行一个账号、独立执行、任一业务失败整体失败；完全断网预演、时间轴阶段日志、账号统计及单行结构化任务汇总；通过青龙通知适配器发送脱敏总结，通知异常保留业务退出码。
- `scripts/youdao.py`：刷新登录会话，保留已有 Cookie 并接收服务端更新。；每日同步空间奖励，验证 rewardSpace 字段。；每日签到，验证 space 字段。；连续领取三次广告空间奖励，分别验证 space 字段。；显示官方返回的非敏感昵称、用户名、显示名称或公开 UID，不从 Cookie 提取身份。；多账号独立处理，统计已确认奖励、阶段耗时及账号结果，输出单行结构化任务总结。；完全断网预演及青龙脱敏通知，通知失败不改变业务退出码。。
- `scripts/yyshuijuantime.py`：每天读取阴阳师官网最新五条维护更新公告；支持原有三种正文容器，并保留嵌套正文内容；提取追忆绘卷活动名称、维护后开始日期及结束时间，支持跨年并验证日期；保留原 JSON 字段及同名同开始日期去重的活动历史；报告活动时间与已结束活动状态；通过青龙通知模块发送脱敏运行摘要，支持全局通知开关；无网络、无文件读写的内置公告预演；带时间戳的分阶段日志和单行结构化任务统计，失败非零退出。
- `scripts/zcode_cn_daily.py`：保留国内版默认任务，新增显式国际版及跨区域账号选择；两类凭据独立处理。；查询可领取套餐、权益及有效期，并按北京时间显示。；优先级最高套餐自动领取，同优先级保持上游顺序；可指定套餐。；支持每账号验证码及全局补齐参数、客户端版本和固定设备参数。；支持 --preview 只读预览、--only 账号筛选和 --no-notify 通知关闭。；支持显式激活事件补报，默认关闭。；支持每行一个账号、账号独立处理和失败非零退出。；支持完全断网预演、时间轴日志、账号统计及唯一 TASK_SUMMARY 记录。；发送青龙脱敏总结，兼容原推送通道及青龙接口，通知失败保留业务退出码。。
- `scripts/zippo.py`：积分余额查询；每日签到及奖励核验；商品分类7前两页检索；显式收藏及领取奖励，可选择取消本轮收藏；显式记录分享任务及领取奖励，不发布文本；使用指定星级和官方标签评价一个未评价商品并领取奖励，已评价时跳过提交；显式绑定指定推荐人，回显不足时失败闭合；多账号独立执行、断网预演、时间轴日志、结构化汇总及青龙通知。
- `scripts/zodgame_test.py`：每日签到及今日已签到识别；Bux 首次加入、广告观看读秒、观看完成更新与积分领取；领取结果重试一次并核验已知业务成功提示；点币余额查询；签到与广告任务选择开关；逐行多账号独立处理及失败非零退出；HTTP 超时、Cloudflare 拦截识别和脱敏诊断；断网参数与流程预演；分账号阶段日志、任务统计及单行 TASK_SUMMARY 汇总；正式运行通过青龙 notify.py 发送脱敏总结，断网预演生成通知摘要。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

### 必选参数（优先配置）

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="1"><code>scripts/139_yunduo.py</code></td><td><code>YDYP_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：手机号|Basic 授权值；也兼容省略 Basic 前缀的完整编码值或原始授权令牌。仅在第一个竖线处分割，后续凭据原样保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/2cycdx.py</code></td><td><code>cycd_cookie</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留行内分号、等号、&amp; 和 @，不用这些符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/51cto_sign.js</code></td><td><code>ICTO_BLOG_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，推荐用户名|密码；在首个竖线拆分，后续密码原样保留。兼容不含竖线的用户名@密码，在首个@拆分；邮箱用户名须使用竖线。旧版&amp;多账号配置必须迁移为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/999.py</code></td><td><code>HRT999_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行为一个完整 JSON 对象；必填 mobile（十一位中国大陆手机号）和 token（非空字符串）；可选 user_agent（无换行字符串）及 account_name（原有账号备注兼容字段，不用于业务验证）。JSON 可无歧义保留凭据中的分隔符。不要用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/acfun.py</code></td><td><code>ACFUN_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，格式为 手机号|密码；仅在第一个 | 分割，密码中的后续 | 和首尾空格原样保留。手机号两侧空格忽略；不得使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/agentrouter.py</code></td><td><code>AGENTROUTER_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 user_session 值或 JSON 对象；对象必填 github_session，可填 account_name、base_url、user_id、proxy、verify；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/airport.py</code></td><td><code>SUYING_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行：登录邮箱|密码。只按第一个 | 分割，后续密码内容保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/akile_checkin.py</code></td><td><code>AKILE_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 JWT，包含有效 exp；不加 Bearer，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/aliyundrive_checkin.js</code></td><td><code>refreshToken</code></td><td>是</td><td>格式：每个非空行填写一个账号的 refresh_token；仅按换行分隔，不支持 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_REFRESH_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的刷新令牌；不用 &amp;、@ 或其他符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/aolaxing.py</code></td><td><code>AOLAXING_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整 Cookie；不按 &amp;、@ 或分号拆分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/api_hax.py</code></td><td><code>HAX</code></td><td>否</td><td>格式：单个非敏感开关；1 启用；0、false、no、off 或空值不启用。未启用报告配置错误并非零退出。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/arknightsbanner.py</code></td><td><code>ARKNIGHTS_STATE_FILE</code></td><td>否</td><td>格式：一个本地 JSON 文件路径；首次正式运行自动创建文件和父目录，已有文件需包含数组 known_cids 与 notified_cids。断网预演不读写文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/atxyq.py</code></td><td><code>atxyqs</code></td><td>是</td><td>格式：每个非空行一个账号：Authorization#Uid；仅在第一个 # 拆分，后续文本原样保留；Uid 为数字。旧版 @ 账号分隔必须改为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/auto_buy.py</code></td><td><code>SHYP_BUY_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行 Authorization|Cookie；Cookie 可省略，仅在第一个 | 处分割；换行区分账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_SKU_ID</code></td><td>否</td><td>格式：数字字符串；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_ACTIVITY_ID</code></td><td>否</td><td>格式：数字字符串；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，必填字符串 token、device_id；可选 site_id（默认 310110）、user_agent（默认 okhttp/4.10.0）；换行区分账号，JSON 保留字段内分隔符；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/autoclaw_cn_daily.py</code></td><td><code>AUTOCLAW_CN_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号。推荐 JSON 对象，access 必填，refresh、device_id 可选。兼容 token、token|refresh_token、token|refresh_token|device_id、备注|token|refresh_token|device_id 和旧备注|JWT 格式。逐次只按首个 | 切分，最后字段保留剩余文本；可带 Bearer 前缀。禁止用 &amp;、@ 分隔账号；特殊字符或歧义格式使用 JSON。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/autosignin.js</code></td><td><code>ALIYUN_REFRESH_TOKEN</code></td><td>是</td><td>格式：每个非空行一个刷新令牌；空行忽略，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/autosignin.py</code></td><td><code>E_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；字段用分号分隔，每个字段只按第一个等号拆分，后续等号保留。不要使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baidu.py</code></td><td><code>BAIDU</code></td><td>是</td><td>格式：每个非空行是一个 JSON 对象，必填 data_url（HTTPS 文本清单地址）、submit_url（含唯一 site 和 token 的百度 HTTPS 接口地址），可选 times（1 至 100 的整数，默认 1）。不使用 &amp; 或 @ 分隔账号；接口地址内部的 &amp; 保持原样。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDU_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baiduwp.py</code></td><td><code>BAIDUWP_COOKIE</code></td><td>是</td><td>格式：每个非空行为一个账号的完整 Cookie；分号和等号保留，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bilibili.py</code></td><td><code>BILIBILI_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号完整 Cookie，字段以分号分隔；仅在第一个等号处分割键值，值内等号保留。不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bsly_draw.py</code></td><td><code>bsly</code></td><td>是</td><td>格式：每个非空行一个账号：token#User-Agent#账号备注。第一个 # 分隔 token，最后一个 # 分隔备注，中间的 # 保留在 User-Agent 中；备注不可含 #。不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bugutv.py</code></td><td><code>BUGUTV_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：用户名|密码。只在第一个竖线处分割，密码中的后续竖线和空格保留；用户名不能包含竖线，账号凭据不能包含换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/bwcj.py</code></td><td><code>bwcjCookie</code></td><td>是</td><td>格式：每个非空行一个 Token，或 Token|customerId；仅在首个 | 分割。同账号配套字段，账号仅用换行分隔，不支持原 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/caigamer.js</code></td><td><code>CAIGAMER_COOKIE_LIST</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie，包含非空 bbs_sid 和 bbs_token。同一账号字段用分号分隔，只在第一个等号处拆分，保留值中的后续等号。不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cdrail.py</code></td><td><code>CDRAIL_DATA</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象或 URL 编码查询字符串；必填 token、app-token，Cookie 和设备请求头按本人抓包提供。支持 appToken/app_token 及 device-id/device_id 别名和其他自定义请求头；传输控制头忽略。查询字符串用 &amp; 分字段，各字段仅在第一个 = 处分割，值中的 &amp; 编码为 %26；推荐 JSON 保留复杂凭据。不得以 @ 或 &amp; 分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_COOKIE</code></td><td>是</td><td>格式：ticket=&lt;value&gt; 或裸 ticket；多账号每行一个；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/chevrolet.js</code></td><td><code>CHEVROLET_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行填写一个账号的 cpctoken 原始值，不含请求头名称；不使用 &amp;、@ 或其他字符分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ck_2nzz.py</code></td><td><code>NZZ_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；只填写 Cookie 值，不包含 Cookie: 前缀。Cookie 字段使用分号分隔，字段仅按首个等号拆分，后续等号保留；禁止使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ck_acfun.py</code></td><td><code>ACFUN_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：手机号|密码。只按第一个 | 分割，密码中的后续 |、&amp;、@ 和空格完整保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/codearts_daily.py</code></td><td><code>CODEARTS_CREDENTIALS</code></td><td>是</td><td>格式：每个非空行一个账号：单行 JSON（上述字段，可含 expiration、domain_id、user_name、oauth_context.pkce_pair.code_verifier、oauth_context.dpop_key_pair.private_key_jwk），或 AK|SK|STS；仅前两个 | 分隔字段，后续文本保留。兼容 accessKeyId/secretAccessKey/securityToken 和 ak/sk/sts 别名。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/comicai_ai_cookie.py</code></td><td><code>COMICAI_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，token 为必填非空字符串，cookie 为可选字符串；JSON 转义可保留凭据中的分隔符。设置规范变量后不读取旧变量。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/crealitycloud_checkin.py</code></td><td><code>CREALITY_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，格式为「手机号或邮箱 空格 密码」；只按第一个空白字段分隔，后续密码文本保留。手机号支持 11 位、86 加 11 位或 +86 加 11 位；邮箱直接填写；以 # 开头的行忽略。兼容脚本内 CONFIG_ACCOUNTS，推荐环境变量。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/dachao.py</code></td><td><code>DACHAO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行是一个完整 JSON 对象，不用 &amp; 或 @ 分隔账号。必填字段 phone_number、password_encrypted、user_agent；兼容 password、user_agent_vapp、user_agent_aihoge。可选字段 account_name、tenant_id、client_id、session_id、passport_cookies、vapp_cookies、aihoge_cookies（兼容 cookies）、passport_signature_salt、aihoge_signature_salt、sign_lottery_id、redeem_member（兼容 withdraw_member）、redeem_cookies、redeem_user_agent。Cookie 和 member 保留原字符串（JSON 内引号须转义）。forum_session_id、forum_cookies、forum_tenant_id 兼容读取但原主任务没有论坛动作。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/daily_benefits.py</code></td><td><code>WPS_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号；仅福利任务使用完整 Cookie；任务中心使用 user_id|完整 Cookie，仅按第一个 | 分割，保留后续 Cookie 内容。也可每行一个 JSON 对象，包含 cookies 及可选 user_id、user_agent、account_name、max_lottery_limit，兼容原账号字段；不读取私有配置文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/dailynewscn.js</code></td><td><code>DAILYNEWSCN_LIST</code></td><td>否</td><td>格式：仅 dailynewscn 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OILPRICE_LIST</code></td><td>否</td><td>格式：仅油价模式必填；每个非空行一个中文地区，或一个含 area 字符串的 JSON 对象；旧标记 1 可配合 OILPRICE_AREA；不使用 &amp; 或 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ddnsto.py</code></td><td><code>DDNSTO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行填写 路由器ID|完整Cookie；仅在首个 | 分隔，同一行内 Cookie 原样保留，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/deepflood_checkin.py</code></td><td><code>DEEPFLOOD_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号完整 Cookie；不按 &amp;、@ 或分号拆分账号，Cookie 中的这些字符原样保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/durex.py</code></td><td><code>dlshyzx</code></td><td>是</td><td>格式：每个非空行一个完整令牌；保留变量名；不再使用上游的 # 或其他符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/enshan_checkin.py</code></td><td><code>ENSHAN_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；同一账号各字段用分号分隔，字段值内的等号保留；不得用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/epicfreegames.py</code></td><td><code>EPIC_TG_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个机器人令牌|会话编号；只按首个 | 分割，支持数字会话编号或公开频道用户名。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/erke.py</code></td><td><code>ERKE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行为一个 JSON 对象，五项字段均为非空字符串；可选 account_name 和 user_agent，兼容上游字段。account_name 保留输入兼容，日志优先使用官方身份，没有官方身份时用账号序号。JSON 内部文本与标点保留，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/f1owkang_qingskyland_skyland.py</code></td><td><code>SKYLAND_TOKENS</code></td><td>是</td><td>格式：每个非空行一个完整鹰角登录 token；也接受每行一个包含 data.content 的官方 JSON。禁止使用逗号、&amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/fnnasclub.py</code></td><td><code>FNNASCLUB_COOKIE</code></td><td>是</td><td>格式：每个非空行为一个账号的完整 Cookie 值，保留分号及等号，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/forum_download.py</code></td><td><code>FORUM_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，必填 url、cookie，可选 name、fid；不按分号、&amp; 或 @ 拆分 Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/fwxs_checkin.js</code></td><td><code>fwxs</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；兼容 Cookie#昵称备注，仅按首个 # 分割，后续备注完整保留但为防泄漏不输出。禁止用 @ 或 &amp; 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/fxh.js</code></td><td><code>fxhOpenId</code></td><td>是</td><td>格式：每个非空行一个 OpenId，允许字母、数字、下划线和短横线；保留上游变量名，不再支持 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/get_yys_cgvideo.py</code></td><td><code>YYS_OUTPUT_DIR</code></td><td>否</td><td>格式：一个本地目录路径；预演也必须提供占位目录；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/hellogithub.py</code></td><td><code>HELLOGITHUB_STATE_FILE</code></td><td>否</td><td>格式：单个绝对文件路径；文件不存在时从未发送开始，文件损坏时停止。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/hifiti_checkin.py</code></td><td><code>HiFiTi_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；填写完整 Cookie（字段之间使用分号），兼容旧版仅填写 cloudmusic.net 的值；字段值中的等号完整保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/hlyl.py</code></td><td><code>hlylck</code></td><td>是</td><td>格式：每个非空行一个账号：access-token 或 access-token#备注；仅按首个 # 分隔，后续备注内容保留。不使用 &amp;、@ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/hsay.py</code></td><td><code>hsayCookie</code></td><td>是</td><td>格式：每个非空行填写一个完整 Token；账号之间只使用换行，不使用 @ 或 &amp; 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/huaruntong_wx.py</code></td><td><code>HRT_WX_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：可直接填写完整 token，也可填写含 token 字段的单行 JSON 对象。JSON 兼容 answerResult（整数，默认 1）、channelId（默认 APP）、merchantCode（默认 1641000001532）、storeCode（默认 qiandaosonjifen）、sysId（默认 T0000001）、transactionUuid 和 inviteCode（默认空字符串）、user_agent（默认原 iPhone 浏览器标识）、account_name。字符串字段使用 JSON 转义；不使用 &amp;、@ 分隔账号，token 内这些字符保留。account_name 兼容输入但日志使用账号序号和官方公开身份。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/hykb_gamesign.js</code></td><td><code>HYKB_SCOOKIE</code></td><td>是</td><td>格式：每个非空行一个账号，只填写 scookie 值，不添加 scookie= 或 Cookie 请求头。支持原始值及已百分号编码的值；内部 |、&amp;、@ 等字符保留，不作为账号分隔符。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ikuuu_checkin.py</code></td><td><code>IKUUU_ACCOUNT</code></td><td>是</td><td>格式：每行一个账号：邮箱|密码，或 cookie:完整 Cookie；仅在第一个 | 处分割邮箱密码，密码中的后续 | 保留。Cookie 使用分号分隔名称=值，值中的后续 = 保留；禁止用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/imaotai.py</code></td><td><code>IMAOTAI_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行是一个 JSON 对象；必填 token、userid、device_id，userid 支持字符串或整数。申购另需 province、city、lat、lng。item_codes 是数字字符串数组，默认 [&quot;11318&quot;,&quot;11319&quot;]；reserve_rule 为 0（最近门店）或 1（所在城市库存最多）。mobile 兼容但不使用和输出。禁止用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/index.js</code></td><td><code>PIXIV_ACCOUNTS</code></td><td>是</td><td>格式：每行一个账号：公开UID|完整Cookie；只按第一个 | 拆分，后续 Cookie 内容保留；UID 留空时使用 |完整Cookie。禁止用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/iqiyi_checkin.py</code></td><td><code>IQIYI_COOKIES</code></td><td>是</td><td>格式：每个非空行一个账号，形如 P00001=&lt;登录凭据&gt;; P00003=&lt;用户编号&gt;; __dfp=&lt;设备字段&gt;。分号分隔同账号字段，每个字段仅按第一个等号拆分；保留值中其余等号。设备字段仅使用 @ 前段，@ 不分隔账号。优先使用 __dfp；P00002、QC005 等额外 Cookie 字段允许保留，不单独要求。# 开头的行作为注释。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/jc_checkin.py</code></td><td><code>JC_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个邮箱|密码；仅按首个 | 分割，后续 | 和密码空格保留；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BASE_URL</code></td><td>否</td><td>格式：所有账号共用的 HTTPS 面板根地址，可包含部署子路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/jcqd.py</code></td><td><code>JCQD_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：登录邮箱|密码；只在第一个 | 分割，密码后续字符保持原样；不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/jingyiluntan_sign.py</code></td><td><code>JYLT_Cookie</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留分号及其中的等号，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/jissbon.py</code></td><td><code>jsbaxfls</code></td><td>是</td><td>格式：每个非空行填写一个完整Access-Token；保留原变量名，旧#分隔须改为换行；不使用&amp;或@分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/jyj.py</code></td><td><code>jyjck</code></td><td>是</td><td>格式：每个非空行一个账号：authorization#userid；只按第一个#分割，后续字段原样保留，不支持@@、&amp;或@分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kgqq.py</code></td><td><code>KGQQ_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号。默认填写完整 Cookie（必须含数字 uid）；音乐奖励开启时填写 完整Cookie|g_tk_openkey，只在第一个竖线处分割，Cookie 内等号及分号原样保留，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kjwj.py</code></td><td><code>kjwj_info</code></td><td>是</td><td>格式：邮箱#密码，每行一个账号，仅首个 # 为分隔符，密码中后续字符原样保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_COOKIE</code></td><td>是</td><td>格式：每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 &amp; 或 @ 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kuku_daily.py</code></td><td><code>KUKU_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：产品作用域STOKEN|完整Cookie；仅在第一个竖线处分割。Cookie 支持请求头、单行编辑器 JSON 或键值对象，必须包含 BDUSS。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kurobbs_sign.py</code></td><td><code>KUROBBS_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：社区UID|Token，仅在第一个 | 分隔，保留 Token 后续内容。社区 UID 为数字。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/l.py</code></td><td><code>LINUXDO_COOKIES</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie，字段以分号分隔，每个字段仅在第一个等号处分割；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/leaflow_checkin_pyleaflow_checkin.py</code></td><td><code>LEAFLOW_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号，完整名称=值请求头，多项 Cookie 用分号分隔；值中的等号、&amp; 和 @ 原样保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/littlewuh_qinglongbox_dailycheckin_scripts.py</code></td><td><code>NZZ_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；完整 Cookie 的字段用分号分隔，键和值仅在第一个等号处分割，保留值中的后续等号；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/lizhixu_ql_script_hub_nodeseek.py</code></td><td><code>NODESEEK_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Cookie；行内分号、等号及 &amp; 原样保留，不使用分隔符拆分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/lizhixu_ql_script_hub_youdao.py</code></td><td><code>YOUDAO_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie，字段按分号分隔，每个字段仅在第一个等号处分开，后续等号和 &amp; 保留为凭据内容；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/lobsterai_checkin.py</code></td><td><code>LOBSTERAI_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号：uid:AT:RT、uid:AT 或纯 AT。RT 可为空；同一账号字段使用英文冒号，逐个仅按首个冒号拆分并保留后续 RT 文本。不使用 @ 或 &amp; 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/loomy_daily.py</code></td><td><code>LOOMY_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号，填写 session 或 备注|session；仅在第一个 | 处分割，后续凭据文本完整保留。不得使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/lynkco_qinglong_single.py</code></td><td><code>LYNKCO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个JSON对象；token可单独使用，refreshToken必须配套deviceId，可同时配置token作续期失败回退；不以&amp;、@分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_APP_SECRETS</code></td><td>是</td><td>格式：JSON对象：nativeAppKey、nativeAppSecret必需；分享或续期需glDevId；nativeAppCode用于优先AppCode续期，缺失时回退HMAC；loginAppCode仅兼容保存。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/main.py</code></td><td><code>WALLHAVEN_SAVE_DIR</code></td><td>否</td><td>格式：绝对目录路径；自动追加当天日期子目录。预演可使用 /tmp/wallhaven-dry-run-placeholder。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/mifan_optimized.py</code></td><td><code>MIFAN_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，用户名|密码；只在第一个竖线分割，密码后续竖线保留；用户名不能含竖线。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/mimotion.py</code></td><td><code>MIMOTION_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 手机号或邮箱|密码，仅在第一个 | 分割；也支持每行一个 JSON 对象，字段 phone、password，上传时另需 data_json、last_deviceid，可选 min_step、max_step。data_json 是仅含当天一条记录的数组或 JSON 字符串，必须有非空 data 数组和 summary.stp.ttl；summary 可为对象或 JSON 字符串。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/netease_task.py</code></td><td><code>NETEASE_COOKIE</code></td><td>是</td><td>格式：每个非空行一条完整 Cookie，必须包含非空 MUSIC_U 和 __csrf；字段用分号分隔，值中的 =、&amp;、@ 原样保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NETEASE_API_BASE</code></td><td>否</td><td>格式：正式执行必填，断网预演可省略；HTTPS 地址，不含认证信息、查询参数或片段，该服务会接收账号 Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nga_checkin.py</code></td><td><code>NGA_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个账号；兼容 access_uid|access_token，仅按首个竖线分割；iOS 使用单行 JSON 对象，字段为 access_uid、access_token、client_checksum，全部为字符串。JSON 也适用于 Token 含竖线的账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nodeseek.py</code></td><td><code>NS_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号，保留完整 Cookie 中的分号、等号与其他字符；不以 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nodeseek_checkin.py</code></td><td><code>NODESEEK_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行，每行为完整 Cookie 请求头值；Cookie 内的 &amp; 和 @ 保持原样；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/nte.py</code></td><td><code>NTE_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号：纯 refreshToken 或单行 JSON 对象。对象支持 refreshToken（兼容 token）、uid、deviceId、gameId、roleIds；可添加 cloudToken、cloudUserId、cloudDeviceId；云凭据必须成对提供，也可仅提供云账号。兼容 cloud_token、cloud_user_id、cloudUid、cloud 对象的 token/userId/uid/deviceId，以及 deviceid、cloud_device_id、game_id、role_ids、roleId。roleIds 为数组或逗号分隔角色列表；账号之间只用换行，不使用逗号、&amp; 或 @。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/officeace_daily.py</code></td><td><code>OFFICEACE_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号：AK|SK|security_token|project_id|base_url，兼容前置备注。全部配套字段非空，地址为 HTTPS 根地址或 /v2；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ole.py</code></td><td><code>OLE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象；四个必填字段均为非空字符串。可选 shop_code 默认 205368，city_id 默认 c_region_11122，user_agent 默认保留上游值。兼容 account_name 字段但不输出用户填写的标签，避免泄漏手机号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/passnat_checkin.py</code></td><td><code>PASSNAT_SK</code></td><td>是</td><td>格式：每个非空行是一个账号的完整 Authorization 值；仅以换行分隔账号，不使用其他分隔符。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/psnine.py</code></td><td><code>PSNINE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行填写 psnid|shell，只按首个 | 分割；字段不能含分号、换行或非 ASCII 字符。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/pt_sign_v5.js</code></td><td><code>PT_SITE_HDKYL_CK</code></td><td>是</td><td>格式：每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SITE_CARPT_CK</code></td><td>是</td><td>格式：每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SITE_AFUN_CK</code></td><td>是</td><td>格式：每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/qoder_airscript.js</code></td><td><code>QODER_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象；accessToken 或 access_token、refreshToken 或 refresh_token 至少一项有效。device 内 clientType、machineOS、machineHostname、machineId、machineToken、machineCode、machineType、version 八项均为必填单行字符串。enabled=true 或 qiandao=&quot;是&quot; 才执行，默认跳过。region 可选 cn/global。可保留 name、uid；serverchan、pushplus、qywx 为可选逐账号通知凭据。仅刷新模式必须有刷新令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/quark_signin.py</code></td><td><code>QUARK_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；保留分号及等号，不使用 &amp;、&amp;&amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/raccoon_daily.py</code></td><td><code>RACCOON_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号：令牌或备注|令牌，只在第一个 | 拆分，支持 Bearer 前缀，不支持 &amp; 或 @ 分隔账号。备注不输出。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/rainyun.py</code></td><td><code>rainyun_ck</code></td><td>是</td><td>格式：每个非空行一个账号：用户名#密码。仅在第一个 # 处分隔，密码后续的 # 和空格完整保留；用户名按上游规则转换为小写。不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/rousi_checkin.js</code></td><td><code>ROUSI_TOKEN</code></td><td>是</td><td>格式：规范凭据变量，每个非空行一个账号 Token，可带 Bearer 前缀；禁止用 &amp; 或 @ 分隔账号。已有兼容变量也能独立提供凭据，无需同时配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sf.py</code></td><td><code>SF_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，必填字符串字段 sign、channel、device_id；可选字符串字段 user_agent、account_name。账号只按换行分隔，字段内容完整保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sfsu_checkin.py</code></td><td><code>sfsyUrl</code></td><td>是</td><td>格式：每个非空行一个完整的 URL 编码登录/分享 URL；整行作为同一账号凭据，不使用 &amp;、@ 等字符分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sgs.py</code></td><td><code>sgs</code></td><td>是</td><td>格式：每个非空行一个完整 Token；保留小写变量名 sgs，原版 # 多账号分隔改为换行，单账号参数兼容。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/shuyi.py</code></td><td><code>sysxc_auth</code></td><td>是</td><td>格式：每个非空行一个账号的 auth 原值；保留变量名，不再以 # 分隔账号，凭据内部的 # 原样保留。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sign_in.py</code></td><td><code>KANXUE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，必填 cookie、csrf_token 字符串，可选 user_agent、account_name；JSON 内保留完整凭据，不用任何分隔符拆分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/skland_daily.py</code></td><td><code>SKLAND_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号：通行证 Token、cred:token、含 cred/token 的单行 JSON、含 data.content 的官方响应 JSON，或含 phone/password 的单行 JSON；冒号仅在第一处分割，不使用 &amp;、@、分号或逗号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/skland_demo.py</code></td><td><code>SKLAND_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：通行证原文、含 data.content 的单行 JSON，或单行 JSON 对象，字段 token；也可字段 phone 与 password，或 phone 与 code；可在同一 JSON 添加 did（由本人官方登录请求的 dId 头获取）。send-code 动作仅需 phone。账号不能使用逗号、&amp; 或 @ 分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/skyland.py</code></td><td><code>SKYLAND_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整账号 Token；禁止用逗号、&amp; 或 @ 分隔多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个账号，格式 sk|完整 Cookie；仅在第一个 | 分割。网页或仅抽奖模式使用 |完整 Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ssl.py</code></td><td><code>SSL_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象；token 或 email/key 配套认证；zone_ids 和 domains 为一一对应的非空数组，区域标识为32位十六进制；例如字段结构 {&quot;token&quot;:&quot;占位凭据&quot;,&quot;zone_ids&quot;:[&quot;区域标识&quot;],&quot;domains&quot;:[&quot;主域名&quot;]}。凭据文本由 JSON 解析完整保留，不使用符号分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_33agilestudio.js</code></td><td><code>AGILE_STUDIO_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个邮箱#密码，只按第一个 # 分隔，密码中的后续 #、&amp; 和 @ 均保留；禁止使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_allgirls.js</code></td><td><code>ALL_GIRLS_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的 AccessToken；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_amx.js</code></td><td><code>AMX_TOKEN</code></td><td>是</td><td>格式：每个非空行一个完整 Token；不使用 &amp; 或 @ 分隔账号，行内字符保持不变，首尾空白忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_authcheck.js</code></td><td><code>AUTH_CHECK_ACCOUNTS</code></td><td>是</td><td>格式：每行一个 JSON 对象，service 为下列兼容变量名，credential 为该账号完整凭据；同一账号配套字段保存在同一个 credential 中。设置本变量时优先使用它，不再读取兼容账号变量。；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="1"><code>scripts/sudojia_jlc_yj.js</code></td><td><code>JLC_COOKIE</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie；兼容 OSHW_COOKIE，二者同时设置时优先使用 JLC_COOKIE；不以 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="1"><code>scripts/sudojia_v2ex.js</code></td><td><code>V2EX_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号。兼容完整 Cookie 字符串，也可使用 JSON 对象，cookie 字段为完整 Cookie，proxy 字段为该账号可选代理 URL。Cookie 内等号和分号原样保留，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_wnna.js</code></td><td><code>WNNA_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的原始令牌，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xhn.js</code></td><td><code>XHN_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号的 URL 编码表单，包含 password、logintype、RegistrationID、appid、type、username；保留全部原始字段与编码，&amp; 仅分隔表单字段，不分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xiangwan.js</code></td><td><code>XWGAME_ACCOUNTS</code></td><td>是</td><td>格式：手机号#密码，每个非空行一个账号；仅在第一个 # 处分割，后续密码字符完整保留。不再使用 &amp; 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xiaomi_community.js</code></td><td><code>XIAOMI_COMM_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号的完整 Cookie；字段以分号分隔，字段值按第一个等号之后的全部内容保留；不按 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xinxi.js</code></td><td><code>XINXI_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个完整 sso，不使用 #、&amp; 或 @ 分隔账号；值不可含空白或控制字符。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_xpfarm.js</code></td><td><code>XPFARM_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号的完整 authorization 值；仅按换行分隔，不使用 &amp; 或 @ 分隔账号，不添加变量赋值语句。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_znds.js</code></td><td><code>ZNDS_COOKIE</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 Cookie，保留分号、等号与 &amp;；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/sudojia_zxice.js</code></td><td><code>ZX_ICE_TOKEN</code></td><td>是</td><td>格式：每个非空行填写一个账号的 access-token 原值；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/supertopicsign.py</code></td><td><code>WEIBO_SUPERTOPIC_ACCOUNTS</code></td><td>是</td><td>格式：每行一个账号；完整 HTTPS URL 或 URL 编码查询字符串；按第一个等号解析字段并保留后续内容；&amp; 仅分隔同一账号的查询字段，不分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/synspoint.py</code></td><td><code>synshd</code></td><td>是</td><td>格式：每个非空行一个账号凭据，可带 Bearer 前缀；不使用 #、&amp;、@ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tencent_video_checkin.py</code></td><td><code>TENCENT_VIDEO_COOKIES</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie，字段以分号分隔，仅按第一个等号拆分字段值。必需非空字段 vqq_openid、vqq_access_token、main_login；建议保留 vqq_vuserid、vqq_appid、vdevice_qimei36 和 ip。支持空行及 # 开头注释，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tieba_checkin.py</code></td><td><code>TIEBA_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；支持 BDUSS 单值或完整 Cookie。成长任务要求同一行含 BDUSS=值; CUID=值，字段值按首个等号分割，后续等号保留；不能按 &amp; 或 @ 分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tjd_daily.py</code></td><td><code>TJD_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，必含 token、deviceid 字符串；可选 uid（默认 0）、name、phone、password、openudid、vendorid、account_uid。兼容旧 JSON 对象或数组，不以 &amp; 或 @ 分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/trae_checkin.py</code></td><td><code>TRAE_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象；accessToken 或 refreshToken 或 session/sessionid 至少一种，配套 deviceId 为同账号真实 12 至 20 位数字。可选 deviceKeyPem、devicePubPem、machineId、uid、name、expiresAt、fingerprint；兼容 access_token、refresh_token、device_id、account_name、expires_at。显式 icubeAuth、storagePath 或 authPath 可替代明文凭据；旧 JSON 数组仅作兼容。预演只用占位明文，不读凭据文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tsthb_checkin.py</code></td><td><code>tsthbck</code></td><td>是</td><td>格式：每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 &amp; 或 @ 分隔账号，字段内部字符保持原样。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/ty_netdisk_checkin.py</code></td><td><code>TY_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号：用户名|密码；仅切分第一个竖线，密码内的竖线、&amp;、@和空格原样保留；账号之间只能换行；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tyqhdraw.py</code></td><td><code>tyqhCookie</code></td><td>是</td><td>格式：每个非空行 thirdId#wid#备注；备注可省略。先在首个 # 拆分 thirdId，再在剩余内容首个 # 拆分 wid 与备注，保留备注后续文本。不再使用 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/valorantstore.py</code></td><td><code>VALORANT_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；字段以分号分隔、名称与值以第一个等号分隔，后续等号原样保留。至少包含 userId、openid、access_token、ct，保留 tid、acctype 等其他原始 Cookie 字段。不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/vortexa_free_claim.js</code></td><td><code>VORTEXA_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象，不使用任何符号分隔账号。支持 account/password、token、cookie、refresh；至少提供一组可用凭据。可选 fingerprint/userAgent 绑定同一账号；JSON 字符串保留密码中的分隔符。Cookie 仅填写请求头值，不包含 Cookie: 前缀；token 不含 Bearer 前缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/wangchao.py</code></td><td><code>WangChao</code></td><td>是</td><td>格式：每个非空行一个“登录手机号#密码”。仅按第一个 # 切分，密码中的后续 #、&amp;、@ 等字符完整保留。密码 UTF-8 长度不超过 117 字节。旧版 &amp;&amp; 多账号分隔须手动迁移为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/wentiweilaihui.py</code></td><td><code>WENTIWEILAIHUI_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个账号，可填裸 JWT 或完整 Wechat JWT；也可每行一个 JSON 对象，字段 token 必填，account_name、mobile、user_agent 可选，沿用上游字段名。JSON 不跨行；手机号兼容输入不发送不输出，账号名称不作为官方身份。不得用 &amp;、@ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/workbuddy.py</code></td><td><code>WORKBUDDY_ACCOUNTS</code></td><td>是</td><td>格式：每个非空行一个 JSON 对象；access_token 为必填字符串，refresh_token、uid、enterprise_id、domain、user_agent 为同账号的可选字符串。兼容 accessToken、refreshToken、enterpriseId、userAgent。JSON 保留完整字段内容，不按 &amp;、@ 或其他字符分割账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="2"><code>scripts/workbuddy_daily.py</code></td><td><code>WORKBUDDY_REFRESH_TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号：手机号:AT:RT、AT:RT、手机号:RT 或单个明文 JWT；手机号只作为兼容备注，不输出；字段仅逐次切分首个冒号，保留末尾 RT 完整内容。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_INTL_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号：AT、备注|AT、备注|AT|uid 或 备注|AT|uid|RT；逐次切分首个竖线，保留末尾 RT 完整内容。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/wps_clock_in.py</code></td><td><code>wps_ck</code></td><td>是</td><td>格式：每个非空行一个wps_sid值；只按换行分隔账号，不使用&amp;或@分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/yht.py</code></td><td><code>Yht_token</code></td><td>是</td><td>格式：每个非空行一个完整令牌；保留大小写；不使用 #、&amp;、@ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/youdao.py</code></td><td><code>YOUDAO_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；Cookie 字段用分号分隔，字段仅按第一个等号拆分，保留值中的后续等号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/yyshuijuantime.py</code></td><td><code>YYS_HUIJUAN_OUTPUT</code></td><td>否</td><td>格式：以 .json 结尾的绝对文件路径；每次运行使用一个路径，不按账号拆分；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/zcode_cn_daily.py</code></td><td><code>ZCODE_CN_TOKENS</code></td><td>是</td><td>格式：每行一个账号：jwt、jwt|device_mid、jwt|device_mid|captcha_param 或 备注|jwt|device_mid|captcha_param。验证码保留后续竖线，不用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/zippo.py</code></td><td><code>zippoCookie</code></td><td>是</td><td>格式：每个非空行一个账号；不使用 #、&amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/zodgame_test.py</code></td><td><code>ZODGAME_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号，行内为完整 Cookie 请求头值，字段用分号分隔，字段仅在第一个等号处分割，保留值中后续等号。账号间只用换行。；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

### 可选参数

不需要自定义行为时可以不配置；有默认值的参数会自动使用默认值。

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="11"><code>scripts/139_yunduo.py</code></td><td><code>YDYP_PHONE</code></td><td>是</td><td>格式：中国大陆11位手机号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_AUTH</code></td><td>是</td><td>格式：Authorization 请求头值，可省略 Basic 前缀；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_TRY_ALL</code></td><td>否</td><td>格式：布尔值，默认0；1、true、yes、on开启；0、false、no、off关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_INTERACT_LIMIT</code></td><td>否</td><td>格式：1至100的整数，默认30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_UPLOAD</code></td><td>否</td><td>格式：布尔值，默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_DELETE_AFTER</code></td><td>否</td><td>格式：布尔值，默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YDYP_DRY_RUN</code></td><td>否</td><td>格式：布尔值，默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：已有通知模块所在目录，不需要其他仓库；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：本人推送令牌；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SENDKEY</code></td><td>是</td><td>格式：本人 SendKey；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/2cycdx.py</code></td><td><code>CYCD_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示开启；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CYCD_LOCAL_TEXT</code></td><td>否</td><td>格式：可选纯文本，合并空白后最多 280 字；空值使用内置文案。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。断网预演只模拟通知，不调用通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，仅用于可选通知，不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/51cto_sign.js</code></td><td><code>ICTO_BLOG_DRY_RUN</code></td><td>否</td><td>格式：1开启完全断网预演；其他值为真实运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off关闭通知，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录；同时自动查找青龙标准脚本目录和当前目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/999.py</code></td><td><code>HRT999_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演，其余值正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启；断网预演仅在日志输出通知摘要，不外发。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；缺失或发送失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/acfun.py</code></td><td><code>ACFUN_TASKS</code></td><td>否</td><td>格式：逗号分隔 sign（签到）、info（等级和香蕉余额查询）、like（点赞）、like-cycle（点赞后取消）、danmu（公开弹幕）、banana（投一根香蕉）、share（分享任务上报）；不得重复，like 与 like-cycle 不可同时选择。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ACFUN_LOCAL_TEXT</code></td><td>否</td><td>格式：空白合并后须为 1 至 280 字符，仅 danmu 使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ACFUN_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全断网预演；0、false、no、off 或空值关闭。预演不验证真实业务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启，默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；依次尝试导入 notify.send、此目录的 notify.py、/ql/data/scripts/notify.py、/ql/scripts/notify.py。通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="11"><code>scripts/agentrouter.py</code></td><td><code>AGENTROUTER_CONFIG</code></td><td>是</td><td>格式：本地 JSON 文件路径，结构为 agentrouter.accounts 数组；账号字段与账号变量的 JSON 对象相同。user_id 可从站点用户信息取得，正常登录自动获取；verify 只允许 true 或可信 CA 文件路径，不接受 false。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AGENTROUTER_BASE_URL</code></td><td>否</td><td>格式：HTTPS 根地址，默认 https://ps.air-outer.com；账号 base_url 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AGENTROUTER_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址，可含代理认证；仅用于请求，不输出。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HTTPS_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址；支持标准小写变量及 NO_PROXY。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HTTP_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NO_PROXY</code></td><td>否</td><td>格式：逗号分隔的主机名或域名规则。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AGENTROUTER_CA_BUNDLE</code></td><td>否</td><td>格式：本地 CA 文件路径；账号 verify 路径优先，始终开启 TLS 校验。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AGENTROUTER_ALLOW_AUTHORIZE</code></td><td>否</td><td>格式：默认 0；设为 1 允许首次授权表单提交，会授予应用权限。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AGENTROUTER_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，不登录、不查询、不发送通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；预演只展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，通知失败或不可用不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/airport.py</code></td><td><code>SUYING_USERNAME</code></td><td>是</td><td>格式：一个账号的登录邮箱，须配套 SUYING_PASSWORD。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SUYING_PASSWORD</code></td><td>是</td><td>格式：一个账号的完整密码，须配套 SUYING_USERNAME。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SUYING_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机青龙通知模块所在目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/akile_checkin.py</code></td><td><code>AKILE_DRY_RUN</code></td><td>否</td><td>格式：1 开启断网预演，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AKILE_REFRESH_TOKEN</code></td><td>否</td><td>格式：1 开启刷新及回写，默认 0；仅查询模式不刷新。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CLIENT_ID</code></td><td>是</td><td>格式：青龙应用标识。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CLIENT_SECRET</code></td><td>是</td><td>格式：青龙应用密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AKILE_STATE_FILE</code></td><td>否</td><td>格式：默认同目录 state.json；保存时保留其他分区，禁止符号链接。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DAILY_ALL_CHILD</code></td><td>否</td><td>格式：1 输出兼容的 __DAILY_ALL_RESULT__ JSON。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DAILY_ALL_DISABLED</code></td><td>否</td><td>格式：包含 akile、akile_checkin 或 akilecloud 时跳过；用逗号、分号、竖线或换行列出服务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；预演只模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 或 sendNotify.js 的目录；通知不可用不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/aliyundrive_checkin.js</code></td><td><code>ALIYUNDRIVE_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网预演，其他值或未设置表示正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_PUSH_PLUS</code></td><td>是</td><td>格式：单个 PushPlus 推送令牌；未设置时只使用青龙通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭全部通知，大小写不敏感。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选通知模块目录；默认依次查找 /ql/data/scripts、/ql/scripts 和候选脚本所在目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="15"><code>scripts/aliyunpan_checkin.py</code></td><td><code>refreshToken</code></td><td>是</td><td>格式：每个非空行一个刷新令牌；旧的 &amp; 分隔格式须改为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_CLAIM_REWARD</code></td><td>否</td><td>格式：1 领取奖励；0 只签到，不领取任何奖励。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_CLAIM_ALL_REWARDS</code></td><td>否</td><td>格式：0 保留当日领奖；1 领取 status 为 normal 且 isReward 为 false 的全部签到奖励；ALIYUN_CLAIM_REWARD=0 优先关闭领奖。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_DRIVE_DRY_RUN</code></td><td>否</td><td>格式：1 启用完全断网预演、模拟通知，不等待、不写凭据文件、不注册设备。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_MAX_DELAY_SECONDS</code></td><td>否</td><td>格式：非负整数秒。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数秒。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：1 启用配置的延迟；0 关闭；未设置时不覆盖延迟配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENABLE_DEVICE_SESSION</code></td><td>否</td><td>格式：1 注册设备会话并签名领奖；0 不注册。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_PERSIST_ROTATED_TOKENS</code></td><td>否</td><td>格式：1 开启安全文件持久化；0 关闭；预演始终不写文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_TOKEN_OUTPUT_FILE</code></td><td>否</td><td>格式：绝对文件路径，原子写入权限 0600，每行对应原账号顺序的最新刷新令牌，请安全更新青龙凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；通知缺失或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径，仅用于可选通知组件，核心账号任务不依赖私有仓库。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTO_UPDATE_TOKEN</code></td><td>否</td><td>格式：不改变运行行为。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PRIVACY_MODE</code></td><td>否</td><td>格式：不改变运行行为，凭据始终隐藏。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHOW_TOKEN_IN_NOTIFICATION</code></td><td>否</td><td>格式：不改变运行行为，凭据始终隐藏。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/aolaxing.py</code></td><td><code>AOLAXING</code></td><td>是</td><td>格式：JSON 数组，每项为包含 cookie 字段的对象。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AOLAXING_TASK_IDS</code></td><td>否</td><td>格式：逗号分隔的不重复数字任务 ID。仅执行列表中未完成的指定任务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AOLAXING_DRY_RUN</code></td><td>否</td><td>格式：1 开启；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/api_hax.py</code></td><td><code>HAX_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1 使用内置样本且不加载通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知，不是业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/arknightsbanner.py</code></td><td><code>ARKNIGHTS_DRY_RUN</code></td><td>否</td><td>格式：1 表示断网预演；0、false、no、off 表示正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ARKNIGHTS_TELEGRAM</code></td><td>是</td><td>格式：每个非空行一个机器人 Token|聊天 ID，只在第一个 | 拆分字段；多个接收目标用换行分隔，支持负数群组 ID。图片失败独立记录，任一目标失败则本次非零退出并保留公告重试。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。断网预演仅模拟通知，不加载通知代码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：一个本地目录路径；不需要其他仓库、程序或安装引导。通知模块缺失不阻止扫描，但待推送公告会失败并保留重试；最终总结通知故障保持业务退出码。；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="17"><code>scripts/auto_buy.py</code></td><td><code>SHYP_TASK</code></td><td>否</td><td>格式：buy（默认）或 points；商城计划 0 0 10 * * *，积分原计划 1 1 1 1 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_NUM</code></td><td>否</td><td>格式：1 至 100 的整数，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_PROMOTION_TYPE</code></td><td>否</td><td>格式：大写字母和下划线，最长 40 字符，默认 EXCHANGE；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_ENABLE</code></td><td>否</td><td>格式：仅 1 允许真实抢购，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_TARGET_TIME</code></td><td>否</td><td>格式：默认 10:00:00；支持 YYYY-MM-DD HH:MM:SS 或 immediate；仅时间已过等待次日，完整日期过期拒绝；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_RETRY_TIMES</code></td><td>否</td><td>格式：1 至 100 的整数，默认 10；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_RETRY_INTERVAL</code></td><td>否</td><td>格式：0.1 至 60 秒，默认 0.3；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_TIMEOUT</code></td><td>否</td><td>格式：1 至 60 秒，默认 10；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_BUY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_ENABLE</code></td><td>否</td><td>格式：仅 1 开启，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_ACTIONS</code></td><td>否</td><td>格式：逗号分隔 read、video、favor、comment、share，默认全部五项；无需用逗号分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_UNFAVOR</code></td><td>否</td><td>格式：仅 1 开启，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_TIMEOUT</code></td><td>否</td><td>格式：1 至 60 秒，默认 30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_LOCAL_TEXT</code></td><td>否</td><td>格式：去除首尾空白并合并连续空白，最长 280 字；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHYP_POINTS_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；预演只生成摘要，不调用联网通知模块；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录；优先 import notify.send，再检查此目录、/ql/data/scripts、/ql/scripts；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="15"><code>scripts/autoclaw_cn_daily.py</code></td><td><code>AUTOCLAW_INTL_TOKENS</code></td><td>是</td><td>格式：每个非空行一个账号；字段和国内变量相同，推荐 JSON 对象。无续期登录态时只填 access，不伪造 refresh。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTOCLAW_REGION</code></td><td>否</td><td>格式：cn 默认国内版；intl 国际版；both 两地区执行，先国内后国际，所选每个地区均须配置账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTOCLAW_CN_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用全任务断网预演，不请求接口、不读写缓存、不实际推送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTOCLAW_INTL_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTOCLAW_CN_STORE_FILE</code></td><td>是</td><td>格式：非符号链接的私有绝对路径；已有文件须为 0600，父目录须存在；以 0600 原子写入。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTOCLAW_INTL_STORE_FILE</code></td><td>是</td><td>格式：非符号链接的私有绝对路径；已有文件须为 0600，父目录须存在；以 0600 原子写入。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录内为 notify.py 或 sendNotify.js，不下载或安装组件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个推送令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：含推送密钥的完整 HTTPS 地址。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECOM_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS 机器人地址或机器人密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS 机器人地址。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_SECRET</code></td><td>是</td><td>格式：与 DINGTALK_WEBHOOK 配套的加签密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_URL</code></td><td>否</td><td>格式：HTTPS 面板根地址，需配套 QL_TOKEN。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_TOKEN</code></td><td>是</td><td>格式：与 QL_URL 配套的访问令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/autosignin.js</code></td><td><code>refreshToken</code></td><td>是</td><td>格式：每个非空行一个刷新令牌，旧版 &amp; 分隔格式需改为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_DRY_RUN</code></td><td>否</td><td>格式：1 为断网预演，不调用业务接口及外部通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；模块不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/autosignin.py</code></td><td><code>E_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址，所有账号共用；可包含代理认证信息但不会输出。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>E_USER_AGENT</code></td><td>否</td><td>格式：单行浏览器标识，禁止换行和空字符。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>E_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演，其他值正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；预演始终只生成通知摘要，不调用外部通知提供方。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径；通知失败保持业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/baidu.py</code></td><td><code>BAIDU_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，其他值关闭，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：含 notify.py 的目录绝对路径；可留空。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDUWANGPAN_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BAIDUWANGPAN_DELAY_MAX</code></td><td>否</td><td>格式：非负整数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：1/0 或常见布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/baiduwp.py</code></td><td><code>BAIDUWP_TASKS</code></td><td>否</td><td>格式：英文逗号分隔 signin,quiz,info；可单独选择；重复项只执行一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BAIDUWP_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演；预演不验证实际登录状态，通知也仅模拟。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 禁用；其余值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知，不是业务执行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="10"><code>scripts/bilibili.py</code></td><td><code>BILIBILI_COIN_NUM</code></td><td>否</td><td>格式：0 至 5 的整数，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_COIN_TYPE</code></td><td>否</td><td>格式：1 或 2，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_MANGA</code></td><td>否</td><td>格式：布尔值，默认 1；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_WATCH</code></td><td>否</td><td>格式：布尔值，默认 1；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_SHARE</code></td><td>否</td><td>格式：布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_SELECT_LIKE</code></td><td>否</td><td>格式：布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_SILVER2COIN</code></td><td>否</td><td>格式：布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BILIBILI_DRY_RUN</code></td><td>否</td><td>格式：布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，不含凭据；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/bsly_draw.py</code></td><td><code>BSLY_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，其他值为实跑；预演仅在本地展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BSLY_ENABLE_DRAW</code></td><td>否</td><td>格式：仅 1 允许实际抽奖；预演无需开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BSLY_MAX_DRAWS</code></td><td>否</td><td>格式：1 至 100 的整数；达到上限即停止，任何未验证成功的请求立即停止该账号，不自动重试。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off（忽略大小写）关闭通知；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；优先 notify.py，失败后尝试其他可用桥接及 sendNotify.js，后者需要青龙环境已有 Node.js。业务 HTTP 不依赖这些桥接。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/bugutv.py</code></td><td><code>BUGUTV_DRY_RUN</code></td><td>否</td><td>格式：默认0；1开启，0、false、no、off关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BUGUTV_LOGOUT</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭全部通知，包括可选Server酱。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，目录内应有notify.py及send函数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BUGUTV_SERVER_SEND_KEY</code></td><td>是</td><td>格式：单个SendKey，允许字母、数字、下划线和短横线；通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>sever_jiang_send_key</code></td><td>是</td><td>格式：单个SendKey，仅在未设置BUGUTV_SERVER_SEND_KEY时使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/bwcj.py</code></td><td><code>BWCJ_TASKS</code></td><td>否</td><td>格式：new、old 或 new,old；默认 new。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_ACTIVITY_ID</code></td><td>否</td><td>格式：数字字符串，默认 947079313798000641。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_STORE_ID</code></td><td>否</td><td>格式：正整数，默认 49006。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BWCJ_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启完全断网预演，默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/caigamer.js</code></td><td><code>CAIGAMER_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知目录的绝对路径，仅用于可选通知，不影响业务独立运行。；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="4"><code>scripts/chevrolet.js</code></td><td><code>xflCookie</code></td><td>是</td><td>格式：每个非空行填写一个 cpctoken；规范变量即使为空也优先，不回退旧变量。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CHEVROLET_DRY_RUN</code></td><td>否</td><td>格式：1 表示断网预演，其他值表示实际签到。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off（不区分大小写）关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；同时自动查找 /ql/data/scripts 和 /ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/ck_2nzz.py</code></td><td><code>NZZ_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认 0；预演仅校验凭据格式，不验证真实业务成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；仅用于通知，不是业务依赖；通知故障不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/ck_acfun.py</code></td><td><code>ACFUN</code></td><td>是</td><td>格式：每个非空行 手机号|密码，或旧账号数组的 JSON，每项包含字符串 phone 和 password。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ACFUN_ACTIONS</code></td><td>否</td><td>格式：逗号分隔的任务名，不重复：sign 签到，info 信息查询，like 点赞后取消，danmu 公开弹幕，banana 投一根香蕉。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ACFUN_DANMU_FALLBACK</code></td><td>否</td><td>格式：归一化空白后 1 至 280 个字符，一言网络、超时、HTTP、大小、JSON、正文或长度异常时使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ACFUN_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 或空值关闭。预演也不调用通知插件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 或空值关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，不是下载地址。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/codearts_daily.py</code></td><td><code>CODEARTS_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用，其余关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个渠道配置值；地址必须为 HTTPS；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：单个渠道配置值；地址必须为 HTTPS；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECOM_WEBHOOK</code></td><td>是</td><td>格式：单个渠道配置值；地址必须为 HTTPS；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_WEBHOOK</code></td><td>是</td><td>格式：单个渠道配置值；地址必须为 HTTPS；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_SECRET</code></td><td>是</td><td>格式：单个渠道配置值；地址必须为 HTTPS；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/comicai_ai_cookie.py</code></td><td><code>comicai_Token</code></td><td>是</td><td>格式：仅当 COMICAI_ACCOUNTS 未设置时生效；每个非空行一个 Token，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>comicai_Cookie</code></td><td>是</td><td>格式：仅当规范变量未设置时生效；每个非空行一个完整 Cookie，行数必须与旧 Token 变量一致；可以不设置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>COMICAI_DRY_RUN</code></td><td>否</td><td>格式：1 启用完全断网预演，默认 0；预演不调用业务接口，不表示真实签到成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，默认 1；通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；依次尝试导入 notify、指定目录及 /ql/data/scripts、/ql/scripts 的 notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/crealitycloud_checkin.py</code></td><td><code>CREALITY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启断网预演；预演成功只说明本地参数和流程检查通过，不表示真实签到成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：true 开启整体随机延时，其他值关闭；预演无延时。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：整数秒，默认 3600；非正数关闭整体延时，非法值沿用默认；多个账号正式运行间隔 10 至 30 秒。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启；通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录，搜索 notify.py；另支持脚本目录、/ql/data/scripts 和 /ql/scripts。预演禁止通知模块联网或运行外部命令。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/dachao.py</code></td><td><code>DACHAO_MODE</code></td><td>否</td><td>格式：all（默认签到和阅读）、sign（签到）、read（阅读）；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DACHAO_MAX_ARTICLES</code></td><td>否</td><td>格式：1 至 100 的整数，默认 6；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DACHAO_LOTTERY</code></td><td>否</td><td>格式：默认 0；1 开启签到和阅读抽奖；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DACHAO_REDEEM</code></td><td>否</td><td>格式：默认 0；1 开启兑换，需同时开启抽奖；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DACHAO_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演；默认 0 为实际执行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径，仅用于青龙通知；业务运行不依赖私有文件；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/daily_benefits.py</code></td><td><code>WPS_TASKS</code></td><td>否</td><td>格式：逗号分隔任务名称：checkin,reward,trial,lottery,task_center,task_center_lottery；账号仍按换行分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WPS_RESTART_SERIES</code></td><td>否</td><td>格式：1 启用；0 关闭。仅对服务端明确返回系列失效重试一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WPS_USER_AGENT</code></td><td>否</td><td>格式：单行浏览器 User-Agent，不含 Cookie 或凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WPS_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全断网预演；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余启用，默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，不填则尝试导入 notify 和 /ql/data/scripts、/ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="22"><code>scripts/dailynewscn.js</code></td><td><code>DAILYNEWSCN_TASK</code></td><td>否</td><td>格式：可选：dailynewscn、bdhot、chouq、day60s、dyhot、jitang、kfc、meiju、miyu、oilprice；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DAILYNEWSCN_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；对所有模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BDHOT_LIST</code></td><td>否</td><td>格式：仅 bdhot 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BDHOT_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 bdhot 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CHOUQ_LIST</code></td><td>否</td><td>格式：仅 chouq 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CHOUQ_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 chouq 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DAY60S_LIST</code></td><td>否</td><td>格式：仅 day60s 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DAY60S_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 day60s 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DYHOT_LIST</code></td><td>否</td><td>格式：仅 dyhot 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DYHOT_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 dyhot 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JITANG_LIST</code></td><td>否</td><td>格式：仅 jitang 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JITANG_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 jitang 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KFC_LIST</code></td><td>否</td><td>格式：仅 kfc 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KFC_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 kfc 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MEIJU_LIST</code></td><td>否</td><td>格式：仅 meiju 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MEIJU_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 meiju 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIYU_LIST</code></td><td>否</td><td>格式：仅 miyu 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIYU_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 miyu 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OILPRICE_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演；仅对 oilprice 模式生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OILPRICE_AREA</code></td><td>否</td><td>格式：中文地区，例如北京；地区行或 JSON area 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；缺失或通知失败保持业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/ddnsto.py</code></td><td><code>ddns_userid</code></td><td>是</td><td>格式：单个路由器ID，仅字母、数字、下划线或连字符；不接受多行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ddns_cookie</code></td><td>是</td><td>格式：单行完整 Cookie，含唯一且非空的 csrftoken；末尾不必带分号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DDNSTO_DRY_RUN</code></td><td>否</td><td>格式：1 启用断网预演，0 执行真实续费；默认 0；也支持 true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。预演尝试通知时封锁网络，因此远程通知不会送达。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：已有通知模块目录的路径，不执行下载或安装。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/deepflood_checkin.py</code></td><td><code>DEEPFLOOD_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启，0/false/no/off 关闭；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DF_RANDOM</code></td><td>否</td><td>格式：字符串，默认 true；仅传给签到接口，不控制本地等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：1/true/yes/on 开启，0/false/no/off 关闭；预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 86400 的整数，默认 3600；仅 RANDOM_SIGNIN 开启时等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DEEPFLOOD_STATS_DAYS</code></td><td>否</td><td>格式：1 至 365 的整数，默认 30；以北京时间计算滚动窗口，最多查询 10 页。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DEEPFLOOD_TIMEOUT</code></td><td>否</td><td>格式：1 至 120 的整数，默认 15。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭通知。预演仅显示脱敏通知预览，不加载模块、不发送网络通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；不安装或下载通知模块，通知不可用不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/durex.py</code></td><td><code>DUREX_DRY_RUN</code></td><td>否</td><td>格式：1 开启断网预演，0 正式执行；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_SHARE</code></td><td>否</td><td>格式：1 开启分享记录上报，0 关闭；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_SHARE_ACT_ID</code></td><td>否</td><td>格式：数字活动编号；默认沿用上游 343766308960192；仅开启分享时使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DUREX_DRAW</code></td><td>否</td><td>格式：1 开启抽奖，0 关闭；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>dlshyzx_drawid</code></td><td>否</td><td>格式：数字活动编号；所有账号参与同一活动；仅 DUREX_DRAW=1 时必填。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；断网预演仅生成本地通知预览。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；否则查找可导入的 notify 和 /ql/data/scripts、/ql/scripts。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="12"><code>scripts/enshan_checkin.py</code></td><td><code>enshan_cookie</code></td><td>是</td><td>格式：与 ENSHAN_COOKIE 相同，每行一个账号；不从 config.json 读取或写回凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EST_cookie</code></td><td>是</td><td>格式：与 ENSHAN_COOKIE 相同，每行一个账号；不从 config.json 读取或写回凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENSHAN_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENSHAN_HTTP_TIMEOUT</code></td><td>否</td><td>格式：5 至 120 的整数秒，默认 20。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENSHAN_MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 3600 的整数秒，默认 0；优先于 MAX_RANDOM_DELAY 和 EST_ENABLE_RANDOM_WAIT。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 3600 的整数秒，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EST_ENABLE_RANDOM_WAIT</code></td><td>否</td><td>格式：1、true、yes、on 开启 0 至 900 秒等待；默认关闭，断网预演始终不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：默认开启；0、false、no、off 禁用等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENSHAN_PRIVACY_MODE</code></td><td>否</td><td>格式：布尔值；ENSHAN_PRIVACY_MODE 优先，默认开启；不会隐藏公开昵称。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PRIVACY_MODE</code></td><td>否</td><td>格式：布尔值；ENSHAN_PRIVACY_MODE 优先，默认开启；不会隐藏公开昵称。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，非必填；脚本业务不依赖通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/epicfreegames.py</code></td><td><code>TG_BOT_TOKEN</code></td><td>是</td><td>格式：单个机器人令牌，不支持用符号分隔多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TG_USER_ID</code></td><td>是</td><td>格式：单个数字会话编号或公开频道用户名，配合 TG_BOT_TOKEN 使用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EPIC_LOCALE</code></td><td>否</td><td>格式：双字母语言代码或语言代码-地区代码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EPIC_COUNTRY</code></td><td>否</td><td>格式：双字母国家代码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EPIC_FONT_PATH</code></td><td>否</td><td>格式：本地字体文件路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EPIC_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启完全断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0/false/no/off 关闭汇总通知，不影响 Telegram 游戏提醒。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/erke.py</code></td><td><code>ERKE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演；默认 0 正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。断网预演仅生成通知摘要并记录未投递，不调用可能联网的通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录，含 notify.py 或 sendNotify.js；通知不可用不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/f1owkang_qingskyland_skyland.py</code></td><td><code>SKYLAND_TOKEN_FILE</code></td><td>是</td><td>格式：文件路径，支持 ~；文件每行一个账号，支持以 # 开头的注释。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKYLAND_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1 启用，0/false/no/off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKYLAND_MODE</code></td><td>否</td><td>格式：auto（默认）、qinglong 或 hermes。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKYLAND_SILENT_OK</code></td><td>否</td><td>格式：on 启用；默认 off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>USE_PROXY</code></td><td>否</td><td>格式：默认 off，忽略系统代理；on 使用系统代理。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NOTIFY_TITLE</code></td><td>否</td><td>格式：默认“森空岛自动签到”。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知模块不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>EXIT_WHEN_FAIL</code></td><td>否</td><td>格式：旧版 on/off 输入不再允许失败返回零。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/fnnasclub.py</code></td><td><code>FNNASCLUB_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启断网预演，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：现有通知模块所在目录路径；业务运行不依赖通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/forum_download.py</code></td><td><code>FORUM_TASKS</code></td><td>否</td><td>格式：逗号分隔 visit、credits、download、sign、sign_plus、work；默认 visit,credits。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FORUM_ALLOW_DOWNLOAD</code></td><td>否</td><td>格式：1 开启；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FORUM_ALLOW_WORK</code></td><td>否</td><td>格式：1 开启；默认 0；work 动作必须开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FORUM_DRY_RUN</code></td><td>否</td><td>格式：1 开启；默认 0；不访问论坛或发送网络通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录；通知失败保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/fwxs_checkin.js</code></td><td><code>FWXS_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网预演，包括模拟通知；不会验证真实账号或执行签到。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，其他值启用；断网预演仅模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；通知模块不可用或失败时不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/fxh.js</code></td><td><code>FXH_DRY_RUN</code></td><td>否</td><td>格式：1 表示完全断网预演；其他值表示实际执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，不区分大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 sendNotify.js 或 notify.py 的目录，不是业务依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/get_yys_cgvideo.py</code></td><td><code>YYS_TASKS</code></td><td>否</td><td>格式：video、image 或 video,image；默认 video；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_DOWNLOAD</code></td><td>否</td><td>格式：1 开启下载；其他值仅列出，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_LIMIT</code></td><td>否</td><td>格式：非负整数；0 表示全部，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_DRY_RUN</code></td><td>否</td><td>格式：1 开启断网预演，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/get_yys_imagelinks.py</code></td><td><code>YYS_TASKS</code></td><td>否</td><td>格式：images（默认）、videos 或 images,videos；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_DOWNLOAD</code></td><td>否</td><td>格式：1 开启下载；0 默认仅解析并列出素材；兼容 true/false、yes/no、on/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_IMAGE_DIR</code></td><td>否</td><td>格式：目录路径，默认 ./yys原画；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_VIDEO_DIR</code></td><td>否</td><td>格式：目录路径，默认 ./yys视频；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_VIDEO_LIMIT</code></td><td>否</td><td>格式：非负整数，默认 0 表示全部；已有文件不计入上限；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_VIDEO_INTERVAL</code></td><td>否</td><td>格式：0 至 3600 的秒数，默认 2；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YYS_DRY_RUN</code></td><td>否</td><td>格式：1 使用内置页面样本且不联网、不写素材、不调用通知服务；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；通知模块不可用不改变任务退出码；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/hellogithub.py</code></td><td><code>HELLOGITHUB_DRY_RUN</code></td><td>否</td><td>格式：1 启用完全断网预演，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用；新刊未提交通知时不更新状态且退出非零。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/hifiti_checkin.py</code></td><td><code>HIFIHI_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号；完整 Cookie 或旧版 cloudmusic.net 的值，不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HIFITI_DRY_RUN</code></td><td>否</td><td>格式：1/0、true/false、yes/no 或 on/off；默认 0。预演不请求站点或通知服务，不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：1/0、true/false、yes/no 或 on/off；多个账号时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数，实际最大等待 3600 秒；设置 0 关闭启动等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 或 sendNotify.js 的目录路径，仅用于可选青龙通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/hlyl.py</code></td><td><code>HLYL_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HLYL_LOTTERY_ATTEMPTS</code></td><td>否</td><td>格式：0 至 10 的整数；0 关闭，正数为每账号最大抽奖请求数，失败立即停止该账号抽奖，不自动重试。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HLYL_LOTTERY_ACTIVITY_ID</code></td><td>否</td><td>格式：1 至 30 位数字，默认 1796131190130262018。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启；通知不可用不改变业务退出码。断网预演仅在封锁套接字的 Python 通知环境中尝试，不进行远程投递。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于可选通知，不是业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/hsay.py</code></td><td><code>HSAYCookie</code></td><td>是</td><td>格式：每个非空行一个完整 Token。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HSAY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/huaruntong_wx.py</code></td><td><code>HRT_WX_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes 或 on 启用断网预演，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。断网预演仅模拟发送通知，不调用任何通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；不下载或安装通知程序。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/hykb_gamesign.js</code></td><td><code>HYKB_DRY_RUN</code></td><td>否</td><td>格式：1 或 0；默认 0。预演不请求业务接口，也不载入通知发送模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HYKB_ALLOW_EXPERIENCE</code></td><td>否</td><td>格式：1 或 0，默认 0。关闭时如活动要求试玩则记失败，不伪报已签到。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HYKB_ALLOW_SHARE</code></td><td>否</td><td>格式：1 或 0，默认 0。仅记录官方 sharelimit 动作，不发布公开文本；关闭时如需分享则记失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：1、true、yes、on 开启；0、false、no、off 关闭。通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，只用于可选通知；业务功能不依赖该文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="10"><code>scripts/ikuuu_checkin.py</code></td><td><code>ikuuu</code></td><td>是</td><td>格式：每行邮箱#密码，仅在第一个 # 处分割，保留后续密码字符。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_COOKIES</code></td><td>是</td><td>格式：每行完整 Cookie 或 备注||完整 Cookie，只在第一个 || 处分割；备注不输出，# 开头行跳过；每个 Cookie 必须包含 uid、email、key，不用 &amp; 分隔字段或账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_HOST</code></td><td>否</td><td>格式：仅 HTTPS 主机名，不含协议、端口或路径；未设置时邮箱模式用 ikuuu.nl，Cookie 模式用 ikuuu.win。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_PROFILE</code></td><td>否</td><td>格式：默认 0；设 1 开启，资料失败仍尝试签到，但该账号整体失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_FLOW</code></td><td>否</td><td>格式：未设置时仅 Cookie 模式开启；设 1 全部开启，设 0/false/no/off 全部关闭。查询失败仍保留签到结果，但账号整体失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 3600 整数秒，默认 0；断网预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_DRY_RUN</code></td><td>否</td><td>格式：默认 0；设 1 仅验证参数与请求计划，不请求、不等待、不导入或投递通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭；预演仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录；否则尝试 import notify.send、/ql/data/scripts/notify.py、/ql/scripts/notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个通知 Token；仅向 HTTPS PushPlus 通知接口发送，不进入日志；受 QINGLONG_NOTIFY 控制，预演不投递。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/imaotai.py</code></td><td><code>IMAOTAI_RESERVE</code></td><td>否</td><td>格式：默认 0；1 开启，0、false、no、off 关闭；商品编号按实际活动更新。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IMAOTAI_ENERGY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；至少启用一项任务。申购模式每个商品请求后等待 20 秒领取耐力。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IMAOTAI_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1 完全断网预演，不查询接口、不申购、不领奖。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用。断网预演仅展示本地脱敏通知总结。正式运行通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：notify.py 或 sendNotify.js 所在目录；默认查找标准青龙路径和可导入的 notify 模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/index.js</code></td><td><code>PIXIV_OUTPUT</code></td><td>否</td><td>格式：目录路径；新图片保存为 标题_作品ID/标题_页码.扩展名，兼容检查旧版 标题/标题_页码.扩展名。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PIXIV_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，大小写不敏感；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知组件目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="16"><code>scripts/iqiyi_checkin.py</code></td><td><code>IQIYI_COOKIE</code></td><td>是</td><td>格式：每个非空行一个账号，形如 P00001=&lt;登录凭据&gt;; P00003=&lt;用户编号&gt;; __dfp=&lt;设备字段&gt;。分号分隔同账号字段，每个字段仅按第一个等号拆分；保留值中其余等号。设备字段仅使用 @ 前段，@ 不分隔账号。优先使用 __dfp；P00002、QC005 等额外 Cookie 字段允许保留，不单独要求。# 开头的行作为注释。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_CHANCES</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_LOTTERY</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_LOTTERY_ALL</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_SHAKE</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_SHAKE_ALL</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_GIVE_TIMES</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_PLATINUM</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_V7</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_VIP_SIGN</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_DAILY_TASKS</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IQIYI_DRY_RUN</code></td><td>否</td><td>格式：默认 0；支持 1/0、true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；1、true、yes、on 开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径，不安装或下载任何文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个令牌，不按账号拆分。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SENDKEY</code></td><td>是</td><td>格式：单个推送密钥，不按账号拆分。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/jc_checkin.py</code></td><td><code>EMAIL</code></td><td>是</td><td>格式：单个注册邮箱；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PASSWORD</code></td><td>是</td><td>格式：单个密码，不可用换行分隔多个账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JC_DRY_RUN</code></td><td>否</td><td>格式：1/0、true/false、yes/no 或 on/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：通知开关；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JC_PUSHPLUS</code></td><td>否</td><td>格式：1/0、true/false、yes/no 或 on/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SCKEY</code></td><td>是</td><td>格式：PushPlus 推送令牌，不放入请求 URL；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/jcqd.py</code></td><td><code>jcuname</code></td><td>是</td><td>格式：单账号登录邮箱；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>jcpasswd</code></td><td>是</td><td>格式：单账号完整密码；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JCQD_TASKS</code></td><td>否</td><td>格式：ikuuu、v2free、gw，可用逗号组合；默认 ikuuu；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IKUUU_BASE_URL</code></td><td>否</td><td>格式：仅 HTTPS 域名，无路径、查询参数、用户信息或非标准端口；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JCQD_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0/false/no/off 关闭，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/jingyiluntan_sign.py</code></td><td><code>JYLT_RATE</code></td><td>否</td><td>格式：1 开启热门帖逐帖 +1 评分，0 关闭；评分失败或额度受限时停止该账号评分并返回失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYLT_LOCAL_TEXT</code></td><td>否</td><td>格式：归一化后不超过 280 字；空值或超长时使用内置文字。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYLT_DRY_RUN</code></td><td>否</td><td>格式：1 完全断网模拟所有请求和通知，0 正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启；通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；脚本业务不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/jissbon.py</code></td><td><code>JSB_DRY_RUN</code></td><td>否</td><td>格式：1启用断网预演；0实际执行，默认0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JSB_LOTTERY</code></td><td>否</td><td>格式：1启用抽奖；默认0关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JSB_LOTTERY_COUNT</code></td><td>否</td><td>格式：1至10的整数，默认10；次数已用完或失败立即停止抽奖。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；只用于可选通知，不是业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="10"><code>scripts/jyj.py</code></td><td><code>jyjlatlon</code></td><td>是</td><td>格式：纬度#经度；分别在[-90,90]和[-180,180]内，所有账号共用本人授权位置。沿用原执行代码顺序，修正原说明文字错误。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_TASKS</code></td><td>否</td><td>格式：逗号分隔：info,sign,beat,turntable,like,subscribe,survey,share,run,garden,daily-water,photo,photo-query,health-draw,red-rain,herb-game。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>jyjRun</code></td><td>否</td><td>格式：1开启运动奖励领取；其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_PLANT_TYPE</code></td><td>否</td><td>格式：正整数；留空不自动种植。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_WATER_LIMIT</code></td><td>否</td><td>格式：0至100整数，默认0，不自动消耗水滴。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_PHOTO_PATH</code></td><td>是</td><td>格式：已有JPEG照片路径，非空且不超过10MB。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_HERB_SCORE</code></td><td>否</td><td>格式：非负整数；未设置则不允许执行herb-game。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JYJ_DRY_RUN</code></td><td>否</td><td>格式：1开启；0、false、no、off关闭，默认0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭。预演调用本地适配器但阻断网络。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含notify.py或sendNotify.js的目录路径；通知失败保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/kgqq.py</code></td><td><code>KGQQ_COOKIES</code></td><td>是</td><td>格式：与 KGQQ_COOKIE 相同；规范变量有值时不读取此别名。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KGQQ_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启，0/false/no/off 关闭，默认 0；预演只检查凭据结构及任务计划，不校验账号真实性、不发送通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KGQQ_LOTTERY</code></td><td>否</td><td>格式：布尔开关，默认 0；开启四类上游抽奖入口。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KGQQ_MUSIC_REWARDS</code></td><td>否</td><td>格式：布尔开关，默认 0；每个账号一次读取卡片并按上游档位领取最高奖励，不枚举鉴权参数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1，0/false/no/off 关闭；通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录；业务执行无此模块也能独立运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/kjwj.py</code></td><td><code>KJWJ_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；不是业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/kuku_daily.py</code></td><td><code>KUKU_COOKIES</code></td><td>是</td><td>格式：Cookie 请求头、编辑器 JSON 或键值对象，包含 BDUSS。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUKU_STOKEN</code></td><td>是</td><td>格式：完整产品会话令牌，与 KUKU_COOKIES 配套。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUKU_TOKENS</code></td><td>是</td><td>格式：每个非空行：备注|BDUSS|PTOKEN|STOKEN；最多分割前三个竖线。不支持用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUKU_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址；不支持 SOCKS。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUKU_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全断网预演，0 正式领取。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余非空值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，仅用于可选通知，不是业务依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUKU_NO_NOTIFY</code></td><td>否</td><td>格式：1 关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/kurobbs_sign.py</code></td><td><code>kurobbs</code></td><td>是</td><td>格式：单账号 Token，不支持旧式账号分隔符；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>kuro_uid</code></td><td>是</td><td>格式：单账号数字社区 UID，与 kurobbs 配对；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUROBBS_DRY_RUN</code></td><td>否</td><td>格式：1 开启；0 关闭，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUROBBS_LIKE</code></td><td>否</td><td>格式：1 开启；0 关闭，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KUROBBS_SHARE</code></td><td>否</td><td>格式：1 开启；0 关闭，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/l.py</code></td><td><code>BROWSE_ENABLED</code></td><td>否</td><td>格式：true、1、yes、on 启用；false、0、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TOPIC_LIMIT</code></td><td>否</td><td>格式：1 至 500 的整数；HTTP 首页无动态滚动，实际数量受返回页面限制。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BROWSE_COUNT</code></td><td>否</td><td>格式：0 至 500 的整数，0 跳过浏览。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LINUXDO_DRY_RUN</code></td><td>否</td><td>格式：1 完全断网，包括通知；使用本地样例，不验证账号或真实业务。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块目录的绝对路径；不属于业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="18"><code>scripts/leaflow_checkin_pyleaflow_checkin.py</code></td><td><code>LEAFLOW_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFLOW_BASE</code></td><td>否</td><td>格式：HTTPS 根地址，无用户名、密码、路径、查询或片段；默认 https://checkin.leaflow.net。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFLOW_TIMEOUT</code></td><td>否</td><td>格式：1 至 120 的整数秒，默认 20；维护参数优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFLOW_RETRIES</code></td><td>否</td><td>格式：1 至 5 的整数，默认 3；维护参数优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFLOW_RETRY_DELAY</code></td><td>否</td><td>格式：0 至 60 的整数秒，默认 3；维护参数优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFLOW_MAX_DELAY</code></td><td>否</td><td>格式：0 至 3600 的整数秒，维护版默认 0；维护参数优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LEAFFLOW_BASE</code></td><td>否</td><td>格式：与 LEAFLOW_BASE 相同；新参数未设置时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIMEOUT</code></td><td>否</td><td>格式：1 至 120 的整数秒；新参数未设置时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RETRY_TIMES</code></td><td>否</td><td>格式：1 至 5 的整数；新参数未设置时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RETRY_DELAY</code></td><td>否</td><td>格式：0 至 60 的整数秒；新参数未设置时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 3600 的整数秒；新参数未设置时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：显式 true 开启旧随机窗口，窗口未设置时为 3600 秒；显式其他值关闭；新窗口参数优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NOTIFY_ON_ALREADY</code></td><td>否</td><td>格式：默认 true；其他值关闭此类明细，仍发送任务总数汇总。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DEBUG_MODE</code></td><td>否</td><td>格式：接受旧值但不保存原始响应，也不显示页面片段。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭；预演只生成本地通知内容，不加载或调用通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录，可选；亦支持 import notify.send、/ql/data/scripts/notify.py 和 /ql/scripts/notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HTTP_PROXY</code></td><td>是</td><td>格式：标准库支持的代理地址；兼容 http_proxy。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HTTPS_PROXY</code></td><td>是</td><td>格式：标准库支持的代理地址；兼容 https_proxy。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/littlewuh_qinglongbox_dailycheckin_scripts.py</code></td><td><code>NZZ_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，不含 notify.py 文件名。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/lizhixu_ql_script_hub_nodeseek.py</code></td><td><code>NS_RANDOM</code></td><td>否</td><td>格式：布尔值：true/false，也支持 1/0、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：布尔值；false 表示立即签到。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数秒；账号按随机计划时间排序，等待使用同一起点，避免累积延时。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NODESEEK_DRY_RUN</code></td><td>否</td><td>格式：布尔值；开启后不加载 HTTP 依赖、不请求接口、不等待、不执行签到，通知器在禁止网络的子进程中尝试发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知；其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知组件不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/lizhixu_ql_script_hub_youdao.py</code></td><td><code>YOUDAO_DRY_RUN</code></td><td>否</td><td>格式：1 或 0，也支持 true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YOUDAO_AD_REWARDS</code></td><td>否</td><td>格式：1 或 0，也支持 true/false、yes/no、on/off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1，关闭值为 0、false、no、off。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径；只用于可选通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/lobsterai_checkin.py</code></td><td><code>LOBSTERAI_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LOBSTERAI_REFRESH_STORE</code></td><td>否</td><td>格式：本机文件路径；文件使用 0600 权限原子保存。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可信本机通知模块目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个推送令牌，不是账号凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/loomy_daily.py</code></td><td><code>LOOMY_ONBOARDING</code></td><td>否</td><td>格式：0（默认，仅每日积分）或 1（批量领取）；--no-onboarding 优先关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LOOMY_DRY_RUN</code></td><td>否</td><td>格式：1 启用，0 默认正式执行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：推送令牌；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：完整 HTTPS 地址；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECOM_WEBHOOK</code></td><td>是</td><td>格式：HTTPS Webhook 地址或机器人 key；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS 地址；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_SECRET</code></td><td>是</td><td>格式：加签密钥；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="21"><code>scripts/lynkco_qinglong_single.py</code></td><td><code>LYNKCO_REFRESH_TOKEN</code></td><td>是</td><td>格式：每行一个刷新令牌，与设备标识按行配对。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_DEVICE_ID</code></td><td>是</td><td>格式：每行一个同账号deviceId，不广播单个设备标识。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_TOKEN</code></td><td>是</td><td>格式：每行一个静态令牌，按行配对回退；可单独使用，兼容bearer无空格前缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_NATIVE_APP_KEY</code></td><td>是</td><td>格式：单个字符串，对应nativeAppKey；不分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_NATIVE_APP_SECRET</code></td><td>是</td><td>格式：单个字符串，对应nativeAppSecret；不分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_NATIVE_APP_CODE</code></td><td>是</td><td>格式：单个字符串，对应nativeAppCode；不分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_LOGIN_APP_CODE</code></td><td>是</td><td>格式：单个字符串，对应loginAppCode；不分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_NATIVE_GL_DEV_ID</code></td><td>是</td><td>格式：单个字符串，对应glDevId；不分账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_DO_SHARE</code></td><td>否</td><td>格式：1签到并分享；0、false、no、off关闭分享。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_SHARE_MODE</code></td><td>否</td><td>格式：默认simple两步链；full完整三步链，必须设置LYNKCO_CONTENT_ID。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_CONTENT_ID</code></td><td>否</td><td>格式：单个文章内容编号，不是账号凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_ARTICLE_ID</code></td><td>否</td><td>格式：单个文章编号，不是账号凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_TIMEOUT</code></td><td>否</td><td>格式：请求超时秒数，默认30，范围大于0且不超过120。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_ENERGY_DELAY</code></td><td>否</td><td>格式：积分查询等待秒数，默认5，范围0至120。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_ENV_FILE</code></td><td>是</td><td>格式：可选JSON文件路径，包含secrets、user；只有无账号环境输入时才使用单账号user。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_DRY_RUN</code></td><td>否</td><td>格式：默认0；1完全断网，不发送请求，不验证真实业务成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off关闭全部通知，其余开启；通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_QL_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭青龙渠道，Bark仍受全局开关控制。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录；预演只尝试禁止联网的Python通知，不启动Node通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_BARK_KEY</code></td><td>是</td><td>格式：单个推送Key，仅向固定Bark服务发送脱敏总结。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LYNKCO_BARK_ICON</code></td><td>否</td><td>格式：可选图标URL。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/main.py</code></td><td><code>WALLHAVEN_PAGES</code></td><td>否</td><td>格式：1 至 100 的整数，默认 5。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WALLHAVEN_DRY_RUN</code></td><td>否</td><td>格式：0、false、no、off 表示正式运行；其他值表示断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。断网预演仅生成通知摘要，不调用通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/mifan_optimized.py</code></td><td><code>MIFAN_USER</code></td><td>是</td><td>格式：每个非空行一个用户名；不支持旧版分号多账号分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIFAN_PASSWORD</code></td><td>是</td><td>格式：每个非空行一个密码，行数必须与用户名一致。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIFAN_TASKS</code></td><td>否</td><td>格式：sign、like、comment、repair 用逗号组合；默认sign；点赞每次最多20条，评论每次最多10条。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENABLE_REPAIR</code></td><td>否</td><td>格式：true或1开启补签；默认false。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIFAN_DRY_RUN</code></td><td>否</td><td>格式：1开启；默认0；不调用业务、文本提供商或通知网络，不读写进度。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIFAN_LOCAL_TEXT</code></td><td>否</td><td>格式：单段文本，空白折叠后最多280字；不要填写任何隐私或凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIFAN_STATE_DIR</code></td><td>否</td><td>格式：目录路径；按账号哈希隔离点赞和评论进度，不保存密码或Token。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭；预演仅记录通知摘要准备状态。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；通知组件可选，缺失或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/mimotion.py</code></td><td><code>MIMOTION</code></td><td>是</td><td>格式：JSON 数组；每个对象支持 phone、password、min_step、max_step；上传仍须本人 data_json、last_deviceid。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIMOTION_ACTION</code></td><td>否</td><td>格式：login 或 upload，默认 login。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIMOTION_MIN_STEP</code></td><td>否</td><td>格式：整数，默认 10000；0≤最小值≤最大值≤100000。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIMOTION_MAX_STEP</code></td><td>否</td><td>格式：整数，默认 19999；与最小步数构成含两端的随机范围。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIMOTION_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 或空值关闭，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录；不是业务脚本依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/netease_task.py</code></td><td><code>NETEASE_COOKIES</code></td><td>是</td><td>格式：每个非空行一条 Cookie，支持 # 注释和包裹整行的引号；非空时优先于 NETEASE_COOKIE。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NETEASE_WEB_SIGN_WEAPI</code></td><td>否</td><td>格式：1 使用官方 weapi 网页签到并显示积分；默认 0 保留原 API 方式，其他阶段不变。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NETEASE_SCROBBLE</code></td><td>否</td><td>格式：默认 0；只有 1 开启随机模拟听歌记录，最多 300 首。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NETEASE_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演，默认 0 为正式执行；预演不验证真实账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知，预演只模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个令牌；青龙通知失败时使用 HTTPS JSON 接口，业务码 200 才确认送达。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SENDKEY</code></td><td>是</td><td>格式：单个 SendKey；青龙与 PushPlus 均不可用时使用，业务码 0 才确认送达。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：HTTPS 地址，不含查询参数或片段；保留独立推送，受全局通知开关控制。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="15"><code>scripts/nga_checkin.py</code></td><td><code>nga_uid</code></td><td>是</td><td>格式：每行一个值，三个旧版变量必须逐行对应同一账号；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>nga_cookie</code></td><td>是</td><td>格式：每行一个值，三个旧版变量必须逐行对应同一账号；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>nga_client_checksum</code></td><td>是</td><td>格式：每行一个值，三个旧版变量必须逐行对应同一账号；不使用 &amp; 或 @ 分隔账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_UA</code></td><td>否</td><td>格式：默认 Nga_Official/90409；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_DRY_RUN</code></td><td>否</td><td>格式：默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_DAILY_MISSIONS</code></td><td>否</td><td>格式：默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_VIDEO_MISSIONS</code></td><td>否</td><td>格式：默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ENABLE_SHARE_MISSIONS</code></td><td>否</td><td>格式：默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_QUERY_STATS</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_RANDOM_DELAY_MAX</code></td><td>否</td><td>格式：默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_ACTION_DELAY_SECONDS</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_VIDEO_DELAY_SECONDS</code></td><td>否</td><td>格式：默认 30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NGA_HTTP_TIMEOUT</code></td><td>否</td><td>格式：默认 20；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：默认 未设置；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/nodeseek.py</code></td><td><code>NS_RANDOM</code></td><td>否</td><td>格式：true 随机奖励，false 固定奖励。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_IMPERSONATE</code></td><td>否</td><td>格式：curl_cffi 支持的浏览器指纹名称。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他值启用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录；通知不可用或失败不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/nodeseek_checkin.py</code></td><td><code>NODESEEK_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_RANDOM</code></td><td>否</td><td>格式：布尔值，默认 true；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：布尔值，默认 false；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0..86400 整数秒，默认 3600；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NS_STATS_DAYS</code></td><td>否</td><td>格式：1..365 整数天，默认 30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0/false/no/off 表示禁用，默认启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/nte.py</code></td><td><code>TOKEN</code></td><td>是</td><td>格式：每个非空行一个账号，格式同 NTE_TOKEN。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TGD_GAME_ID</code></td><td>否</td><td>格式：单个游戏编号，默认 1289；账号对象 gameId 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TGD_SIGN_GAME_IDS</code></td><td>否</td><td>格式：逗号分隔编号；尝试顺序为本变量、账号 gameId、默认编号、1289、1257，去重。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TGD_ROLE_IDS</code></td><td>否</td><td>格式：逗号分隔角色编号，追加到各账号角色列表；留空自动发现。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NTE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启断网预演；其余值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录；未设置时尝试 import notify、/ql/data/scripts/notify.py、/ql/scripts/notify.py。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="13"><code>scripts/officeace_daily.py</code></td><td><code>OFFICEACE_AK</code></td><td>是</td><td>格式：临时 AK；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_SK</code></td><td>是</td><td>格式：临时 SK；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_STS</code></td><td>是</td><td>格式：临时 security_token；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_PROJECT_ID</code></td><td>是</td><td>格式：项目 ID；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_BASE_URL</code></td><td>是</td><td>格式：网关地址；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OFFICEACE_RETRIES</code></td><td>否</td><td>格式：0 到 5 的整数，默认 2；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NO_NOTIFY</code></td><td>否</td><td>格式：1、true、yes、on 关闭全部推送；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QYWX_TOKEN</code></td><td>是</td><td>格式：机器人密钥或 webhook 地址，优先于 WECHAT_WEBHOOK；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECHAT_WEBHOOK</code></td><td>是</td><td>格式：机器人密钥或 webhook 地址；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PLUSPLUS_TOKEN</code></td><td>是</td><td>格式：推送令牌，通过 HTTPS 投递；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/ole.py</code></td><td><code>OLE_CONFIG_JSON</code></td><td>是</td><td>格式：JSON 对象，结构为 huaruntong.ole.accounts 数组；数组内保留原账号字段。无需私有文件路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OLE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认 0。预演不代表真实业务成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。断网预演生成摘要并模拟投递，不运行通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录路径，仅用于青龙通知；不可用或失败不会改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/passnat_checkin.py</code></td><td><code>PASSNAT_DRY_RUN</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数秒，默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/psnine.py</code></td><td><code>PSNID</code></td><td>是</td><td>格式：单账号 psnid，必须配合 SHELL。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHELL</code></td><td>是</td><td>格式：单账号 shell 凭据，必须配合 PSNID。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PSNINE_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知不可用或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="15"><code>scripts/pt_sign_v5.js</code></td><td><code>PT_SITE_HDKYL_URL</code></td><td>否</td><td>格式：无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SITE_CARPT_URL</code></td><td>否</td><td>格式：无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SITE_AFUN_URL</code></td><td>否</td><td>格式：无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SITES</code></td><td>否</td><td>格式：逗号分隔的站点键，例如 hdkyl,carpt；这是站点选择设置，不是账号分隔符。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认实际签到；预演仍校验必需凭据的格式，但不验证真实账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_WEBHOOK_URL</code></td><td>是</td><td>格式：无内嵌用户名或密码的 HTTPS 完整地址；不要公开其中的推送密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_WEBHOOK_TYPE</code></td><td>否</td><td>格式：feishu、bark、sct、ding、wx、custom；默认 custom。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_PROXY</code></td><td>是</td><td>格式：HTTP 或 HTTPS 代理地址，可含代理认证信息；默认直接连接。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_RETRY</code></td><td>否</td><td>格式：1 至 10 的整数，默认 3；签到提交超时或业务状态未知时停止自动重试，避免重复提交。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_TIMEOUT</code></td><td>否</td><td>格式：1000 至 120000 的整数，默认 20000；Webhook 固定 8000 毫秒；青龙通知最多等待 15000 毫秒。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_SAFELINE</code></td><td>否</td><td>格式：0 关闭，其他值启用；仅向挑战服务发送挑战令牌和浏览器属性，不发送账号 Cookie 或额外认证头。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_EXTRA_HEADERS</code></td><td>是</td><td>格式：key1:value1|key2:value2；仅在第一个冒号处分割；禁止 Cookie、认证、代理认证、Host、内容长度、Origin、Referer、Content-Type 和伪造来源 IP 等受保护字段。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PT_DEBUG</code></td><td>否</td><td>格式：1、true、yes、on 启用；不输出 HTML、表单令牌、Cookie、代理地址或原始响应。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭青龙通知及可选 Webhook；其他值开启。断网预演只模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知模块不可用、失败或超时只记录状态，不改变签到退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/qoder_airscript.js</code></td><td><code>QODER_ACCOUNTS_FILE</code></td><td>否</td><td>格式：可选私有 JSONL 文件路径，内容与 QODER_ACCOUNTS 相同，设置后优先读取此文件作为兼容输入。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QODER_REGION</code></td><td>否</td><td>格式：cn 或 global，默认 cn；账号 region 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QODER_ACTION</code></td><td>否</td><td>格式：checkin（默认）查询并领取活动；refresh 仅刷新令牌，仍须显式启用账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QODER_ONLY</code></td><td>否</td><td>格式：可选从 1 开始的正整数，留空表示全部账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QODER_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 为断网预演，不请求业务或通知接口，不写回文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0/false/no/off 关闭全部通知；--no-notify 同样关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：通知模块所在目录，仅用于通知，业务独立运行；模块不存在或投递失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/quark_signin.py</code></td><td><code>QUARK_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QUARK_TIMEOUT_SECONDS</code></td><td>否</td><td>格式：3 至 60 的整数秒数，默认 15。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QUARK_RANDOM_DELAY_MAX_SECONDS</code></td><td>否</td><td>格式：0 至 3600 的整数秒数，默认 0；预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，无需安装或下载应用。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="12"><code>scripts/raccoon_daily.py</code></td><td><code>RACCOON_DRY_RUN</code></td><td>否</td><td>格式：1 完全断网、通知模拟、不写台账；0 正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RACCOON_STATE_FILE</code></td><td>否</td><td>格式：默认脚本旁 raccoon_onboarding.json，仅保存令牌哈希和奖励结算时间。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RACCOON_MAIN_SITE_URL</code></td><td>否</td><td>格式：默认 https://xiaohuanxiong.com；无内嵌凭据、无路径及查询串的 HTTPS 站点。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他非空值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；也尝试导入 notify.send 和标准青龙目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个推送令牌，仅用于通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：完整 HTTPS 推送地址，仅用于通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECOM_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS Webhook 或机器人密钥，仅用于通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS Webhook，仅用于通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_SECRET</code></td><td>是</td><td>格式：与 DINGTALK_WEBHOOK 配套，仅用于通知签名。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_URL</code></td><td>否</td><td>格式：完整 HTTPS 面板地址，不包含登录凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_TOKEN</code></td><td>是</td><td>格式：与 QL_URL 配套，仅用于兼容通知接口。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/rainyun.py</code></td><td><code>RAINYUN_DRY_RUN</code></td><td>否</td><td>格式：默认 0；设置 1 开启完全断网预演，仅验证参数与执行计划，跳过业务请求和通知实际发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，可选。业务脚本不依赖通知模块存在，通知失败保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="89"><code>scripts/rousi_checkin.js</code></td><td><code>ROUSI_COOKIE</code></td><td>是</td><td>格式：旧版凭据兼容输入，每个非空行一个完整 Cookie；不拆分 Cookie 内的 &amp;、@、分号或等号。Token 与 Cookie 为可替换认证方式，无需配对，同一账号请只选一种。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_1</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_2</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_3</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_4</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_5</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_6</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_7</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_8</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_9</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_10</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_11</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_12</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_13</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_14</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_15</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_16</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_17</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_18</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_19</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_TOKEN_20</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_1</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_2</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_3</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_4</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_5</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_6</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_7</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_8</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_9</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_10</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_11</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_12</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_13</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_14</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_15</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_16</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_17</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_18</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_19</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_COOKIE_20</code></td><td>是</td><td>格式：旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。规范凭据变量，每个非空行一个账号 Token，可带 Bearer 前缀；禁止用 &amp; 或 @ 分隔账号。已有兼容变量也能独立提供凭据，无需同时配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版凭据兼容输入，每个非空行一个完整 Cookie；不拆分 Cookie 内的 &amp;、@、分号或等号。Token 与 Cookie 为可替换认证方式，无需配对，同一账号请只选一种。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_1</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_2</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_3</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_4</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_5</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_6</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_7</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_8</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_9</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_10</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_11</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_12</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_13</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_14</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_15</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_16</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_17</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_18</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_19</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_token_20</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_1</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_2</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_3</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_4</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_5</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_6</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_7</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_8</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_9</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_10</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_11</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_12</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_13</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_14</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_15</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_16</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_17</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_18</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_19</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>rousi_cookie_20</code></td><td>是</td><td>格式：小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ROUSI_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示完全断网预演；默认关闭。预演只验证参数和流程，不代表真实业务成功，通知仅模拟。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭青龙与 PushPlus 通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径；仅通知扩展使用，业务不依赖该目录或私有仓库。缺失或失败仅记录，不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：一个推送令牌，用于可选 HTTPS 通知，不是 Rousi 账号凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>pushplus_token</code></td><td>是</td><td>格式：旧版小写兼容输入，PUSHPLUS_TOKEN 非空时优先使用大写变量。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TYPE</code></td><td>否</td><td>格式：默认 wechat；兼容 pushplusvip、wxgo、qywxgo、email、feishu、dingtalk、bark，其余值按上游使用 send。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sf.py</code></td><td><code>SF_CONFIG</code></td><td>是</td><td>格式：文件路径，文件结构为 sf.accounts 数组，沿用 sign、channel、device_id、user_agent、account_name 字段。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_TASK_CODES</code></td><td>否</td><td>格式：逗号分隔任务代码，默认空；空时仅签到、任务查询和积分查询。非日常任务始终跳过。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 或空值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 或空值关闭；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知缺失或失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/sfsu_checkin.py</code></td><td><code>SFSU_DRY_RUN</code></td><td>否</td><td>格式：布尔值；1 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_AUTO_COUPON</code></td><td>否</td><td>格式：布尔值；1 表示启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SF_RANDOM_DELAY_MAX</code></td><td>否</td><td>格式：0 至 86400 的整数秒数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：布尔开关，默认启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sgs.py</code></td><td><code>SGS_TASKS</code></td><td>否</td><td>格式：逗号分隔，无重复：info（账号信息）、sign（签到）、read（最多五篇阅读）、service（五次服务计数）、activity（五次活动计数）。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SGS_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录，无需业务仓库或安装器。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/shuyi.py</code></td><td><code>SHUYI_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示完全断网预演，其他值表示实际执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径；业务功能不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSH_PLUS_TOKEN</code></td><td>是</td><td>格式：单个 PushPlus 令牌；不设置则不请求该推送接口。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/sign_in.py</code></td><td><code>KANXUE_CONFIG</code></td><td>是</td><td>格式：本地文件路径；文件含 kanxue.accounts 或 kanxue.kanxue.accounts 数组，每个对象包含 cookie、csrf_token，可选 user_agent、account_name。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KANXUE_DRY_RUN</code></td><td>否</td><td>格式：1 开启，0、false、no、off 或空值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="16"><code>scripts/skland_daily.py</code></td><td><code>SKLAND_PHONE</code></td><td>是</td><td>格式：与 SKLAND_PASSWORD 成对设置，一个账号；不能用作多账号分隔输入。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_PASSWORD</code></td><td>是</td><td>格式：与 SKLAND_PHONE 成对设置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_TOKEN_N</code></td><td>是</td><td>格式：每个序号变量仍按非空行解析账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_PHONE_N</code></td><td>是</td><td>格式：与同序号 SKLAND_PASSWORD_N 成对设置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_PASSWORD_N</code></td><td>是</td><td>格式：与同序号 SKLAND_PHONE_N 成对设置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_DID</code></td><td>是</td><td>格式：单个设备标识，不输出到日志。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_ACTIONS</code></td><td>否</td><td>格式：逗号分隔 checkin、view、like、share、attendance、endfield；attendance 仅明日方舟，endfield 仅终末地；原源游戏签到可设置 attendance,endfield。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_ZONE_IDS</code></td><td>否</td><td>格式：逗号分隔版区编号；只筛选社区动作，不筛选游戏签到角色。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_VIEW_COUNT</code></td><td>否</td><td>格式：非负整数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_LIKE_COUNT</code></td><td>否</td><td>格式：非负整数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_SHARE_COUNT</code></td><td>否</td><td>格式：非负整数；接口只计数，不发布文本。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKYLAND_TYPE</code></td><td>否</td><td>格式：不参与任务选择。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_NOTIFY_URL</code></td><td>是</td><td>格式：HTTPS 地址，禁止重定向和 URL 用户名密码；不得填写账号凭据。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用完全断网预演，默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；通知模块不可用、超时或失败时保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/skland_demo.py</code></td><td><code>TOKEN</code></td><td>是</td><td>格式：每个非空行一个通行证或单行 JSON；旧版逗号分隔需改为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_ACTION</code></td><td>否</td><td>格式：sign：登录并签到；send-code：显式发送短信，不签到。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKYLAND_TYPE</code></td><td>否</td><td>格式：sign 或 send-code；add_account 已移除，不再保存凭据文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_GAMES</code></td><td>否</td><td>格式：arknights,endfield，或其中任意一个；逗号仅用于游戏选项。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_REFRESH</code></td><td>否</td><td>格式：1 开启；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SKLAND_DRY_RUN</code></td><td>否</td><td>格式：1 开启断网预演；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；通知不可用不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/skyland.py</code></td><td><code>SKYLAND_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，默认 1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="14"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_COOKIE_LIST</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie，必须含 sess；固定活动模式下优先于其他旧 Cookie 变量。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_COOKIE</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie，至少含 sess；客户端签到另配同顺序 SMZDM_SK，或 Cookie 内带 sk。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_COOKIES</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie；可用 # 开头的注释行；客户端签到另配配套 sk。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_SK</code></td><td>是</td><td>格式：每个非空行一个 sk；需要 sk 时行数须与旧 Cookie 账号数相同。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_ACTION</code></td><td>否</td><td>格式：checkin：签到；lottery：既有会员转盘；all：签到和既有会员转盘；upstream-lottery：仅原固定活动一次抽奖。固定活动原调度为 45 0 15 * * *，会员转盘原独立调度为 20 8 * * *，需在相应任务环境中选择模式。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_TOKEN_MODE</code></td><td>否</td><td>格式：sess、robot 或 web；默认 sess。网页模式无需 sk。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_INTERACTION</code></td><td>否</td><td>格式：none、value、article 或 both；默认 none，每类最多七条，原互动调度 29 0-23/8 * * * 可自定义。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_LOTTERY_LIFE</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_USER_AGENT_APP</code></td><td>否</td><td>格式：可选请求头字符串；未配置时使用各模式既有客户端配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。离线预演仅生成脱敏通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录；组件缺失或发送失败只记录通知状态，不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：可选推送令牌，受 QINGLONG_NOTIFY 控制。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SENDKEY</code></td><td>是</td><td>格式：可选推送密钥，受 QINGLONG_NOTIFY 控制。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/ssl.py</code></td><td><code>CF_API_TOKEN</code></td><td>是</td><td>格式：单账号令牌，优先于 CF_API_EMAIL 和 CF_API_KEY；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CF_API_EMAIL</code></td><td>是</td><td>格式：单账号邮箱；无需与令牌同时填写；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CF_API_KEY</code></td><td>是</td><td>格式：单账号全局密钥；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CF_ZONE_IDS</code></td><td>否</td><td>格式：逗号分隔32位十六进制标识，与 CF_DOMAINS 顺序对应；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CF_DOMAINS</code></td><td>否</td><td>格式：逗号分隔主域名，与 CF_ZONE_IDS 顺序对应；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SSL_WARNING_DAYS</code></td><td>否</td><td>格式：非负整数；警告证书通过验证则检查成功，过期或检查失败返回非零；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SSL_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用，默认关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知目录；不影响独立业务运行，通知失败不更改业务退出码；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_33agilestudio.js</code></td><td><code>AGILE_STUDIO_DRY_RUN</code></td><td>否</td><td>格式：1 为断网预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；预演始终只生成摘要，不联网投递。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录路径，仅用于可选通知，业务无此依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_allgirls.js</code></td><td><code>ALL_GIRLS_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其余值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录绝对路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/sudojia_amx.js</code></td><td><code>AMX_DRY_RUN</code></td><td>否</td><td>格式：1 为预演；其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 禁用，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机目录路径，不下载或安装通知模块。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="36"><code>scripts/sudojia_authcheck.js</code></td><td><code>ALL_GIRLS_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AMX_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BW_TEA_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>FN_NAS_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>GYJ_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HGF_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HLZJ_UNID</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>HZHFP_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>INSTAX_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JINDIAN_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KOZBS_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KTGZS_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>KURO_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LAOBAN_OPENID</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>LONG_FOR_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MALLCOO_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAWUW_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MIDEA_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MOTO_TOKEN</code></td><td>是</td><td>格式：token#uid，只在首个 # 分割；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>NFHK_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PANG_GE_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PPX_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SHUI_FEI_COOKIE</code></td><td>是</td><td>格式：Cookie#memberId，只在首个 # 分割；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TEBU_JSON</code></td><td>是</td><td>格式：一行一个认证请求头 JSON 对象；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIE_BA_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>V2EX_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XPFARM_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZNDS_COOKIE</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZX_ICE_TOKEN</code></td><td>是</td><td>格式：每行一个账号的完整凭据，不使用 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ENABLE_CHECK_TOKEN</code></td><td>否</td><td>格式：true 开启；默认关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTH_CHECK_DRY_RUN</code></td><td>否</td><td>格式：1 为断网预演；默认关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>AUTH_CHECK_ALLOW_MUTATIONS</code></td><td>否</td><td>格式：true 显式允许；默认关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：含 sendNotify.js 的本地目录；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="11"><code>scripts/sudojia_jlc_yj.js</code></td><td><code>OSHW_COOKIE</code></td><td>是</td><td>格式：每行一个完整 Cookie；仅在 JLC_COOKIE 未设置时使用；忽略以 # 开头的注释行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_TOKEN</code></td><td>是</td><td>格式：令牌#密钥，每行一个账号；只在第一个 # 切分，保留密钥后续字符；不以 &amp; 或 @ 分隔账号；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_TASKS</code></td><td>否</td><td>格式：oshwhub、mapp 或 all，两套流程凭据独立；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_CLAIM_REWARD</code></td><td>否</td><td>格式：0 或 1；未授权待选奖励则任务未完成并非零退出；领取后最多补签一次；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：true 或 false；已签到不等待；预演不等待；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 1800 的整数秒，仅启用延迟时校验；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_YJ_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>JLC_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>OSHW_DRY_RUN</code></td><td>否</td><td>格式：1 为完全断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，不区分大小写；其他值开启；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录；通知失败不改变业务退出码；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="4"><code>scripts/sudojia_v2ex.js</code></td><td><code>V2EX_PROXY</code></td><td>是</td><td>格式：HTTP/HTTPS URL，可含代理认证；账号 JSON 的 proxy 优先于全局值，显式空字符串表示直连。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>V2EX_DRY_RUN</code></td><td>否</td><td>格式：1 为预演，其他值为正式运行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭通知，大小写不敏感。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径，仅用于通知，不影响独立 HTTP 业务。；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="9"><code>scripts/sudojia_xinxi.js</code></td><td><code>xx_sso</code></td><td>是</td><td>格式：每个非空行一个完整 sso；旧 # 分隔需迁移为换行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_DRY_RUN</code></td><td>否</td><td>格式：0 或 1，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_FREE_DRAW</code></td><td>否</td><td>格式：0 或 1，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_REWARD_TASKS</code></td><td>否</td><td>格式：0 或 1，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_DAILY_TASKS</code></td><td>否</td><td>格式：0 或 1，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>XINXI_MEMBER_BENEFITS</code></td><td>否</td><td>格式：0 或 1，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>xx_del_topic</code></td><td>否</td><td>格式：移除该变量或设为 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地通知模块目录路径。；多账号格式以该脚本文档为准</td></tr>
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
<tr><td rowspan="6"><code>scripts/supertopicsign.py</code></td><td><code>ROW_URL</code></td><td>是</td><td>格式：与规范变量相同，每行一个账号；原分号账号格式需要改为换行；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>IS_SORT</code></td><td>否</td><td>格式：NONE、INCREASE（等级升序）或 DECREASE（等级降序）；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SIGN_ONCE_COUNT</code></td><td>否</td><td>格式：非负整数，默认 0 表示不限；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WEIBO_SUPERTOPIC_DRY_RUN</code></td><td>否</td><td>格式：默认 0；0、false、no、off 为关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 为关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/synspoint.py</code></td><td><code>SYNSPOINT_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1/0、true/false、yes/no、on/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SYNSPOINT_APPOINTMENT</code></td><td>否</td><td>格式：默认 0；1/0、true/false、yes/no、on/off；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SYNSPOINT_ACTIVITY_ID</code></td><td>否</td><td>格式：正整数；沿用原始活动默认值 818，旧活动可能已失效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SYNSPOINT_GOODS_ID</code></td><td>否</td><td>格式：正整数；可选，不影响默认关闭预约。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；断网预演只模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，不作为业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/tencent_video_checkin.py</code></td><td><code>TENCENT_VIDEO_COOKIE</code></td><td>是</td><td>格式：完整 Cookie；也按每行一个账号解析。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TENCENT_VIDEO_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启预演，默认实际执行。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：已有通知模块的目录路径；业务运行不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：单个推送令牌，与账号 Cookie 分开配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SENDKEY</code></td><td>是</td><td>格式：单个 SendKey，与账号 Cookie 分开配置。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/tieba_checkin.py</code></td><td><code>TIE_BA_COOKIE</code></td><td>是</td><td>格式：每个非空行一个完整 Cookie 或 BDUSS 单值；成长任务需包含 BDUSS 与 CUID。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_GROWTH_TASKS</code></td><td>否</td><td>格式：1、true、yes、on 开启，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_VERBOSE</code></td><td>否</td><td>格式：1、true、yes、on 开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DELAY_MS</code></td><td>否</td><td>格式：整数毫秒；限制在 500 至 10000；格式错误沿用默认值。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，其他值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；仅作为可选通知组件位置，业务功能不依赖此文件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="13"><code>scripts/tjd_daily.py</code></td><td><code>TJD_TOKEN</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_DEVICEID</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_UID</code></td><td>否</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_NAME</code></td><td>否</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_PHONE</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_PASSWORD</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_OPENUDID</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_VENDORID</code></td><td>是</td><td>格式：每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 &amp; 分隔。缺少 deviceid 时该账号失败。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_TASKS</code></td><td>否</td><td>格式：逗号分隔 signin、gamesign、browse、like、share、status；默认 signin,gamesign,browse；--only 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_SHARE_PLATFORM</code></td><td>否</td><td>格式：qq、wechat、timeline 或 wb；默认 qq，不发布文字。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TJD_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 禁用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，通知失败保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="54"><code>scripts/trae_checkin.py</code></td><td><code>TRAE_ACCESS_TOKEN</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_2</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_2</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_3</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_3</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_4</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_4</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_5</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_5</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_6</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_6</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_7</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_7</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_8</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_8</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ACCESS_TOKEN_9</code></td><td>是</td><td>格式：单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_REFRESH_TOKEN_9</code></td><td>是</td><td>格式：单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_SESSION</code></td><td>是</td><td>格式：每行一个账号的单个 Cookie Value；与 TRAE_SESSIONID 行数相同且同账号对应，不填整个 Cookie 请求头。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_SESSIONID</code></td><td>是</td><td>格式：每行一个账号的长效 Cookie Value；与 TRAE_SESSION 同行配对，不填请求头。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_ID</code></td><td>是</td><td>格式：真实 12 至 20 位数字；单账号无后缀，多账号兼容 _2 至 _9 与令牌对应，禁止生成或共享其他账号设备。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_UID</code></td><td>否</td><td>格式：单个公开用户编号；兼容 _2 至 _9 的账号后缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_NAME</code></td><td>否</td><td>格式：单个名称；兼容 _2 至 _9 的账号后缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ICUBE_AUTH</code></td><td>是</td><td>格式：单账号明文 JSON 或原始加密值；加密值需要公共包 cryptography。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_STORAGE_PATH</code></td><td>是</td><td>格式：单个文件路径；仅读取，不改写源文件；预演禁止读取。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_AUTH_DIR</code></td><td>是</td><td>格式：目录路径；签到只有显式设置时读取；login 默认脚本目录 auths；预演禁止读取。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_KEY_PEM</code></td><td>是</td><td>格式：PEM 字符串，支持字面量换行转义；与公钥及设备号配套。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_PUB_PEM</code></td><td>是</td><td>格式：PEM 字符串；须与私钥配套，不能仅设置一个。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_MACHINE_ID</code></td><td>是</td><td>格式：单个设备绑定标识；显式 login 未设置时为本次授权生成，不输出。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_BRAND</code></td><td>否</td><td>格式：单个字符串；未设置保留维护版本自动探测及空值行为。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_NAME</code></td><td>是</td><td>格式：单个字符串；未设置保留维护版本自动探测及空值行为。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DEVICE_MODEL</code></td><td>是</td><td>格式：单个字符串；未设置保留维护版本自动探测及空值行为。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_CLIENT_ID</code></td><td>否</td><td>格式：字符串；默认 ono9krqynydwx5，保留 IDE_PC、SOLO_PC 与旧客户端回退。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_TASK</code></td><td>否</td><td>格式：checkin 默认签到和余额；credits 仅查询余额；login 显式交互登录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_LOGIN_TIMEOUT</code></td><td>否</td><td>格式：30 至 900 的整数秒，默认 300。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_DRY_RUN</code></td><td>否</td><td>格式：默认 0；0、false、no、off 为正式模式，1 为完全断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_ONLY</code></td><td>否</td><td>格式：账号原始序号、uid 或 name；无匹配时报错，默认全部。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_BATCH</code></td><td>否</td><td>格式：默认 all；0 或 all 为全签，正整数为按北京时间小时轮签；早窗仍全签。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_PEAK_HOURS</code></td><td>否</td><td>格式：默认 0；逗号分隔小时或范围，如 0-2；仅用于小时配置，不用于账号分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_COOLDOWN_MIN</code></td><td>否</td><td>格式：1 至 1440 的整数分钟，默认 55。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_PEAK_COOLDOWN_MIN</code></td><td>否</td><td>格式：1 至 1440 的整数分钟，默认 12。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CLAIM_TRIES</code></td><td>否</td><td>格式：1 至 5 的整数，默认 1；不轮换设备。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_CIRCUIT</code></td><td>否</td><td>格式：默认 0；1 为某账号限流后跳过其余未处理账号，未完成仍非零退出。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_JITTER</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_JITTER_MAX</code></td><td>否</td><td>格式：0 至 86400 的整数秒，默认 20；设 600 可使用上游原错峰上限；预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：维护默认 false；0、false、no、off 关闭，其他值启用；预演不等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0 至 86400 的整数秒，默认 3600；未启用时不增加等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_TOKEN_CACHE</code></td><td>是</td><td>格式：文件路径；默认脚本目录 .trae_token_cache.json；以 0600 权限原子保存轮换凭据和官方公开 UID，预演不读写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TRAE_STATE_FILE</code></td><td>否</td><td>格式：文件路径；默认脚本目录 .trae_checkin_state.json；北京时间每日状态，0600 原子写入，预演不读写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，通知失败不改变业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：目录路径；也自动查找 /ql/data/scripts、/ql/scripts 或导入 notify；预演仅提交本地摘要并阻止网络投递。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QYWX_TOKEN</code></td><td>是</td><td>格式：机器人 key 或官方 webhook；只向固定官方主机发送脱敏摘要，预演不发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECHAT_WEBHOOK</code></td><td>是</td><td>格式：含 key 的官方 webhook 或 key；QYWX_TOKEN 优先，预演不发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PLUSPLUS_TOKEN</code></td><td>是</td><td>格式：单个令牌；仅发送脱敏汇总，预演不发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/tsthb_checkin.py</code></td><td><code>TSTHB_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 表示启用。预演不执行等待、HTTP 或通知模块，仅展示通知摘要。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：忽略大小写，只有 true 启用随机延迟，其他值关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：非负整数，单位秒；随机延迟开启时在 0 至该值之间随机选择并显示倒计时。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，忽略大小写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；不会下载安装通知组件。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/ty_netdisk_checkin.py</code></td><td><code>TY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on启用；默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TY_DRAW_SIGNIN</code></td><td>否</td><td>格式：1、true、yes、on启用；0、false、no、off关闭；默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TY_DRAW_PHOTOS</code></td><td>否</td><td>格式：1、true、yes、on启用；0、false、no、off关闭；默认0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>RANDOM_SIGNIN</code></td><td>否</td><td>格式：仅true启用；默认true；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>MAX_RANDOM_DELAY</code></td><td>否</td><td>格式：0～86400的整数；默认3600；断网预演不等待；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TY_ACCOUNT_TIMEOUT</code></td><td>否</td><td>格式：10～600的整数；默认60；需要Python 3.9及以上的青龙Linux或其他支持信号计时器的系统；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭；断网预演只生成通知摘要、不传输；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录路径；通知模块不可用或失败不改变业务退出码；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/tyqhdraw.py</code></td><td><code>TYQH_DRAW_ENABLE</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TYQH_DRAW_LIMIT</code></td><td>否</td><td>格式：1 至 10 的整数；默认 10；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TYQH_DRY_RUN</code></td><td>否</td><td>格式：0 或 1；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭，不区分大小写；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ocr_url</code></td><td>否</td><td>格式：已废弃，设置后也不使用；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="6"><code>scripts/valorantstore.py</code></td><td><code>VALORANT_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭；其他非空值开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TG_BOT_TOKEN</code></td><td>是</td><td>格式：机器人令牌；仅向 Telegram 官方 HTTPS 接口发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TG_USER_ID</code></td><td>是</td><td>格式：十进制聊天编号，群组编号可为负数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VALORANT_FONT_PATH</code></td><td>否</td><td>格式：可读本地字体文件路径；不是必需文件，不依赖固定私有路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="32"><code>scripts/vortexa_free_claim.js</code></td><td><code>VORTEXA_LOGIN</code></td><td>是</td><td>格式：旧格式每行 账号@密码；用户名在第一个 @ 分割，邮箱在完整邮箱后的 @ 分割，密码剩余内容完整保留。推荐规范 JSON。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_ACCOUNT_PASSWORD</code></td><td>是</td><td>格式：同 VORTEXA_LOGIN；两者同时设置时优先 VORTEXA_LOGIN。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_ACCOUNT</code></td><td>是</td><td>格式：每个非空行一个账号，配套 VORTEXA_PASSWORD，非空旧凭据变量行数必须相同。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_EMAIL</code></td><td>是</td><td>格式：每行一个邮箱，配套 VORTEXA_PASSWORD；优先级 ACCOUNT、EMAIL、USERNAME。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_USERNAME</code></td><td>是</td><td>格式：每行一个用户名，配套 VORTEXA_PASSWORD。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_PASSWORD</code></td><td>是</td><td>格式：每个非空行一个密码，不能含换行；需要包含换行的凭据不支持。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_TOKEN</code></td><td>是</td><td>格式：每行一个访问 Token，不含 Bearer 前缀。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_ACCESS_TOKEN</code></td><td>是</td><td>格式：同 VORTEXA_TOKEN；优先使用 VORTEXA_TOKEN。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_COOKIE</code></td><td>是</td><td>格式：每行一个账号完整 Cookie，不含请求头名称。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_REFRESH</code></td><td>是</td><td>格式：每行一个刷新凭据；仅未提供完整 Cookie 时组装为 openbot_refresh Cookie。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_FINGERPRINT</code></td><td>是</td><td>格式：单行文本；默认每个账号独立随机生成。规范账号对象内字段优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_USER_AGENT</code></td><td>否</td><td>格式：单行文本；规范账号对象内 userAgent 优先。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_LOGIN_FIELD</code></td><td>否</td><td>格式：可选字母开头的字母、数字、下划线字段，不能是 password；默认邮箱使用 email，其余使用 username。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_API_BASE</code></td><td>否</td><td>格式：默认 https://api.vortexa.cloud/api；只允许 HTTPS，无 URL 凭据、查询串或片段。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_ORIGIN</code></td><td>否</td><td>格式：默认 https://www.vortexa.cloud；只允许 HTTPS。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_REFERER</code></td><td>否</td><td>格式：默认 https://www.vortexa.cloud/free-hosting；只允许 HTTPS。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_PRODUCT_ID</code></td><td>否</td><td>格式：产品 ID；指定值不存在就失败，不自动更换产品；即使同时提供套餐 ID 也须核验免费。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_PLAN_ID</code></td><td>否</td><td>格式：免费套餐 ID；必须属于所选产品，且 type 为 free 或明确价格为零。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_PRODUCT_SLUG</code></td><td>否</td><td>格式：不区分大小写精确匹配；优先级低于产品 ID。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_PRODUCT_NAME</code></td><td>否</td><td>格式：不区分大小写子串匹配，如 node；优先级低于 ID、slug；无选择参数时保留首个免费产品默认选择。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_LIST_PRODUCTS</code></td><td>否</td><td>格式：1/true/yes/on 开启；默认关闭；优先于领取和循环模式，账号凭据仍必须符合契约但不发送到产品接口。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_CLAIM</code></td><td>否</td><td>格式：1/true/yes/on 开启；默认关闭，只读取主机、库存、免费套餐；不直接领取付费套餐。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_LOOP</code></td><td>否</td><td>格式：1/true/yes/on 开启；默认关闭；在领取模式下最多扫描 VORTEXA_MAX_SCANS 次，已有主机或领取核验完成即停止。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_MAX_SCANS</code></td><td>否</td><td>格式：1 至 30 的整数；循环默认 3 次，未开启循环只扫描一次；建议执行时间小于十分钟定时间隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_TIMEOUT_MS</code></td><td>否</td><td>格式：1000 至 120000 的整数毫秒；默认 30000，覆盖完整请求时长。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_CONFIRM_DELAY_SECONDS</code></td><td>否</td><td>格式：0 至 120 的整数秒；默认 5；领取后等待再确认官方状态，未确认则失败且不重复提交。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_INTERVAL_SECONDS</code></td><td>否</td><td>格式：1 至 300 的整数秒；旧最小间隔别名，默认 30。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_INTERVAL_MIN_SECONDS</code></td><td>否</td><td>格式：1 至 300 的整数秒；默认采用 INTERVAL_SECONDS 或 30。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_INTERVAL_MAX_SECONDS</code></td><td>否</td><td>格式：不小于最小间隔且不大于 300 的整数秒；默认最小间隔与 60 中较大者。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>VORTEXA_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启；不访问任何业务网络，不执行领取或登录；通知也受断网保护。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 关闭；其余值尝试通知。通知缺失或失败不影响业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选目录；其次探测 /ql/data/scripts 和 /ql/scripts；不下载辅助文件，不作为业务依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/wangchao.py</code></td><td><code>WANGCHAO_DRY_RUN</code></td><td>否</td><td>格式：默认 0；1/0、true/false、yes/no、on/off。预演不代表真实业务成功。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WANGCHAO_LOTTERY</code></td><td>否</td><td>格式：默认 0；设为 1 时仅在阅读进度和官方资格都通过后抽奖一次，不自动重试。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WANGCHAO_BONUS</code></td><td>否</td><td>格式：默认 0；设为 1 时按接口提供的入口浏览，不重放随机文章阅读或承诺增加次数，不运行诗词答题及红包。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。总结含账号总数、成功数、失败数及预演状态。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本地目录路径；用于通知，不参与业务请求。通知不可用、失败或超时均保留业务退出码。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/wentiweilaihui.py</code></td><td><code>WENTIWEILAIHUI_DRY_RUN</code></td><td>否</td><td>格式：1 开启完全离线预演；0、false、no、off 关闭，默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 禁用，其余值启用；预演仅模拟通知，保证完全断网。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 或 sendNotify.js 的本地目录，不用于业务接口或凭据配置；JavaScript 通知仅在已有 Node.js 时可用。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/workbuddy.py</code></td><td><code>WORKBUDDY_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 开启；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_JITTER_MAX</code></td><td>否</td><td>格式：0～3600 的整数秒；默认 600，0 关闭。正式运行账号间保留 5～10 秒等待。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_TIMEOUT</code></td><td>否</td><td>格式：1～120 的整数秒；默认 30。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。断网预演仅模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选本机目录路径，仅用于通知，不用于业务 HTTP。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="14"><code>scripts/workbuddy_daily.py</code></td><td><code>WORKBUDDY_TOKEN</code></td><td>是</td><td>格式：国际版单个 AT；规范变量非空时忽略。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_TASKS</code></td><td>否</td><td>格式：任务名逗号或空格分隔：checkin、claim、travel、buddy_info、badges、lottery、blindbox、redeem、gift、makeup、canvas、team_3、apps、theme、library、expert_5、template_5、chat_5、black_cat、Expert_lighthouse、Sequential_Tasks_1 至 Sequential_Tasks_7，兼容对应服务端成长任务代码。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_ONLY_TASKS</code></td><td>否</td><td>格式：与 WORKBUDDY_TASKS 相同；规范变量未定义时生效。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_SKIP_TASKS</code></td><td>否</td><td>格式：同任务白名单格式，逗号或空格分隔。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_ALLOW_REPORT</code></td><td>否</td><td>格式：默认0；仅1开启成长任务模拟上报。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_MP_GAP</code></td><td>否</td><td>格式：默认45，单位秒，有限非负数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_TOKEN_STORE</code></td><td>是</td><td>格式：私有普通文件路径； --refresh、只有RT或已配置缓存的按需续期会原子写入；断网预演不读写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_INTL_TOKEN_STORE</code></td><td>是</td><td>格式：国际版独立私有普通文件路径；续期需同一行RT；断网预演不读写。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_INTL_KEEPALIVE</code></td><td>否</td><td>格式：默认0；1、true、yes、on开启。独立日报或trial模式不得开启。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_INTL_MODELS</code></td><td>否</td><td>格式：逗号分隔模型名；默认 deepseek-v4.1-flash、hy3、hy4-preview、hy4-preview-f。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_DRY_RUN</code></td><td>否</td><td>格式：默认0；1、true、yes、on启用完全断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WORKBUDDY_INTL_DRY_RUN</code></td><td>否</td><td>格式：默认0；1、true、yes、on开启国际版断网预演。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认1；0、false、no、off关闭；断网预演仅模拟通知。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：含 notify.py 的本地目录；不作为业务运行依赖。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/wps_clock_in.py</code></td><td><code>WPS_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on启用，默认0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off关闭；默认1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地青龙通知模块所在目录，可不填写。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="9"><code>scripts/yht.py</code></td><td><code>YHT_DRY_RUN</code></td><td>否</td><td>格式：1 完全断网预演，0 实跑；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_HELP</code></td><td>否</td><td>格式：1 开启，0 关闭；默认 0；至少两个可取得用户标识的账号；排除自己。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_SIGN</code></td><td>否</td><td>格式：1 开启，0 关闭；默认 0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_PLANT_ACTIVITY_ID</code></td><td>否</td><td>格式：数字字符串；默认 1025694534292430849。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_SIGN_ACTIVITY_ID</code></td><td>否</td><td>格式：数字字符串；默认 992065397145317377；不使用上游未被调用的 dailySignId 属性。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_TIMEOUT</code></td><td>否</td><td>格式：1～60 秒，默认 15。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>YHT_FERTILIZE_LIMIT</code></td><td>否</td><td>格式：1～100 的整数，默认 100；任何未确认成功的响应立即停止施肥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；不是业务必需依赖；预演通知适配器运行于禁网子进程。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/youdao.py</code></td><td><code>YOUDAO_DRY_RUN</code></td><td>否</td><td>格式：1 启用；0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/yyshuijuantime.py</code></td><td><code>YYS_HUIJUAN_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用断网预演；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：可选绝对目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="17"><code>scripts/zcode_cn_daily.py</code></td><td><code>ZCODE_INTL_TOKENS</code></td><td>是</td><td>格式：每行一个账号，格式与 ZCODE_CN_TOKENS 相同。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_REGION</code></td><td>否</td><td>格式：cn（默认）、intl 或 all；all 按国内、国际顺序处理已配置账号。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_PLAN_ID</code></td><td>否</td><td>格式：套餐标识，留空按最高优先级选择，同优先级取首项。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_APP_VERSION</code></td><td>否</td><td>格式：版本字符串，默认 3.14.0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_CAPTCHA_PARAM</code></td><td>是</td><td>格式：仅补齐账号行未提供的验证码，可能短时一次性。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_ACTIVATION</code></td><td>否</td><td>格式：0（默认）或 1；预览和断网预演始终不发送。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_CN_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启全进程预演；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZCODE_INTL_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启全进程预演；默认关闭。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0/false/no/off 禁用。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机通知模块目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>PUSHPLUS_TOKEN</code></td><td>是</td><td>格式：推送令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BARK_URL</code></td><td>是</td><td>格式：完整 HTTPS 推送地址。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>WECOM_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS Webhook 或机器人密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_WEBHOOK</code></td><td>是</td><td>格式：完整 HTTPS Webhook。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>DINGTALK_SECRET</code></td><td>是</td><td>格式：与 Webhook 配套的签名密钥。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_URL</code></td><td>否</td><td>格式：HTTPS 青龙地址，不带末尾斜线。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QL_TOKEN</code></td><td>是</td><td>格式：与 QL_URL 配套的通知令牌。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="7"><code>scripts/zippo.py</code></td><td><code>ZIPPO_TASKS</code></td><td>否</td><td>格式：逗号分隔 points,sign,goods,favorite,unfavorite,share,comment,invite；默认 points,sign；unfavorite 必须同时选择 favorite。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZIPPO_COMMENT_STAR</code></td><td>否</td><td>格式：1至5的整数。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZIPPO_COMMENT_TAG</code></td><td>否</td><td>格式：一个完整标签，必须与官方候选完全一致；仅提交标签，不发布自由文本。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZIPPO_INTRODUCER</code></td><td>是</td><td>格式：单个推荐码，不从远程获取；回显不足时报告失败并提示人工核对。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZIPPO_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用，默认0。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：0、false、no、off 关闭，默认1。；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径，仅用于通知适配器；业务运行不依赖此目录。；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="5"><code>scripts/zodgame_test.py</code></td><td><code>ZODGAME_TASKS</code></td><td>否</td><td>格式：all（默认）、sign（仅签到）、bux（仅广告及余额）；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZODGAME_DRY_RUN</code></td><td>否</td><td>格式：1、true、yes、on 启用；默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ZODGAME_DEBUG</code></td><td>否</td><td>格式：兼容旧版 0 或 1，不再开启原始响应输出；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：默认 1；0、false、no、off 关闭；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本机青龙通知模块所在目录；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

- `scripts/139_yunduo.py`：每个非空行一个手机号与配套授权凭据，格式为手机号|授权值；仅在第一个竖线处分割。空行及以井号开头的注释行忽略，错误行计为账号失败。逐账号独立执行，任一账号失败时整体非零退出。。
- `scripts/2cycdx.py`：每个非空行一个账号；使用完整 Cookie，不拆分行内字符。逐个独立执行，任一账号失败则整体非零退出。。
- `scripts/51cto_sign.js`：每个非空行一个账号，配套用户名和密码合并；独立处理，任一账号失败则整体非零退出。。
- `scripts/999.py`：每个非空行一个 JSON 账号对象，手机号和令牌须属于同一账号。账号按行独立处理，任一账号配置或业务失败则整体非零退出。。
- `scripts/acfun.py`：每个非空行一个 手机号|密码；仅拆分第一个 |，逐账号独立登录和执行任务；任一账号失败则整个进程非零退出。。
- `scripts/agentrouter.py`：每个非空行一个账号；每行可为独立 GitHub user_session 值或包含 github_session 的 JSON 对象，配套账号配置在同一对象中；账号独立处理，任一失败整体非零退出。。
- `scripts/airport.py`：SUYING_ACCOUNTS 每个非空行一个账号，以第一个 | 分隔同一账号的邮箱和密码。逐账号独立处理，任一账号配置、登录、签到或流量查询失败时整体非零退出。旧版参数支持单账号。。
- `scripts/akile_checkin.py`：每个非空行一个账号的原始 JWT，顺序独立处理，任一失败或未确认则整体非零退出；配套青龙应用凭证为共享管理配置。。
- `scripts/aliyundrive_checkin.js`：refreshToken 每个非空行一个账号；账号顺序独立执行，任一账号失败则进程非零退出。。
- `scripts/aliyunpan_checkin.py`：每个非空行一个账号；ALIYUN_REFRESH_TOKEN 为规范变量，未设置时兼容 refreshToken；账号独立执行，任一账号失败则整体非零退出。。
- `scripts/aolaxing.py`：每个非空行对应一个账号，整行保留；逐账号独立处理，任何账号失败则整体非零退出。兼容变量 AOLAXING 使用原 JSON 数组。。
- `scripts/atxyq.py`：atxyqs 每个非空行一个账号，配套 Authorization 与 Uid 用第一个 # 拆分；后续字段不再次拆分。各账号独立执行，任一账号失败整体非零退出；不再使用 @ 分隔账号。。
- `scripts/auto_buy.py`：每个非空行一个账号，独立执行；商城配套凭据仅按首个 | 分割，积分配套凭据使用单行 JSON；任一账号失败整体非零退出。两种模式凭据不混用。。
- `scripts/autoclaw_cn_daily.py`：每个非空行一个账号，同账号配套凭据合并在对应地区的一个变量内，推荐 JSON。账号独立执行，任一账号失败或所选地区缺少配置时整体非零退出。--only N 选择所选地区列表中的第 N 个账号；both 时先国内后国际。。
- `scripts/autosignin.js`：每个非空行一个账号的刷新令牌，规范变量优先于旧变量。账号独立执行；账号或奖励失败继续处理其他账号及奖励，但整体非零退出。。
- `scripts/autosignin.py`：E_COOKIE 每个非空行一个账号；同一行保留该账号所有 Cookie 字段。账号独立处理，任一账号失败时整体非零退出。。
- `scripts/baidu.py`：BAIDU 每个非空行对应一个站点账号 JSON 对象，同一站点的清单地址、含令牌提交地址和次数合并在此对象中。各账号独立处理，任一账号失败整体非零退出。。
- `scripts/baiduwangpan_checkin.py`：BAIDU_COOKIE 中每个非空行是一个独立账号；依次处理，任一账号失败时进程整体非零退出。。
- `scripts/baiduwp.py`：BAIDUWP_COOKIE 每个非空行为一个账号，各账号独立执行；任一账号或子任务失败均整体非零退出。。
- `scripts/bilibili.py`：BILIBILI_COOKIE 每个非空行一个账号，同一账号的 SESSDATA、bili_jct 和其他字段合并在该行。逐账号独立处理，任一账号失败整体非零退出。。
- `scripts/bsly_draw.py`：每个非空行一个账号，保留旧 token#User-Agent#备注字段。账号独立执行，任一账号失败整体非零退出。。
- `scripts/bugutv.py`：BUGUTV_ACCOUNTS每个非空行一个用户名|密码，各账号使用独立Cookie会话顺序运行；一账号失败不阻断其他账号，任一账号失败整体非零退出。。
- `scripts/bwcj.py`：每个非空行一个账号；同账号 Token 与可选 customerId 使用首个 | 分割。各账号独立处理，任一失败整体非零退出。。
- `scripts/caigamer.js`：每个非空行一个账号，完整保留 Cookie；顺序独立执行所有账号，任一配置或业务失败均非零退出。。
- `scripts/cdrail.py`：每个非空行一个账号，同一账号的配套凭据集中在该行；各账号独立处理，任一账号失败整体非零退出。。
- `scripts/cfmoto_checkin.py`：CFMOTO_COOKIE 每行一个账号。
- `scripts/chevrolet.js`：每个非空行代表一个账号，按顺序独立签到；行首尾空白去除，行内所有字符保留。任一账号失败整体非零退出，其他账号继续执行。。
- `scripts/ck_2nzz.py`：NZZ_COOKIE 每个非空行一个账号；空行忽略，独立处理所有账号，任一账号失败则进程非零退出。。
- `scripts/ck_acfun.py`：每个非空行一个账号，手机号与密码在同一行，只在第一个 | 分割；逐账号独立处理，任一账号失败则整体非零退出。兼容 ACFUN 的旧 JSON 账号数组。。
- `scripts/codearts_daily.py`：每个非空行一个账号，JSON 必须为单行；不按 & 或 @ 拆分账号。账号独立执行，无效账号计失败，任一失败整体非零退出。。
- `scripts/comicai_ai_cookie.py`：每个非空行一个账号 JSON 对象，同账号 Token 和可选 Cookie 放在同一对象内；账号独立执行，任一账号失败整体非零退出。兼容变量按非空行对应，不允许 & 或 @ 分隔账号。。
- `scripts/crealitycloud_checkin.py`：每个非空非注释行一个账号；同一行以首个空白字段分隔账号与密码，保留密码后续文本。各账号独立处理，格式错误计为失败，任一账号失败则整体非零退出。。
- `scripts/dachao.py`：每个非空行一个账号 JSON 对象，配套凭据置于同一对象，独立校验和执行；任何账号配置或业务失败时整体非零退出。。
- `scripts/daily_benefits.py`：每个非空行一个账号；Cookie 和同账号 user_id 合并在 WPS_ACCOUNTS 的一行，只在首个 | 分割。JSON 每行一个对象也可用。账号相互独立，任一账号或启用任务失败则整体非零退出。。
- `scripts/ddnsto.py`：每个非空行一个账号，使用 路由器ID|完整Cookie，仅按首个 | 拆分；各账号独立执行，任一账号失败整体非零退出。兼容旧变量仅支持单账号。。
- `scripts/deepflood_checkin.py`：每个非空行填写一个账号完整 Cookie；忽略空行并兼容换行格式，各账号独立执行，任一账号签到或收益查询失败则整体非零退出。。
- `scripts/durex.py`：每个非空行一个账号的 Access-Token；各账号独立处理；任何账号失败则整体非零退出。。
- `scripts/enshan_checkin.py`：每个非空行一个账号的完整 Cookie，账号独立执行；任一账号失败整体非零退出。。
- `scripts/epicfreegames.py`：每个非空行配置一个 Telegram 通知账号，格式为机器人令牌|会话编号；仅按首个 | 分割。逐账号独立发送，任一账号失败则整体非零退出。Epic 公开商品查询不需要商店登录凭据。。
- `scripts/erke.py`：每个非空行一个账号 JSON，同账号五项凭据组合在同一对象；逐账号、逐阶段独立处理，任一账号或配置失败时整体非零退出。。
- `scripts/f1owkang_qingskyland_skyland.py`：每个非空行一个账号，完整 token 或官方 JSON；环境变量与可选文件合并按解析后的 token 去重。各账号独立处理，角色失败继续处理其他角色和账号；任意账号失败均非零退出。。
- `scripts/fnnasclub.py`：每个非空行填写一个账号的完整 Cookie，各账号独立执行；任何账号失败均整体非零退出。。
- `scripts/forum_download.py`：每个非空行一个账号 JSON，论坛地址和完整 Cookie 放在同一行；独立执行，任一账号失败则整体非零退出。。
- `scripts/fwxs_checkin.js`：fwxs 每个非空行一个账号；同一账号仅需完整 Cookie。逐账号独立执行，任一账号失败时整体非零退出。昵称备注兼容解析，日志采用账号序号与官方公开 UID，防止备注泄露凭据。。
- `scripts/fxh.js`：fxhOpenId 每个非空行一个账号，逐个独立执行；任一账号失败整体非零退出，不使用 @ 或 & 分隔。。
- `scripts/hifiti_checkin.py`：HiFiTi_COOKIE 和 HIFIHI_COOKIE 各自每个非空行一个账号，账号独立会话并顺序处理。两者至少一项非空；单个账号失败不阻止其他账号，任一失败整体非零退出。。
- `scripts/hlyl.py`：每个非空行一个账号，Token 与可选备注仅按首个 # 分隔。账号独立处理；任一账号配置、查询或已启用操作失败时整体非零退出。备注不展示。。
- `scripts/hsay.py`：每个非空行一个账号，逐账号独立运行；任何账号失败均非零退出。账号凭据保留完整内容，不按 @ 或 & 拆分。。
- `scripts/huaruntong_wx.py`：每个非空行一个账号，配套参数放在同一行 JSON 对象中；逐账号独立处理，任一账号失败则整体非零退出。。
- `scripts/hykb_gamesign.js`：HYKB_SCOOKIE 每个非空行一个账号，逐账号独立执行；不按 &、@ 或 | 分割。任一账号参数或任务失败，整体退出码为 1，其他账号继续处理。。
- `scripts/ikuuu_checkin.py`：每个非空行一个账号，IKUUU_ACCOUNT 兼容邮箱密码及 cookie: 前缀；IKUUU_COOKIES 作为可选追加输入。账号独立执行，任一账号失败则进程非零退出；全局配置错误退出 2。不得以 & 或 @ 分隔账号。。
- `scripts/imaotai.py`：每个非空行一个 JSON 账号对象；同一账号凭据及定位合并，独立执行；任一账号失败则整体非零退出。。
- `scripts/index.js`：每个非空行表示一个独立账号，按第一个 | 分隔公开 UID 与完整 Cookie；账号顺序处理，任一账号失败使整体非零退出。旧版 config.json 单账号 cookie/output/proxy 继续兼容；代理使用 host、port、protocol 等 axios 代理字段，无默认代理。。
- `scripts/iqiyi_checkin.py`：每个非空行一个账号完整 Cookie；同账号字段以分号分隔且只按第一个等号拆分，不使用 & 或 @ 分隔账号。逐账号独立运行，任一账号失败则整体非零退出。。
- `scripts/jc_checkin.py`：JC_ACCOUNTS 每个非空行一个邮箱|密码，仅按首个 | 分割；密码中的后续 | 和空格保留。所有账号共用 BASE_URL，独立执行；任一账号业务失败整体非零退出。EMAIL/PASSWORD 只兼容单账号。。
- `scripts/jcqd.py`：每个非空行一个账号，登录邮箱|密码，仅按首个 | 分割；各账号和站点独立会话，任一账号失败整体非零退出。旧变量保留单账号兼容。。
- `scripts/jingyiluntan_sign.py`：JYLT_Cookie 每个非空行一个账号，按行独立登录和执行；任一账号失败时进程非零退出。。
- `scripts/jissbon.py`：每个非空行一个账号Access-Token，逐账号独立执行；任一账号失败整体非零退出。。
- `scripts/jyj.py`：每个非空行一个账号，authorization#userid，只分割第一个#；逐账号独立处理，任一失败整体非零退出。。
- `scripts/kgqq.py`：每行一个账号的完整 Cookie，开启音乐奖励时使用 完整Cookie|g_tk_openkey；配套值须属于同一账号。忽略空行，逐个独立处理，任何账号失败则整体非零退出。。
- `scripts/kjwj.py`：每个非空行表示一个账号，仅按首个 # 拆分邮箱和密码；逐账号独立执行，任一账号失败整体返回非零退出码。。
- `scripts/kuaishou_reward_status.py`：KUAISHOU_COOKIE 每个非空行对应一个账号；任一账号失败时任务整体非零退出。
- `scripts/kuku_daily.py`：每个非空行一个账号，账号独立处理；规范输入只在第一个竖线处分割令牌与 Cookie。旧凭据输入可兼容替代规范变量。任一账号格式或业务失败时整体非零退出。。
- `scripts/kurobbs_sign.py`：每个非空行一个账号，社区UID|Token；只分割第一个 |。账号独立执行，任一账号或配置失败时整体非零退出。旧变量仅兼容一个账号。。
- `scripts/l.py`：LINUXDO_COOKIES 每个非空行一个账号；逐个独立校验和处理，任何账号失败均以非零状态退出。。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：每个非空行一个账号，整行作为完整 Cookie；不使用 & 或 @ 分隔账号，账号独立执行，任一账号失败则整体非零退出。。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：NZZ_COOKIE 每个非空行一个账号，各账号独立 Cookie 会话；任一账号配置错误或签到未确认成功，整体以非零退出。。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：每个非空行一个账号的完整 NODESEEK_COOKIE；账号独立处理，任一账号签到或收益查询失败，整体非零退出。。
- `scripts/lizhixu_ql_script_hub_youdao.py`：YOUDAO_COOKIE 每个非空行一个账号；逐个独立处理，任一账号失败或配置无效均以非零退出码结束。。
- `scripts/lobsterai_checkin.py`：一个非空行对应一个账号，使用 LOBSTERAI_TOKEN 合并 UID、AT、RT；支持 uid:AT:RT、uid:AT 和纯 AT。每个账号独立执行，任一账号失败时整体非零退出。。
- `scripts/loomy_daily.py`：每个非空行一个账号；兼容 session 和 备注|session，仅在第一个 | 处分割。独立处理各账号，任一账号失败则整体非零退出。--only N 可选择账号。。
- `scripts/lynkco_qinglong_single.py`：每个非空行一个账号JSON对象，配套刷新令牌和设备标识合并保存；旧变量仅换行按行配对，互不广播，不用&或@分账号；独立处理，任何账号失败整体非零退出。。
- `scripts/mifan_optimized.py`：每个非空行一个账号，使用MIFAN_ACCOUNTS合并用户名和密码；只在第一个竖线分割，不使用分号、&或@分隔账号。账号独立执行，任一账号失败整体非零退出。。
- `scripts/mimotion.py`：每个非空行一个账号，仅在首个 | 分割账号和密码，密码中的其它分隔符保留；上传参数同属该行 JSON 对象。每个账号独立执行，任一失败均非零退出。旧 MIMOTION 数组只作为兼容输入。。
- `scripts/netease_task.py`：每个非空行一个账号的完整 Cookie；同账号 MUSIC_U 与 __csrf 放在同一行，不以 & 或 @ 分隔账号。逐账号独立处理，任一账号失败时整体非零退出。。
- `scripts/nga_checkin.py`：每个非空行一个账号；优先使用 NGA_ACCOUNT；旧版三个变量逐行对应。账号执行互不影响，任一账号失败整体非零退出。。
- `scripts/nodeseek.py`：NS_COOKIE 每个非空行一个账号，逐个独立签到；任意账号失败整体非零退出。。
- `scripts/nodeseek_checkin.py`：NODESEEK_COOKIE 中每个非空行是一个独立账号；逐账号执行，任一失败时进程整体非零退出。
- `scripts/nte.py`：每个非空行一个账号，同账号配套凭据放在一个 JSON 对象中。各账号独立执行；任一账号失败则进程非零退出。。
- `scripts/officeace_daily.py`：每个非空行一个账号，同行包含全部配套凭据。兼容前置备注但不打印。独立处理账号，任一账号失败整体非零退出；--only 序号可选择账号。。
- `scripts/ole.py`：每个非空行一个完整 JSON 账号对象，同一账号凭据合并在一行；逐账号独立执行，任一失败时整体非零退出。。
- `scripts/passnat_checkin.py`：PASSNAT_SK 中每个非空行对应一个账号；账号独立执行，任一账号失败时进程整体返回非零。。
- `scripts/psnine.py`：每个非空行一个账号，psnid 与 shell 同行，仅按首个 | 分割。逐账号独立处理，任一账号失败则进程非零退出。。
- `scripts/pt_sign_v5.js`：每个站点的 PT_SITE_<SITE>_CK 内每个非空行代表该站一个独立账号；Cookie 字段用分号分隔，字段值中的后续等号原样保留；不同站点及账号分别维护 Cookie 罐并独立执行，任一账号或必需配置失败时整体非零退出。。
- `scripts/qoder_airscript.js`：每个非空行一个完整账号 JSON 对象，配套令牌、设备字段和逐账号通知凭据放在同一对象中；禁止用 &、@ 或其他字符分隔账号。各账号和各活动独立执行，任一账号失败时整体非零退出。。
- `scripts/quark_signin.py`：每个非空行一个账号，完整 Cookie 作为一个字段保留；账号独立执行，任一账号失败则进程非零退出。。
- `scripts/raccoon_daily.py`：每个非空行一个账号，令牌或备注|令牌；仅在第一个 | 拆分，保留后续凭据文本，支持 Bearer 前缀。账号和两端奖励独立处理，任一账号失败整体非零退出。。
- `scripts/rainyun.py`：每个非空行一个账号，格式为用户名#密码，仅在第一个 # 处分隔。账号独立使用会话，单账号失败不阻止后续账号；任一账号失败或配置无效时整体非零退出。。
- `scripts/rousi_checkin.js`：每个非空行一个账号；ROUSI_TOKEN 为规范变量，Cookie、小写及编号变量为兼容输入。相同类型的完全相同凭据去重，Token 与 Cookie 无需配对，同一账号只选一种。逐个独立处理，任一账号或读取阶段失败则整体非零退出。禁止使用 & 或 @ 分隔账号。。
- `scripts/sf.py`：每个非空行一个账号 JSON 对象；同账号配套 sign、channel、device_id 放在同一行。各账号独立处理，任一账号失败则整体非零退出。旧配置数组按元素独立处理。。
- `scripts/sfsu_checkin.py`：sfsyUrl 中每个非空行是一个独立账号的完整 URL；逐账号隔离处理，任一账号失败则进程非零退出。。
- `scripts/sgs.py`：每个非空行一个账号 Token，独立处理；任一账号或子任务失败，整体非零退出。。
- `scripts/shuyi.py`：sysxc_auth 每个非空行一个账号，逐个独立处理；任一账号失败则整体非零退出。账号间不能使用 #、& 或 @ 分隔。。
- `scripts/sign_in.py`：每个非空行一个账号 JSON 对象，同一对象组合 Cookie 与 CSRF token；逐个独立执行，任一失败时整体非零退出。旧配置使用账号数组。。
- `scripts/skland_daily.py`：每个非空行一个账号，配套凭据写在同一行 JSON 或 cred:token 中，冒号只拆分一次；保留旧序号和成对账密变量兼容。各账号独立处理，任何账号失败则进程非零退出。。
- `scripts/skland_demo.py`：每个非空行一个账号；同一账号的通行证、手机号、密码、验证码和可选设备标识以单行 JSON 配套保存；各账号独立处理，任一账号失败则整体非零退出。。
- `scripts/skyland.py`：SKYLAND_TOKEN 每个非空行一个账号，忽略空行；账号与角色独立执行，任一失败整体非零退出。。
- `scripts/smzdm_checkin.js`：每个非空行一个账号；配套 sk 与完整 Cookie 合并为 SMZDM_ACCOUNT，仅在首个 | 分割。旧 Cookie 变量逐行兼容，不用 & 或 @ 分隔账号；独立处理所有账号，任一账号失败整体非零退出。。
- `scripts/ssl.py`：SSL_ACCOUNTS 每个非空行一个完整 JSON 账号对象，认证与区域配置放在同一行；逐账号独立处理，任一账号失败整体非零。旧版 CF_* 变量仅兼容一个账号。。
- `scripts/sudojia_33agilestudio.js`：每个非空行一个邮箱#密码，仅第一个 # 为字段分隔符，各账号独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_allgirls.js`：每个非空行一个账号；按行独立处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_amx.js`：每个非空行一个账号的 access-token，按行独立处理；任一账号失败时整体非零退出。。
- `scripts/sudojia_authcheck.js`：每行一个账号。统一变量为一行一个 JSON 对象，配套凭据在同一个 credential 字段中；也兼容原变量按行输入。贴吧同一账号分别检查两种接口，统计按账号检查项计数。。
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
- `scripts/sudojia_jlc_yj.js`：每个非空行一个账号；两套凭据分别独立处理；同账号下单助手令牌和密钥合并，仅在第一个 # 切分；任一账号失败或配置错误整体非零退出。。
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
- `scripts/sudojia_v2ex.js`：一个非空行对应一个账号；逐个独立执行，任一账号参数或业务失败则进程非零退出。同一账号 Cookie 和专属代理可放在同一行 JSON 中。。
- `scripts/sudojia_wnna.js`：每个非空行一个账号，逐账号独立执行；任一账号失败则整体非零退出。。
- `scripts/sudojia_xhn.js`：每个非空行一个完整登录表单，忽略空行；账号独立处理，任一账号失败则整体非零退出。。
- `scripts/sudojia_xiangwan.js`：每个非空行一个手机号#密码；首个 # 后均为密码，不以 & 或 @ 分隔账号。逐账号独立处理，任一账号失败整体非零退出。。
- `scripts/sudojia_xiaomi_community.js`：每个非空行一个账号，完整 Cookie 配套字段属于同一账号；独立执行，任一账号失败时整体非零退出。。
- `scripts/sudojia_xinxi.js`：每个非空行一个账号，按行独立处理；任一账号失败时整体非零退出。XINXI_TOKEN 优先于 xx_sso，不合并两个变量。。
- `scripts/sudojia_xpfarm.js`：每个非空行一个账号，顺序独立执行；任一账号失败时整体非零退出。。
- `scripts/sudojia_znds.js`：每个非空行一个账号，配套认证字段包含在同一完整 Cookie 中，不按 & 或 @ 拆分；账号独立执行，任一失败则整体非零退出。。
- `scripts/sudojia_zxice.js`：每行一个非空账号凭据，按顺序独立运行；任何账号失败均以非零状态退出。。
- `scripts/supertopicsign.py`：每个非空行代表一个账号，依次独立执行；任一账号失败或有未完成签到则整体非零退出。重复昵称不会覆盖账号。。
- `scripts/synspoint.py`：synshd 每个非空行一个账号，移除完整 Bearer 前缀后保留整行凭据；逐账号独立处理，任一账号失败则整体非零退出。。
- `scripts/tencent_video_checkin.py`：每个非空行一个完整账号 Cookie，同账号字段组合在同一行；忽略空行和 # 开头注释。规范变量优先，兼容旧单账号变量；独立处理账号，任一账号或步骤失败整体非零退出。。
- `scripts/tieba_checkin.py`：每个非空行一个账号，整行保留为 Cookie；重复行去重，不按 & 或 @ 拆分。账号独立执行，任一账号失败则进程非零退出。。
- `scripts/tjd_daily.py`：每个非空行一个账号 JSON 对象，同账号凭据组合在一行。兼容旧 JSON 数组和换行对齐的旧变量。各账号独立执行，任一失败整体非零退出。。
- `scripts/trae_checkin.py`：TRAE_ACCOUNTS 每个非空行一个账号 JSON 对象，同账号令牌、Cookie、设备号和证明放在同一对象中；不使用 &、@ 或其他字符分隔账号。兼容旧 JSON 数组及带 _2 至 _9 后缀的旧令牌变量。账号独立处理，任一账号失败、未完成或配置错误时整体非零退出；重复会话单列统计，仍独立核验官方状态和余额。。
- `scripts/tsthb_checkin.py`：每个非空行一个账号，按顺序独立执行；任一账号失败则整体非零退出。。
- `scripts/ty_netdisk_checkin.py`：每个非空行一个账号，用户名与密码用第一个竖线配对；不得用&或@分隔账号。各账号独立执行；任意账号配置或业务失败，整体非零退出。。
- `scripts/tyqhdraw.py`：每个非空行一个账号；同一账号的 thirdId 与 wid 写在同一行，保留原字段顺序。逐账号独立处理，任一账号失败则整体非零退出。。
- `scripts/valorantstore.py`：VALORANT_COOKIE 每个非空行一个完整账号 Cookie，ct 与该账号其他字段合并在同一行；按顺序独立执行，任一账号失败则整体非零退出。。
- `scripts/vortexa_free_claim.js`：每个非空行一个 JSON 账号对象；同一账号的配套凭据放在同一对象。旧变量按非空行对齐，不使用 &、@ 或其他符号分隔账号。逐账号隔离登录与 Cookie；任一账号失败时整体退出码为 1。。
- `scripts/wangchao.py`：每个非空行一个账号，只按第一个 # 切分配套手机号与密码。忽略空行；各账号独立处理，任一账号配置或业务失败则整体非零退出。。
- `scripts/wentiweilaihui.py`：每个非空行一个账号，独立执行签到及积分查询。JSON 对象将配套字段放在同一行，完整保存令牌及 User-Agent。任一账号或子任务失败整体非零退出。。
- `scripts/workbuddy.py`：每个非空行一个独立账号 JSON 对象，配套凭据合并在同一行；逐账号独立运行，任一账号失败则进程非零退出。。
- `scripts/workbuddy_daily.py`：每个非空行一个账号；国内版与国际版分别使用各自的规范凭据变量；配套凭据写在同一行，仅按首字段分隔符逐次切分；禁止使用 &、@ 分隔账号。各账号独立执行，任一账号或子任务失败整体非零退出。。
- `scripts/wps_clock_in.py`：每个非空行一个账号，仅使用wps_sid值；各账号独立执行，任一失败则整体非零退出。。
- `scripts/yht.py`：每个非空行一个账号的完整 qm-user-token；逐账号执行，互助仅限本次配置的其他账号；任何账号业务失败整体非零退出。。
- `scripts/youdao.py`：每个非空行一个账号；同一账号的 Cookie 字段以分号连接，字段仅按首个等号拆分。独立处理账号，任一账号失败则整体非零退出。。
- `scripts/zcode_cn_daily.py`：每行一个账号，JWT、设备和验证码放在同一行；逐字段只在首个竖线处分割，验证码保留余下内容。国内及国际账号分别填写变量，默认国内版，--region intl 选择国际版，--region all 执行已配置区域。--only 按所选区域合并顺序筛选。任一账号或显式激活事件失败则非零退出。。
- `scripts/zippo.py`：每个非空行一个完整 authorization，保留凭据正文；账号独立处理，任一失败则整体非零退出。。
- `scripts/zodgame_test.py`：ZODGAME_COOKIE 每个非空行一个账号，Cookie 内部保留分号和后续等号；逐账号独立会话，任一账号失败整体非零退出。。

## 参数获取方法

### 必选参数获取（重点）

#### `YDYP_ACCOUNTS`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：登录中国移动云盘网页版 https://yun.139.com，打开开发者工具的网络面板，刷新页面，在 api.yun.139.com 或 yun.139.com 请求头中复制 Authorization；手机号使用该登录账号的手机号。凭据仅填入青龙环境变量，不要提交或分享。
- 填写格式：`每个非空行一个账号：手机号|Basic 授权值；也兼容省略 Basic 前缀的完整编码值或原始授权令牌。仅在第一个竖线处分割，后续凭据原样保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `cycd_cookie`

- 所属脚本：`scripts/2cycdx.py`
- 获取或设置：浏览器登录 https://www.2cycdx.com/，按 F12 打开网络面板，刷新页面，选择论坛文档请求，从请求头复制完整 Cookie；每个账号分别登录获取。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留行内分号、等号、& 和 @，不用这些符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ICTO_BLOG_ACCOUNTS`

- 所属脚本：`scripts/51cto_sign.js`
- 获取或设置：在51CTO官网注册或使用已有账号的登录用户名和密码；验证码或额外验证须先人工处理，无需抓取Cookie。
- 填写格式：`每个非空行一个账号，推荐用户名|密码；在首个竖线拆分，后续密码原样保留。兼容不含竖线的用户名@密码，在首个@拆分；邮箱用户名须使用竖线。旧版&多账号配置必须迁移为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HRT999_ACCOUNTS`

- 所属脚本：`scripts/999.py`
- 获取或设置：本人登录华润通999答题页面，使用浏览器开发者工具或本人设备抓包查看 api4.jiankangyouyi.com 的答题请求。取请求头 token 与 customdata 中的 mobile；可选 user_agent 使用同一请求的 User-Agent。仅保存在青龙环境变量中，不分享抓包数据。上游未提供更详细的登录入口或令牌有效期，请以本人实际请求为准。
- 填写格式：`每个非空行为一个完整 JSON 对象；必填 mobile（十一位中国大陆手机号）和 token（非空字符串）；可选 user_agent（无换行字符串）及 account_name（原有账号备注兼容字段，不用于业务验证）。JSON 可无歧义保留凭据中的分隔符。不要用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ACFUN_ACCOUNTS`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：使用本人 AcFun 注册手机号和密码；先在官方客户端确认可正常登录，再录入青龙环境变量。验证码或风控导致登录失败时需本人在官方客户端处理。
- 填写格式：`每个非空行一个账号，格式为 手机号|密码；仅在第一个 | 分割，密码中的后续 | 和首尾空格原样保留。手机号两侧空格忽略；不得使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AGENTROUTER_ACCOUNTS`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：先在浏览器登录 GitHub 并手动完成 AgentRouter 的 GitHub 授权；在开发者工具的 Application/Cookies/github.com 中复制 user_session 值。每行一个账号，也可用 JSON 对象组合该账号配置。
- 填写格式：`每个非空行一个 user_session 值或 JSON 对象；对象必填 github_session，可填 account_name、base_url、user_id、proxy、verify；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SUYING_ACCOUNTS`

- 所属脚本：`scripts/airport.py`
- 获取或设置：从本人速鹰666网站注册或账户资料取得登录邮箱，密码使用本人网站登录密码。在青龙环境变量中填写每行一个账号。旧版单账号可改用 SUYING_USERNAME 与 SUYING_PASSWORD，两项必须同时设置；新变量存在时优先使用新变量。
- 填写格式：`每个非空行：登录邮箱|密码。只按第一个 | 分割，后续密码内容保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AKILE_TOKEN`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：登录 https://akile.ai/console/ak-coin-shop，浏览器开发者工具→应用→本地存储→https://akile.ai，复制 akile-token 原始 JWT。
- 填写格式：`每个非空行一个完整 JWT，包含有效 exp；不加 Bearer，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `refreshToken`

- 所属脚本：`scripts/aliyundrive_checkin.js`
- 获取或设置：登录阿里云盘网页版 https://www.aliyundrive.com/，在浏览器开发者工具控制台读取 JSON.parse(localStorage.token).refresh_token，复制到青龙私密环境变量；不要公开或写入日志。
- 填写格式：`每个非空行填写一个账号的 refresh_token；仅按换行分隔，不支持 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ALIYUN_REFRESH_TOKEN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：登录阿里云盘网页版，在浏览器开发者工具的 Application（应用）→ Local Storage（本地存储）中查看 token 项，仅复制 refresh_token 字段；不要复制完整 JSON 或公开凭据。
- 填写格式：`每个非空行一个账号的刷新令牌；不用 &、@ 或其他符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AOLAXING_COOKIE`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：登录百田网奥拉星积分商城，在浏览器开发者工具网络面板查找 service.100bt.com/creditmall 请求，复制请求头 Cookie 完整值。请勿复制到日志或公开仓库。
- 填写格式：`每行一个账号的完整 Cookie；不按 &、@ 或分号拆分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HAX`

- 所属脚本：`scripts/api_hax.py`
- 获取或设置：无需凭据，手动设置青龙环境变量 HAX=1，替代上游私有配置启用开关。
- 填写格式：`单个非敏感开关；1 启用；0、false、no、off 或空值不启用。未启用报告配置错误并非零退出。`

#### `ARKNIGHTS_STATE_FILE`

- 所属脚本：`scripts/arknightsbanner.py`
- 获取或设置：由用户指定青龙可写的独立 JSON 文件路径，用于公告增量状态。无需游戏账号或登录凭据。沿用上游历史状态时指向原脚本旁 config/.arknights_banner_state.json；新安装选择自己的数据目录。不要指向其他脚本、配置或已有非状态文件。
- 填写格式：`一个本地 JSON 文件路径；首次正式运行自动创建文件和父目录，已有文件需包含数组 known_cids 与 notified_cids。断网预演不读写文件。`

#### `atxyqs`

- 所属脚本：`scripts/atxyq.py`
- 获取或设置：在微信艾特校园圈小程序登录后，抓取自己发往 api.atxz.cool 的请求头 Authorization 与 Uid；失效后重新登录抓取。
- 填写格式：`每个非空行一个账号：Authorization#Uid；仅在第一个 # 拆分，后续文本原样保留；Uid 为数字。旧版 @ 账号分隔必须改为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHYP_BUY_ACCOUNTS`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：仅 buy 模式必填。登录自己的上海杨浦 App，在商城兑换页抓取 mall-api.shmedia.tech/trade-service/trade/carts/buy 请求头 Authorization 和可选 Cookie；不填写请求头名称，不使用积分 token。
- 填写格式：`每个非空行 Authorization|Cookie；Cookie 可省略，仅在第一个 | 处分割；换行区分账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHYP_BUY_SKU_ID`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：仅 buy 模式必填。从自己选择的商品抢购请求查询参数 sku_id 获取，禁止沿用他人的商品编号。
- 填写格式：`数字字符串`

#### `SHYP_BUY_ACTIVITY_ID`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：仅 buy 模式必填。从同一商品请求查询参数 activity_id 获取。
- 填写格式：`数字字符串`

#### `SHYP_POINTS_ACCOUNTS`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：仅 points 模式必填。登录自己的上海杨浦 App，抓取 app.ypmedia.cn/media-basic-port/api/app/personal/score/info 请求头 token、deviceid、siteid；将同一账号 token 与 deviceid 分别填入 token、device_id。可选 site_id 和 user_agent 取自该请求；不读取私有配置文件。
- 填写格式：`每个非空行一个 JSON 对象，必填字符串 token、device_id；可选 site_id（默认 310110）、user_agent（默认 okhttp/4.10.0）；换行区分账号，JSON 保留字段内分隔符`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AUTOCLAW_CN_TOKENS`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：默认国内模式必填。在国内版官方桌面端登录，从自己的登录响应安全提取 access_token、refresh_token 和同次登录的 device_id。只有登录态也可签到，过期后须重新登录。国际模式改用 AUTOCLAW_INTL_TOKENS；两地区凭据不能混用。不要分享或提交登录响应。
- 填写格式：`每个非空行一个账号。推荐 JSON 对象，access 必填，refresh、device_id 可选。兼容 token、token|refresh_token、token|refresh_token|device_id、备注|token|refresh_token|device_id 和旧备注|JWT 格式。逐次只按首个 | 切分，最后字段保留剩余文本；可带 Bearer 前缀。禁止用 &、@ 分隔账号；特殊字符或歧义格式使用 JSON。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ALIYUN_REFRESH_TOKEN`

- 所属脚本：`scripts/autosignin.js`
- 获取或设置：登录自己的阿里云盘网页版，在浏览器开发者工具的应用（Application）→本地存储（Local Storage）中查找登录信息里的 refresh_token，仅复制该字段值并保存到青龙环境变量。失效后重新登录获取，不要复制完整登录对象。
- 填写格式：`每个非空行一个刷新令牌；空行忽略，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `E_COOKIE`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：在浏览器登录 E-Hentai，打开开发者工具的网络面板，访问 https://e-hentai.org/news.php，复制该请求的完整 Cookie 请求头值。至少包含 ipb_member_id 与 ipb_pass_hash；Cookie 失效或服务提示更新时重新获取。不要公开分享。
- 填写格式：`每个非空行一个账号的完整 Cookie；字段用分号分隔，每个字段只按第一个等号拆分，后续等号保留。不要使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDU`

- 所属脚本：`scripts/baidu.py`
- 获取或设置：登录百度搜索资源平台，验证自己拥有的站点，在普通收录的 API 提交页面复制含 site 和 token 的提交地址；使用 HTTPS 的 data.zz.baidu.com/urls 地址。自行托管公开的 UTF-8 URL 文本清单，仅包含该站点 URL。不得公开或记录提交令牌。
- 填写格式：`每个非空行是一个 JSON 对象，必填 data_url（HTTPS 文本清单地址）、submit_url（含唯一 site 和 token 的百度 HTTPS 接口地址），可选 times（1 至 100 的整数，默认 1）。不使用 & 或 @ 分隔账号；接口地址内部的 & 保持原样。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDU_COOKIE`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：登录 https://pan.baidu.com/ 后打开浏览器开发者工具的 Network 面板，刷新页面，选择一个 pan.baidu.com 请求，复制 Request Headers 中完整的 Cookie 值。
- 填写格式：`每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDUWP_COOKIE`

- 所属脚本：`scripts/baiduwp.py`
- 获取或设置：在浏览器登录 https://pan.baidu.com，打开开发者工具网络面板，选择发送到 pan.baidu.com 的已登录请求，复制完整 Cookie 请求头值，不包含 Cookie: 前缀。Cookie 失效时重新登录获取。无需原仓库 config.json。
- 填写格式：`每个非空行为一个账号的完整 Cookie；分号和等号保留，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BILIBILI_COOKIE`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：浏览器登录 Bilibili 后，打开开发者工具网络面板，从发往 api.bilibili.com 的已登录请求复制完整 Cookie 请求头，必须包含 SESSDATA 和 bili_jct；仅保存在青龙环境变量，过期后重新获取。
- 填写格式：`每个非空行一个账号完整 Cookie，字段以分号分隔；仅在第一个等号处分割键值，值内等号保留。不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `bsly`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：在本人授权的微信小程序 wx1a72addb7ee74f67 中捕获百事乐元抽奖请求 https://pepcoinbhhpre.pepcoinbypepsico.com.cn/mp/draw，读取 token 和 User-Agent 请求头；账号备注自行填写。不要分享抓包文件或凭据。
- 填写格式：`每个非空行一个账号：token#User-Agent#账号备注。第一个 # 分隔 token，最后一个 # 分隔备注，中间的 # 保留在 User-Agent 中；备注不可含 #。不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BUGUTV_ACCOUNTS`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：使用本人在 https://www.bugutv.vip 注册并可正常登录的用户名及密码。在青龙环境变量中添加 BUGUTV_ACCOUNTS，无需抓包或修改脚本。不要填写手机号作为用户名。
- 填写格式：`每个非空行一个账号：用户名|密码。只在第一个竖线处分割，密码中的后续竖线和空格保留；用户名不能包含竖线，账号凭据不能包含换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `bwcjCookie`

- 所属脚本：`scripts/bwcj.py`
- 获取或设置：在本人微信霸王茶姬小程序登录后，从本人授权的业务请求头获取 Qm-User-Token；可选 customerId 从积分流水接口 data.data 项获取，仅在流水为空时补充。不要使用手机号或设备标识代替。
- 填写格式：`每个非空行一个 Token，或 Token|customerId；仅在首个 | 分割。同账号配套字段，账号仅用换行分隔，不支持原 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CAIGAMER_COOKIE_LIST`

- 所属脚本：`scripts/caigamer.js`
- 获取或设置：登录 https://caigamer.cn，在浏览器开发者工具的网络面板选择本站已登录请求，复制 Cookie 请求头，需包含 bbs_sid 和 bbs_token。过期后重新登录获取。不要复制响应头或向他人提供凭据。
- 填写格式：`每个非空行一个账号的完整 Cookie，包含非空 bbs_sid 和 bbs_token。同一账号字段用分号分隔，只在第一个等号处拆分，保留值中的后续等号。不用 & 或 @ 分隔账号。`
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

#### `CHEVROLET_ACCOUNTS`

- 所属脚本：`scripts/chevrolet.js`
- 获取或设置：在本人授权设备上使用抓包工具查看雪佛兰 APP 签到请求 https://ctwx.sgmlink.com/api/check/submit 的 cpctoken 请求头，复制值；仅在本地青龙环境变量中保存，不分享抓包或凭据。
- 填写格式：`每个非空行填写一个账号的 cpctoken 原始值，不含请求头名称；不使用 &、@ 或其他字符分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NZZ_COOKIE`

- 所属脚本：`scripts/ck_2nzz.py`
- 获取或设置：在咔叽网单官方网站登录后，打开浏览器开发者工具网络面板，从发往 www.2nzz.com 的已登录请求复制完整 Cookie 请求头值。原框架 check_item.cookie 的原始值可直接迁入；不读取原框架配置文件。
- 填写格式：`每个非空行一个账号；只填写 Cookie 值，不包含 Cookie: 前缀。Cookie 字段使用分号分隔，字段仅按首个等号拆分，后续等号保留；禁止使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ACFUN_ACCOUNTS`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：在 AcFun 官方网站或客户端确认自己的登录手机号和密码，在青龙环境变量中填写；仅用于自己的账号。登录需要验证码时需自行在官方客户端处理，脚本不绕过验证。
- 填写格式：`每个非空行一个账号：手机号|密码。只按第一个 | 分割，密码中的后续 |、&、@ 和空格完整保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CODEARTS_CREDENTIALS`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：在官方 CodeArts 客户端登录后，从自己的登录会话或 HTTPS 登录响应取得临时 access_key_id、secret_access_key、security_token。可选续期材料必须来自同一次授权：refresh_token、PKCE code_verifier、P-256 DPoP 私钥。不要使用其他产品的永久 AK/SK，也不要公开分享凭据；无需外部工具或仓库。
- 填写格式：`每个非空行一个账号：单行 JSON（上述字段，可含 expiration、domain_id、user_name、oauth_context.pkce_pair.code_verifier、oauth_context.dpop_key_pair.private_key_jwk），或 AK|SK|STS；仅前两个 | 分隔字段，后续文本保留。兼容 accessKeyId/secretAccessKey/securityToken 和 ak/sk/sts 别名。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `COMICAI_ACCOUNTS`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：登录 ComicAI 网页，从浏览器开发者工具网络面板读取 api.comicai.ai 请求的 Token 请求头；如需要兼容访问登录页，另取 comicai.ai 请求的 Cookie 请求头。仅保存在本人青龙环境中。
- 填写格式：`每个非空行一个 JSON 对象，token 为必填非空字符串，cookie 为可选字符串；JSON 转义可保留凭据中的分隔符。设置规范变量后不读取旧变量。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CREALITY_ACCOUNTS`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：在创想云国内站 https://www.crealitycloud.cn 注册或登录；使用手机号或邮箱及登录密码，忘记密码通过官方流程重置。无需抓取 Cookie 或 Token。
- 填写格式：`每个非空行一个账号，格式为「手机号或邮箱 空格 密码」；只按第一个空白字段分隔，后续密码文本保留。手机号支持 11 位、86 加 11 位或 +86 加 11 位；邮箱直接填写；以 # 开头的行忽略。兼容脚本内 CONFIG_ACCOUNTS，推荐环境变量。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DACHAO_ACCOUNTS`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：使用本人账号在大潮App登录时抓取 HTTPS 请求。passport.tmuyun.com/web/oauth/credential_auth 表单提供 phone_number、password（填到 password_encrypted）、client_id；请求头提供 User-Agent（填到 user_agent）及可选 Cookie。vapp 登录请求头提供 tenant_id 和登录前 session_id；默认 tenant_id=94、client_id=10048。不要填明文密码，不要分享抓包文件。兑换 member 仅在本人微信领取红包请求中取得，与登录 member 不同。
- 填写格式：`每个非空行是一个完整 JSON 对象，不用 & 或 @ 分隔账号。必填字段 phone_number、password_encrypted、user_agent；兼容 password、user_agent_vapp、user_agent_aihoge。可选字段 account_name、tenant_id、client_id、session_id、passport_cookies、vapp_cookies、aihoge_cookies（兼容 cookies）、passport_signature_salt、aihoge_signature_salt、sign_lottery_id、redeem_member（兼容 withdraw_member）、redeem_cookies、redeem_user_agent。Cookie 和 member 保留原字符串（JSON 内引号须转义）。forum_session_id、forum_cookies、forum_tenant_id 兼容读取但原主任务没有论坛动作。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WPS_ACCOUNTS`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：浏览器登录 WPS 后打开福利中心，在开发者工具 Network 中复制 personal-act.wps.cn 的 page_info 或 component_action 请求 Cookie，包含登录会话及 act_csrf_token 或 csrf。启用任务中心时，从同账号官方响应或签到请求获取数字 user_id。不得复制他人账号数据。
- 填写格式：`每个非空行一个账号；仅福利任务使用完整 Cookie；任务中心使用 user_id|完整 Cookie，仅按第一个 | 分割，保留后续 Cookie 内容。也可每行一个 JSON 对象，包含 cookies 及可选 user_id、user_agent、account_name、max_lottery_limit，兼容原账号字段；不读取私有配置文件。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DAILYNEWSCN_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 dailynewscn 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `OILPRICE_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；手工填写地区名称，原工作表 D 列地区迁入本变量。
- 填写格式：`仅油价模式必填；每个非空行一个中文地区，或一个含 area 字符串的 JSON 对象；旧标记 1 可配合 OILPRICE_AREA；不使用 & 或 @ 分隔。`

#### `DDNSTO_ACCOUNTS`

- 所属脚本：`scripts/ddnsto.py`
- 获取或设置：登录 DDNSTO 官网设备页面，在浏览器开发者工具网络面板复制 www.ddnsto.com 请求的完整 Cookie（含 csrftoken）。先申请一次七天免费套餐，从 /api/user/routers/路由器ID/ 请求路径取路由器ID；该值不是登录用户ID。可用兼容旧变量代替。
- 填写格式：`每个非空行填写 路由器ID|完整Cookie；仅在首个 | 分隔，同一行内 Cookie 原样保留，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DEEPFLOOD_COOKIE`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：登录 https://www.deepflood.com 后打开浏览器开发者工具的网络面板，选择本站已登录请求，复制请求头 Cookie 的完整值；不要复制 Cookie: 前缀，不要公开凭据。
- 填写格式：`每个非空行填写一个账号完整 Cookie；不按 &、@ 或分号拆分账号，Cookie 中的这些字符原样保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `dlshyzx`

- 所属脚本：`scripts/durex.py`
- 获取或设置：在微信杜蕾斯会员中心小程序登录，用本人授权的抓包工具读取 vip.ixiliu.cn 请求头 Access-Token；失效时重新登录获取。
- 填写格式：`每个非空行一个完整令牌；保留变量名；不再使用上游的 # 或其他符号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ENSHAN_COOKIE`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：浏览器登录恩山论坛，在开发者工具的网络面板选取发往 www.right.com.cn 的请求，复制完整 Cookie 请求头值；仅填入青龙私密环境变量，不含 Cookie: 前缀。Cookie 已含账号身份，不再要求上游 EST_USER_UID 或 config.json。
- 填写格式：`每个非空行一个账号的完整 Cookie；同一账号各字段用分号分隔，字段值内的等号保留；不得用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `EPIC_TG_ACCOUNTS`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：通过 Telegram 的 BotFather 创建机器人取得令牌；向机器人发送消息后，从官方 Bot API getUpdates 的 message.chat.id 获取会话编号。令牌和会话编号必须对应可接收消息的同一机器人。
- 填写格式：`每个非空行一个机器人令牌|会话编号；只按首个 | 分割，支持数字会话编号或公开频道用户名。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ERKE_ACCOUNTS`

- 所属脚本：`scripts/erke.py`
- 获取或设置：登录本人鸿星尔克微信小程序，在本人授权的网络调试中查看 https://hope.demogic.com/gic-wx-app/integral_record.json 或 sign/member_sign.json 的请求体，获取 memberId、enterpriseId、unionid、openid、wxOpenid，依次对应 member_id、enterprise_id、unionid、openid、wx_openid。五项必须来自同一账号；不要分享请求体。原 config/token.json 中 erke.accounts 的每个账号对象可复制为一行 JSON，不需要该文件或原仓库。
- 填写格式：`每个非空行为一个 JSON 对象，五项字段均为非空字符串；可选 account_name 和 user_agent，兼容上游字段。account_name 保留输入兼容，日志优先使用官方身份，没有官方身份时用账号序号。JSON 内部文本与标点保留，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKYLAND_TOKENS`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：本人登录 https://www.skland.com/ 后，在同一浏览器打开 https://web-api.skland.com/account/info/hg ，取官方响应 data.content。请只保存自己的凭据，不公开响应。账号需在森空岛绑定游戏角色。
- 填写格式：`每个非空行一个完整鹰角登录 token；也接受每行一个包含 data.content 的官方 JSON。禁止使用逗号、& 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `FNNASCLUB_COOKIE`

- 所属脚本：`scripts/fnnasclub.py`
- 获取或设置：登录 https://club.fnnas.com 后打开浏览器开发者工具的网络面板，复制该站已登录请求中的 Cookie 请求头值。
- 填写格式：`每个非空行为一个账号的完整 Cookie 值，保留分号及等号，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `FORUM_ACCOUNTS`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：登录自己的论坛，在浏览器开发者工具网络面板复制同站请求的完整 Cookie；url 填 HTTPS 根地址，可含安装子目录；下载所需 fid 从版块地址取得。
- 填写格式：`每个非空行一个 JSON 对象，必填 url、cookie，可选 name、fid；不按分号、& 或 @ 拆分 Cookie。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `fwxs`

- 所属脚本：`scripts/fwxs_checkin.js`
- 获取或设置：浏览器登录废文网 https://xn--pxtr7m.net，在开发者工具的网络面板选中本站已登录请求，复制请求头 Cookie 的完整值，不包含 Cookie: 前缀。失效时重新登录获取；不要分享或写入仓库。
- 填写格式：`每个非空行一个账号的完整 Cookie；兼容 Cookie#昵称备注，仅按首个 # 分割，后续备注完整保留但为防泄漏不输出。禁止用 @ 或 & 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `fxhOpenId`

- 所属脚本：`scripts/fxh.js`
- 获取或设置：打开芬享汇微信小程序，用自己的合法抓包工具查看 scrm.ocheng.me/v2/api/member/info 请求的 miniProgramOpenId 参数，或签到请求路径中的 OpenId。仅复制自己的 OpenId，不要复制整条请求、Cookie 或手机号。
- 填写格式：`每个非空行一个 OpenId，允许字母、数字、下划线和短横线；保留上游变量名，不再支持 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YYS_OUTPUT_DIR`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：自行选择本地保存目录；无需登录或凭据。原脚本的固定盘符已移除。
- 填写格式：`一个本地目录路径；预演也必须提供占位目录`

#### `HELLOGITHUB_STATE_FILE`

- 所属脚本：`scripts/hellogithub.py`
- 获取或设置：选择青龙脚本可写的持久化目录，自行指定 JSON 状态文件；迁移时填旧脚本目录/config/.hellogithub_bot_state.json 的绝对路径，以保留已发送期号。公开月刊接口无需账号凭据。
- 填写格式：`单个绝对文件路径；文件不存在时从未发送开始，文件损坏时停止。`

#### `HiFiTi_COOKIE`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：在浏览器登录 https://www.hifiti.com/，打开开发者工具的网络面板，复制该站点已登录请求的完整 Cookie 请求头，不含 Cookie: 前缀。凭据至少配置 HiFiTi_COOKIE 或 HIFIHI_COOKIE 一项；仅运行 HiFiHi 时由 HIFIHI_COOKIE 满足此必需凭据要求。
- 填写格式：`每个非空行一个账号；填写完整 Cookie（字段之间使用分号），兼容旧版仅填写 cloudmusic.net 的值；字段值中的等号完整保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `hlylck`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：在本人授权设备登录活力伊利微信小程序，查看发往 https://msmarket.msx.digitalyili.com 的请求头 access-token；失效后重新登录获取。不要分享凭据。
- 填写格式：`每个非空行一个账号：access-token 或 access-token#备注；仅按首个 # 分隔，后续备注内容保留。不使用 &、@ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `hsayCookie`

- 所属脚本：`scripts/hsay.py`
- 获取或设置：登录自己的沪上阿姨微信小程序，在本地抓包工具中查看 webapi.qmai.cn 请求头 Qm-User-Token 的完整值；过期后重新登录获取。不要填写整段 Cookie 或将凭据公开。可使用上游文档别名 HSAYCookie，优先使用 hsayCookie。
- 填写格式：`每个非空行填写一个完整 Token；账号之间只使用换行，不使用 @ 或 & 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HRT_WX_ACCOUNTS`

- 所属脚本：`scripts/huaruntong_wx.py`
- 获取或设置：登录华润通微信版官方页面，在本人授权的网络调试中查看 mid.huaruntong.cn/api/points/saveQuestionSignin 请求加密前的 token 和业务参数；请求体 key/data 是密文，不能直接当作 token。不得分享抓包内容。失效后重新登录获取。将原配置 huaruntong.huaruntong_wx.accounts 中每个对象复制为单独一行亦可，不读取原私有配置文件。
- 填写格式：`每个非空行一个账号：可直接填写完整 token，也可填写含 token 字段的单行 JSON 对象。JSON 兼容 answerResult（整数，默认 1）、channelId（默认 APP）、merchantCode（默认 1641000001532）、storeCode（默认 qiandaosonjifen）、sysId（默认 T0000001）、transactionUuid 和 inviteCode（默认空字符串）、user_agent（默认原 iPhone 浏览器标识）、account_name。字符串字段使用 JSON 转义；不使用 &、@ 分隔账号，token 内这些字符保留。account_name 兼容输入但日志使用账号序号和官方公开身份。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HYKB_SCOOKIE`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：在自己的好游快爆账号登录后，进入游戏签到活动，使用本地抓包工具读取 https://huodong3.3839.com/n/hykb/signcard/ajax.php 请求表单中的 scookie 值。只在本地青龙环境变量中保存，不提交仓库或分享截图。原脚本 config.hykb.scookie 的值可直接迁入本变量。
- 填写格式：`每个非空行一个账号，只填写 scookie 值，不添加 scookie= 或 Cookie 请求头。支持原始值及已百分号编码的值；内部 |、&、@ 等字符保留，不作为账号分隔符。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IKUUU_ACCOUNT`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：在 iKuuu 官方网站注册或找回邮箱密码；Cookie 模式需先在浏览器登录，在开发者工具 Network 的 /user 请求中复制 Cookie 请求头，包含 uid、email、key。仅在青龙私密环境变量中保存。
- 填写格式：`每行一个账号：邮箱|密码，或 cookie:完整 Cookie；仅在第一个 | 处分割邮箱密码，密码中的后续 | 保留。Cookie 使用分号分隔名称=值，值中的后续 = 保留；禁止用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IMAOTAI_ACCOUNTS`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：在本人 i茅台登录后的请求中获取 MT-Token、userId、MT-Device-ID，分别填入 token、userid、device_id；从本人定位填写省市及经纬度。token 过期时在应用重新登录后重新获取。仅检查本人有权查看的流量，不复制他人凭据。参考登录工具可通过短信登录和高德定位获取参数，但不作为定时任务执行。
- 填写格式：`每个非空行是一个 JSON 对象；必填 token、userid、device_id，userid 支持字符串或整数。申购另需 province、city、lat、lng。item_codes 是数字字符串数组，默认 ["11318","11319"]；reserve_rule 为 0（最近门店）或 1（所在城市库存最多）。mobile 兼容但不使用和输出。禁止用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PIXIV_ACCOUNTS`

- 所属脚本：`scripts/index.js`
- 获取或设置：登录本人 Pixiv 账号，在浏览器开发者工具的网络面板中复制 www.pixiv.net 请求的完整 Cookie；公开 UID 从个人主页网址 /users/ 后获取，也可留空由官方收藏跳转获取。兼容当前工作目录 config.json 的 cookie 字段。
- 填写格式：`每行一个账号：公开UID|完整Cookie；只按第一个 | 拆分，后续 Cookie 内容保留；UID 留空时使用 |完整Cookie。禁止用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IQIYI_COOKIES`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在浏览器登录自己的爱奇艺账号，打开开发者工具的应用或存储面板，查看 https://www.iqiyi.com 的 Cookie。复制 P00001 与 P00003 到同一行；建议同时带上 __dfp，也兼容上游 dfp。勿分享凭据，失效后重新登录获取。
- 填写格式：`每个非空行一个账号，形如 P00001=<登录凭据>; P00003=<用户编号>; __dfp=<设备字段>。分号分隔同账号字段，每个字段仅按第一个等号拆分；保留值中其余等号。设备字段仅使用 @ 前段，@ 不分隔账号。优先使用 __dfp；P00002、QC005 等额外 Cookie 字段允许保留，不单独要求。# 开头的行作为注释。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JC_ACCOUNTS`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：取自本人机场注册邮箱及登录密码；无需抓取 Cookie，仅支持无验证码或二步验证的邮箱密码登录。兼容单账号可使用 EMAIL 与 PASSWORD。
- 填写格式：`每个非空行一个邮箱|密码；仅按首个 | 分割，后续 | 和密码空格保留`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BASE_URL`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：从本人机场面板浏览器地址栏取得最终 HTTPS 根地址；去掉 /auth/login 或 /user，不带凭据、查询参数或片段。重定向被拒绝，需填写最终地址。
- 填写格式：`所有账号共用的 HTTPS 面板根地址，可包含部署子路径`

#### `JCQD_ACCOUNTS`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：在所选站点官网注册后使用本人登录邮箱和密码。上游提供的 ikuuu 官网为 https://ikuuu.art，v2free 为 https://w1.v2free.top，gw树洞接口源站为 https://m.mmomm.io，均未在线核实。发布后的 Check 使用本变量；独立运行仍可用旧单账号变量 jcuname 与 jcpasswd 组合。同一行须适用于所选站点，凭据不同的站点请分别建立任务。
- 填写格式：`每个非空行一个账号：登录邮箱|密码；只在第一个 | 分割，密码后续字符保持原样；不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JYLT_Cookie`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：浏览器登录精易论坛 https://bbs.125.la，打开开发者工具的网络面板，选择本站已登录请求，复制请求头 Cookie 的完整值。会话过期后重新登录获取；不要复制请求头名称或向他人公开。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留分号及其中的等号，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `jsbaxfls`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：登录微信小程序“杰士邦安心福利社”，仅抓取自己访问vip.ixiliu.cn请求头中的Access-Token完整值；失效后重新登录并获取。
- 填写格式：`每个非空行填写一个完整Access-Token；保留原变量名，旧#分隔须改为换行；不使用&或@分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `jyjck`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：进入本人微信劲友家小程序及活动页，使用本人授权的抓包工具查看 https://jjw.jingjiu.com/app-jingyoujia/app/jingyoujia/promoteCode/scanUserPromoteCode 请求头 authorization 和请求体 userid，将同账号两项合并，不分享抓包内容。
- 填写格式：`每个非空行一个账号：authorization#userid；只按第一个#分割，后续字段原样保留，不支持@@、&或@分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KGQQ_COOKIE`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：在本人账号登录全民K歌网页版后，用浏览器开发者工具网络面板查看发送至 node.kg.qq.com 的请求，复制完整 Cookie 请求头；失效后重新登录获取。开启音乐奖励时还需从同账号音乐卡片请求查询参数获取实际 g_tk_openkey，禁止猜测或枚举。
- 填写格式：`每个非空行一个账号。默认填写完整 Cookie（必须含数字 uid）；音乐奖励开启时填写 完整Cookie|g_tk_openkey，只在第一个竖线处分割，Cookie 内等号及分号原样保留，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `kjwj_info`

- 所属脚本：`scripts/kjwj.py`
- 获取或设置：在科技玩家官网 https://www.kejiwanjia.net 注册账号，使用登录邮箱及密码；在青龙环境变量中填写。
- 填写格式：`邮箱#密码，每行一个账号，仅首个 # 为分隔符，密码中后续字符原样保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUAISHOU_COOKIE`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：在本人已登录的快手或快手极速版中打开“积分换好礼”页面，从本人控制的本地网络调试记录里找到 accelerate/info 请求，复制 Cookie 请求头；至少保留 kuaishou.api_st。不要绕过证书固定或使用第三方提取网站。
- 填写格式：`每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 & 或 @ 分隔`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUKU_ACCOUNTS`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：登录官方库库 AI 客户端，自行从可查看的 kuku.baidu.com 官方业务请求中复制同账号 Cookie 和 genflowpro 产品作用域 STOKEN；网页通行证令牌不一定有效。脚本不负责换发，请勿使用第三方凭据获取服务。
- 填写格式：`每个非空行一个账号：产品作用域STOKEN|完整Cookie；仅在第一个竖线处分割。Cookie 支持请求头、单行编辑器 JSON 或键值对象，必须包含 BDUSS。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUROBBS_ACCOUNTS`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：登录官方库街区 App，用本人授权的抓包工具读取 api.kurobbs.com 请求头 token；从角色查询 queryUserId 或签到 userId 获取社区 UID，不能用游戏角色 UID。请勿公开凭据或抓包。
- 填写格式：`每个非空行一个账号：社区UID|Token，仅在第一个 | 分隔，保留 Token 后续内容。社区 UID 为数字。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LINUXDO_COOKIES`

- 所属脚本：`scripts/l.py`
- 获取或设置：在浏览器登录 https://linux.do，打开开发者工具的网络面板，选择本站已登录请求，复制请求头 Cookie 的完整值。不要复制其他站点凭据。过期后重新获取。
- 填写格式：`每个非空行一个账号的完整 Cookie，字段以分号分隔，每个字段仅在第一个等号处分割；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LEAFLOW_COOKIE`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：浏览器登录 https://checkin.leaflow.net，打开开发者工具的网络面板，刷新页面后选择本站请求，复制请求头 Cookie 的完整值；不要复制响应头 Set-Cookie，不要公开。
- 填写格式：`每个非空行一个账号，完整名称=值请求头，多项 Cookie 用分号分隔；值中的等号、& 和 @ 原样保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NZZ_COOKIE`

- 所属脚本：`scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`
- 获取或设置：在浏览器登录 https://www.2nzz.com，打开开发者工具的网络面板，选择本站已登录请求，复制请求头 Cookie 的值，不含 Cookie: 前缀；请勿分享或写入公开仓库。失效后重新登录并获取。
- 填写格式：`每个非空行一个账号；完整 Cookie 的字段用分号分隔，键和值仅在第一个等号处分割，保留值中的后续等号；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NODESEEK_COOKIE`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：浏览器登录 https://www.nodeseek.com，打开开发者工具网络面板，找到本站 /api/attendance 或 /api/account/credit/ 请求，从请求标头复制完整 Cookie 值。不要复制 Cookie: 前缀。请勿分享凭据。
- 填写格式：`每个非空行填写一个账号的完整 Cookie；行内分号、等号及 & 原样保留，不使用分隔符拆分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YOUDAO_COOKIE`

- 所属脚本：`scripts/lizhixu_ql_script_hub_youdao.py`
- 获取或设置：浏览器登录有道云笔记 https://note.youdao.com，打开开发者工具的网络面板，选择该域名的已登录请求，复制请求头中的完整 Cookie 值。必须包含 YNOTE_PERS；不要复制 Cookie: 前缀，也不要将凭据贴入日志。
- 填写格式：`每个非空行一个账号的完整 Cookie，字段按分号分隔，每个字段仅在第一个等号处分开，后续等号和 & 保留为凭据内容；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LOBSTERAI_TOKEN`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：登录官方门户 https://lobsterai.youdao.com/portal#/login，在本人浏览器开发者工具 Network 中复制 Authorization 的 Bearer 后的 accessToken；refreshToken 从本人登录响应或 Application 本地存储获取。UID 从本人账号资料获取，也可由 AT 的 JWT sub 自动识别。仅在青龙私密变量中保存。
- 填写格式：`每个非空行一个账号：uid:AT:RT、uid:AT 或纯 AT。RT 可为空；同一账号字段使用英文冒号，逐个仅按首个冒号拆分并保留后续 RT 文本。不使用 @ 或 & 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LOOMY_TOKENS`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：在官方 Loomy 客户端登录，在本人授权的开发者工具或网络抓包中读取 loomyad.xunfei.cn 请求的 token 头，或 Authorization: Bearer 后的 session。登录态失效时重新登录并更新。不要公开凭据。
- 填写格式：`每个非空行一个账号，填写 session 或 备注|session；仅在第一个 | 处分割，后续凭据文本完整保留。不得使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_ACCOUNTS`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：在本人领克App合法抓取登录或刷新请求；从响应data.centerTokenDto取token或refreshToken，从同一账号刷新请求取deviceId。静态令牌通常约30分钟，刷新令牌通常约30天，以实际服务端结果为准。
- 填写格式：`每个非空行一个JSON对象；token可单独使用，refreshToken必须配套deviceId，可同时配置token作续期失败回退；不以&、@分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_APP_SECRETS`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包获取网关签名密钥与gl_dev_id，不内置他人密钥或设备标识。旧独立变量可兼容替代对应字段。
- 填写格式：`JSON对象：nativeAppKey、nativeAppSecret必需；分享或续期需glDevId；nativeAppCode用于优先AppCode续期，缺失时回退HMAC；loginAppCode仅兼容保存。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WALLHAVEN_SAVE_DIR`

- 所属脚本：`scripts/main.py`
- 获取或设置：在青龙中设置自己有写权限的壁纸保存目录。原脚本使用 /ql/data/downloads/local-website/img；本版必须显式设置以避免默认写入。无需账号或凭据。
- 填写格式：`绝对目录路径；自动追加当天日期子目录。预演可使用 /tmp/wallhaven-dry-run-placeholder。`

#### `MIFAN_ACCOUNTS`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：在米饭APP或米饭官方网站使用本人的注册用户名与登录密码；忘记密码时先通过官方渠道重置。无需抓包或提供Token。
- 填写格式：`每个非空行一个账号，用户名|密码；只在第一个竖线分割，密码后续竖线保留；用户名不能含竖线。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIMOTION_ACCOUNTS`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：在 Zepp Life 注册或绑定手机号、邮箱并设置登录密码；使用 Zepp Life 凭据，不是小米账号密码。在青龙环境变量中填写账号，切勿分享凭据。上传时从本人当天的 Zepp Life 运动同步请求取得 data_json 与 last_deviceid，先对 data_json 做 URL 解码，再放入同一账号 JSON 对象。
- 填写格式：`每个非空行一个 手机号或邮箱|密码，仅在第一个 | 分割；也支持每行一个 JSON 对象，字段 phone、password，上传时另需 data_json、last_deviceid，可选 min_step、max_step。data_json 是仅含当天一条记录的数组或 JSON 字符串，必须有非空 data 数组和 summary.stp.ttl；summary 可为对象或 JSON 字符串。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NETEASE_COOKIE`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：浏览器登录网易云音乐网页版，在 F12 → Application → Cookies 中复制同一账号 MUSIC_U 和 __csrf；不要发送给不可信 API 服务。
- 填写格式：`每个非空行一条完整 Cookie，必须包含非空 MUSIC_U 和 __csrf；字段用分号分隔，值中的 =、&、@ 原样保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NETEASE_API_BASE`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：提供自行信任的网易云 Node.js API 兼容 HTTPS 服务；必须支持维护脚本的登录、签到、云贝任务、VIP、榜单、听歌记录和等级接口。脚本自行通过 HTTP 调用，不安装或调用外部程序。
- 填写格式：`正式执行必填，断网预演可省略；HTTPS 地址，不含认证信息、查询参数或片段，该服务会接收账号 Cookie。`

#### `NGA_ACCOUNT`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：登录 NGA 客户端，在自己授权的请求抓包中获取 access_uid 和 access_token；iOS 还需从签到请求获取 __ngaClientChecksum。请勿分享抓包或凭据。保持同一账号的字段配套；出现登录失效时更新凭据，CLIENT ERROR 时重新获取当前 iOS 客户端校验码。
- 填写格式：`每个非空行一个账号；兼容 access_uid|access_token，仅按首个竖线分割；iOS 使用单行 JSON 对象，字段为 access_uid、access_token、client_checksum，全部为字符串。JSON 也适用于 Token 含竖线的账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NS_COOKIE`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：登录 NodeSeek，从浏览器开发者工具网络面板中的本站请求复制完整 Cookie 请求头值，不含 Cookie: 前缀；仅存入青龙环境变量，勿公开。
- 填写格式：`每个非空行一个账号，保留完整 Cookie 中的分号、等号与其他字符；不以 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NODESEEK_COOKIE`

- 所属脚本：`scripts/nodeseek_checkin.py`
- 获取或设置：登录 nodeseek.com，打开浏览器开发者工具的 Network，刷新页面，选择同站请求，复制 Request Headers 中完整的 cookie 值。请妥善保存，不要发送给他人。
- 填写格式：`每个账号一个非空行，每行为完整 Cookie 请求头值；Cookie 内的 & 和 @ 保持原样`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NTE_TOKEN`

- 所属脚本：`scripts/nte.py`
- 获取或设置：在本人官方塔吉多客户端登录，从用户中心刷新响应获取 refreshToken 和 uid；从绑定角色列表取得 roleId。云异环凭据来自本人客户端登录响应的 token 和 userId。deviceId 来自本人对应客户端请求，不要公开抓包内容。纯令牌模式依赖刷新响应返回 uid，否则请在账号对象中补充。
- 填写格式：`每个非空行一个账号：纯 refreshToken 或单行 JSON 对象。对象支持 refreshToken（兼容 token）、uid、deviceId、gameId、roleIds；可添加 cloudToken、cloudUserId、cloudDeviceId；云凭据必须成对提供，也可仅提供云账号。兼容 cloud_token、cloud_user_id、cloudUid、cloud 对象的 token/userId/uid/deviceId，以及 deviceid、cloud_device_id、game_id、role_ids、roleId。roleIds 为数组或逗号分隔角色列表；账号之间只用换行，不使用逗号、& 或 @。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_TOKENS`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。
- 填写格式：`每个非空行一个账号：AK|SK|security_token|project_id|base_url，兼容前置备注。全部配套字段非空，地址为 HTTPS 根地址或 /v2；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OLE_ACCOUNTS`

- 所属脚本：`scripts/ole.py`
- 获取或设置：在本人授权登录的 Ole 微信小程序中抓取 member_sign 请求；将 sessionId、Device-Name、unique、oleWxOpenId 请求头分别填入 session_id、device_name、unique、ole_wx_open_id。可同时取得 shopCode、cityId、User-Agent；不要向他人提供这些值。
- 填写格式：`每个非空行一个 JSON 对象；四个必填字段均为非空字符串。可选 shop_code 默认 205368，city_id 默认 c_region_11122，user_agent 默认保留上游值。兼容 account_name 字段但不输出用户填写的标签，避免泄漏手机号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PASSNAT_SK`

- 所属脚本：`scripts/passnat_checkin.py`
- 获取或设置：登录 PassNAT 网页端，在浏览器开发者工具的网络面板中查看已登录 API 请求，复制 Authorization 请求头的完整值；每个账号单独一行，切勿公开。
- 填写格式：`每个非空行是一个账号的完整 Authorization 值；仅以换行分隔账号，不使用其他分隔符。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PSNINE_ACCOUNTS`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：登录 https://psnine.com，在浏览器开发者工具的应用或存储面板读取本站 Cookie：__Psnine_psnid 与 __Psnine_shell。两项必须来自同一账号。不要复制整段 Cookie 或分享凭据。
- 填写格式：`每个非空行填写 psnid|shell，只按首个 | 分割；字段不能含分号、换行或非 ASCII 字符。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_SITE_HDKYL_CK`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：在浏览器登录蝴蝶站点（www.hdkyl.in），打开开发者工具的网络面板，访问 attendance.php，复制请求头中的完整 Cookie。遇到 SafeLine 时先完成浏览器验证并包含 sl-challenge-jwt。仅供本人账号使用，不要公开。默认选择此站；未选择此站时无需配置。
- 填写格式：`每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_SITE_CARPT_CK`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：在浏览器登录CARPT站点（carpt.net），打开开发者工具的网络面板，访问 attendance.php，复制请求头中的完整 Cookie。遇到 SafeLine 时先完成浏览器验证并包含 sl-challenge-jwt。仅供本人账号使用，不要公开。默认选择此站；未选择此站时无需配置。
- 填写格式：`每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_SITE_AFUN_CK`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：在浏览器登录AFUN站点（www.ptlover.cc），打开开发者工具的网络面板，访问 attendance.php，复制请求头中的完整 Cookie。遇到 SafeLine 时先完成浏览器验证并包含 sl-challenge-jwt。仅供本人账号使用，不要公开。默认选择此站；未选择此站时无需配置。
- 填写格式：`每个非空行是一个账号的完整 Cookie；按分号分隔 Cookie 字段，仅在第一个等号处分割字段，后续等号保留；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QODER_ACCOUNTS`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：在本人已登录的 Qoder 客户端查看本人授权请求的 Authorization 和 Cosy-* 请求头，取得访问令牌及设备字段；刷新令牌从本人客户端登录凭据取得。也兼容原取号工具导出的整行账号 JSON，无需运行该工具。请勿公开或发给第三方。
- 填写格式：`每个非空行一个 JSON 对象；accessToken 或 access_token、refreshToken 或 refresh_token 至少一项有效。device 内 clientType、machineOS、machineHostname、machineId、machineToken、machineCode、machineType、version 八项均为必填单行字符串。enabled=true 或 qiandao="是" 才执行，默认跳过。region 可选 cn/global。可保留 name、uid；serverchan、pushplus、qywx 为可选逐账号通知凭据。仅刷新模式必须有刷新令牌。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QUARK_COOKIE`

- 所属脚本：`scripts/quark_signin.py`
- 获取或设置：登录夸克网盘 https://pan.quark.cn/，打开浏览器开发者工具的网络面板，选择已登录的夸克请求，复制请求头 Cookie 的完整值；失效后重新登录获取。只复制值，不包含 Cookie: 前缀或备注。
- 填写格式：`每个非空行一个账号的完整 Cookie；保留分号及等号，不使用 &、&& 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `RACCOON_TOKENS`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：在小浣熊官网登录，在浏览器开发者工具网络面板查看本站已登录请求的 Authorization，将 Bearer 后令牌私下保存到青龙；过期后重新登录获取。
- 填写格式：`每个非空行一个账号：令牌或备注|令牌，只在第一个 | 拆分，支持 Bearer 前缀，不支持 & 或 @ 分隔账号。备注不输出。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rainyun_ck`

- 所属脚本：`scripts/rainyun.py`
- 获取或设置：使用雨云官网注册的账号用户名和登录密码；不需要抓取 Cookie，也不使用开放接口密钥。若账号需要验证码且接口拒绝空验证码，本脚本会报告失败，请先在官网核对账号登录要求。
- 填写格式：`每个非空行一个账号：用户名#密码。仅在第一个 # 处分隔，密码后续的 # 和空格完整保留；用户名按上游规则转换为小写。不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`规范凭据变量，每个非空行一个账号 Token，可带 Bearer 前缀；禁止用 & 或 @ 分隔账号。已有兼容变量也能独立提供凭据，无需同时配置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SF_ACCOUNTS`

- 所属脚本：`scripts/sf.py`
- 获取或设置：在自己顺丰 App 打开积分福利页面，通过自己的抓包工具读取 /mcs-mimp/share/app/shareLogin 请求的 sign 查询参数；读取后续积分请求头 channel、deviceid 和可选 User-Agent。填入 sign、channel、device_id、user_agent 字段。凭据到期后重新获取，勿分享原始请求。
- 填写格式：`每个非空行一个 JSON 对象，必填字符串字段 sign、channel、device_id；可选字符串字段 user_agent、account_name。账号只按换行分隔，字段内容完整保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `sfsyUrl`

- 所属脚本：`scripts/sfsu_checkin.py`
- 获取或设置：登录顺丰速运 App 或微信小程序，进入“我的-积分”，抓包 shareGiftReceiveRedirect 或 share/app/shareRedirect 请求，保存其完整 URL。不要将 URL 发到日志或通知中。多账号每个非空行一个 URL。
- 填写格式：`每个非空行一个完整的 URL 编码登录/分享 URL；整行作为同一账号凭据，不使用 &、@ 等字符分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `sgs`

- 所属脚本：`scripts/sgs.py`
- 获取或设置：微信关注申工社公众号，打开服务大厅并登录。在本人授权的抓包工具中找到 fwdt.shengongshe.org 的请求，复制请求头 Token 的值；过期后重新登录获取。不要复制 Cookie 或完整请求头。
- 填写格式：`每个非空行一个完整 Token；保留小写变量名 sgs，原版 # 多账号分隔改为换行，单账号参数兼容。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `sysxc_auth`

- 所属脚本：`scripts/shuyi.py`
- 获取或设置：登录自己的书亦烧仙草小程序，用已授权的抓包工具查看 scrm-prod.shuyi.org.cn 请求头的 auth 原值；失效后重新登录获取。不要填写整个请求头或公开凭据。
- 填写格式：`每个非空行一个账号的 auth 原值；保留变量名，不再以 # 分隔账号，凭据内部的 # 原样保留。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KANXUE_ACCOUNTS`

- 所属脚本：`scripts/sign_in.py`
- 获取或设置：登录 https://bbs.kanxue.com，在浏览器开发者工具网络面板查看 user-signin.htm 签到请求，取得同一账号的 Cookie 请求头和 csrf_token 表单值。可选复制 User-Agent；抓取请求可能已完成当天签到。凭据过期后重新登录获取，不要公开。旧配置兼容入口为 KANXUE_CONFIG。
- 填写格式：`每个非空行一个 JSON 对象，必填 cookie、csrf_token 字符串，可选 user_agent、account_name；JSON 内保留完整凭据，不用任何分隔符拆分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_TOKEN`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：登录本人官方鹰角通行证，在浏览器开发者工具中查看登录响应的 token，或使用官方通行证 web-api 响应的 data.content；也可从本人森空岛客户端授权响应获得成对的 cred、token。账密登录请填写本人手机号与密码的单行 JSON。不要共享凭据。
- 填写格式：`每个非空行一个账号：通行证 Token、cred:token、含 cred/token 的单行 JSON、含 data.content 的官方响应 JSON，或含 phone/password 的单行 JSON；冒号仅在第一处分割，不使用 &、@、分号或逗号分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_ACCOUNTS`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：登录森空岛官网后，在同一浏览器访问 https://web-api.skland.com/account/info/hg，复制 data.content 的鹰角通行证；也可使用本人手机号与密码，或通过显式 send-code 动作获取短信验证码。不要分享接口响应。
- 填写格式：`每个非空行一个账号：通行证原文、含 data.content 的单行 JSON，或单行 JSON 对象，字段 token；也可字段 phone 与 password，或 phone 与 code；可在同一 JSON 添加 did（由本人官方登录请求的 dId 头获取）。send-code 动作仅需 phone。账号不能使用逗号、& 或 @ 分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKYLAND_TOKEN`

- 所属脚本：`scripts/skyland.py`
- 获取或设置：在自己的浏览器登录鹰角网络官方账号页面 https://user.hypergryph.com/ ，再访问 https://web-api.hypergryph.com/account/info/hg 获取响应 content 中的账号 Token。若官方登录流程变化，从本人已登录客户端的授权请求获取 token；不要公开响应、Token 或 Cookie。
- 填写格式：`每个非空行一个完整账号 Token；禁止用逗号、& 或 @ 分隔多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_ACCOUNT`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：登录本人什么值得买客户端，从本人签到请求取得 sk；在开发者工具网络请求中复制本人完整 Cookie，至少含 sess。仅抽奖或网页签到可省略 sk。不要分享凭据。
- 填写格式：`每个非空行一个账号，格式 sk|完整 Cookie；仅在第一个 | 分割。网页或仅抽奖模式使用 |完整 Cookie。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SSL_ACCOUNTS`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：在 Cloudflare 个人资料的 API Tokens 中创建令牌，授予对应区域 DNS Read 权限；Zone ID 在区域概览获取；domains 填对应主域名。也可在个人资料获取 Global API Key 并配套登录邮箱。推荐受限令牌。旧版单账号变量可作为兼容输入。
- 填写格式：`每个非空行一个 JSON 对象；token 或 email/key 配套认证；zone_ids 和 domains 为一一对应的非空数组，区域标识为32位十六进制；例如字段结构 {"token":"占位凭据","zone_ids":["区域标识"],"domains":["主域名"]}。凭据文本由 JSON 解析完整保留，不使用符号分隔账号。`
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

#### `AUTH_CHECK_ACCOUNTS`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：在相应应用登录后，从下列兼容变量说明指定的原接口请求中获取本人凭据；只在青龙环境变量中保存，不发给他人。也可使用兼容变量代替本变量。
- 填写格式：`每行一个 JSON 对象，service 为下列兼容变量名，credential 为该账号完整凭据；同一账号配套字段保存在同一个 credential 中。设置本变量时优先使用它，不再读取兼容账号变量。`
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

#### `JLC_COOKIE`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：浏览器登录 https://oshwhub.com，打开 F12 网络面板并刷新 https://oshwhub.com/sign_in，找到 getSignInProfile 请求，复制请求头完整 Cookie 到青龙环境变量。默认开源平台流程必填；仅运行下单助手时改用 JLC_TOKEN。
- 填写格式：`每个非空行一个完整 Cookie；兼容 OSHW_COOKIE，二者同时设置时优先使用 JLC_COOKIE；不以 & 或 @ 分隔账号`
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
- 获取或设置：登录 https://www.v2ex.com，在浏览器开发者工具网络面板复制该站点已登录请求的完整 Cookie 请求头值。不要复制请求头名称。每个账号独立登录获取；原 Python 配置中的 cookie 值可直接迁移为一行。
- 填写格式：`每个非空行一个账号。兼容完整 Cookie 字符串，也可使用 JSON 对象，cookie 字段为完整 Cookie，proxy 字段为该账号可选代理 URL。Cookie 内等号和分号原样保留，不用 & 或 @ 分隔账号。`
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
- 获取或设置：在心喜微信小程序登录后，使用自己的抓包工具查看 api.xinc818.com 请求头 sso；仅使用自己的账号。未设置本变量时可使用旧变量 xx_sso。
- 填写格式：`每个非空行填写一个完整 sso，不使用 #、& 或 @ 分隔账号；值不可含空白或控制字符。`
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

#### `WEIBO_SUPERTOPIC_ACCOUNTS`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：在已登录的微博国际版中打开关注超话页，通过自己设备上已授权的 HTTPS 抓包工具取得 api.weibo.cn/2/cardlist 请求的完整 URL 或查询参数。保留全部原始参数，尤其是 gsid、s、containerid、aid 及客户端参数；密码变更或登录保护可能使其失效，需要重新获取。请勿公开凭据。
- 填写格式：`每行一个账号；完整 HTTPS URL 或 URL 编码查询字符串；按第一个等号解析字段并保留后续内容；& 仅分隔同一账号的查询字段，不分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `synshd`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：登录微信小程序“所有女生会员服务中心”，用本人授权的网络调试工具查看 7.wawo.cc 请求头 Authorization，复制 bearer 后的凭据；过期后重新登录获取。保留原变量名，原 # 多账号分隔改为换行。
- 填写格式：`每个非空行一个账号凭据，可带 Bearer 前缀；不使用 #、&、@ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TENCENT_VIDEO_COOKIES`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：浏览器登录腾讯视频，在开发者工具网络页找到 vip.video.qq.com 请求，复制请求头中的完整 Cookie，保留原始字段，不伪造设备信息。
- 填写格式：`每个非空行一个完整 Cookie，字段以分号分隔，仅按第一个等号拆分字段值。必需非空字段 vqq_openid、vqq_access_token、main_login；建议保留 vqq_vuserid、vqq_appid、vdevice_qimei36 和 ip。支持空行及 # 开头注释，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：在百度贴吧网站登录本人账号，从浏览器开发者工具请求头复制完整 Cookie，或其中 BDUSS 的值；开启成长任务时，从本人贴吧 APP 发往 tieba.baidu.com 的请求取得同一账号的 BDUSS 和 CUID。可改用兼容变量 TIE_BA_COOKIE。
- 填写格式：`每个非空行一个账号；支持 BDUSS 单值或完整 Cookie。成长任务要求同一行含 BDUSS=值; CUID=值，字段值按首个等号分割，后续等号保留；不能按 & 或 @ 分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_ACCOUNTS`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：登录塔吉多 App，通过本人授权抓包获取 bbs-api.tajiduo.com 请求头 Authorization 和 deviceid。可选 phone/password 是本人完美世界账号；openudid/vendorid 从同一设备登录请求获取。
- 填写格式：`每个非空行一个 JSON 对象，必含 token、deviceid 字符串；可选 uid（默认 0）、name、phone、password、openudid、vendorid、account_uid。兼容旧 JSON 对象或数组，不以 & 或 @ 分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCOUNTS`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：规范账号变量：在本人官方 Trae 中国版客户端登录响应或显式上传的 storage/auth 文件取得配套凭据；网页登录 https://www.trae.cn 后在浏览器开发者工具的应用、Cookie 中复制 X-Cloudide-Session 和 sessionid 的单个 Value，保留百分号编码。设备号从本人同账号客户端 storage.json 的 iCubeAuthInfo://icube-dc:<数字> 键取得；设备密钥和 machineId 必须来自同一设备。不要生成设备号、借用其他账号设备或分享凭据。
- 填写格式：`每个非空行一个 JSON 对象；accessToken 或 refreshToken 或 session/sessionid 至少一种，配套 deviceId 为同账号真实 12 至 20 位数字。可选 deviceKeyPem、devicePubPem、machineId、uid、name、expiresAt、fingerprint；兼容 access_token、refresh_token、device_id、account_name、expires_at。显式 icubeAuth、storagePath 或 authPath 可替代明文凭据；旧 JSON 数组仅作兼容。预演只用占位明文，不读凭据文件。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `tsthbck`

- 所属脚本：`scripts/tsthb_checkin.py`
- 获取或设置：在微信塔斯汀小程序登录，用本人授权的抓包工具查看 sss-web.tastientech.com 请求头中的 user-token；仅复制该字段值，过期后重新获取。
- 填写格式：`每个非空行填写一个账号的完整 user-token，不填请求头名称；不使用 & 或 @ 分隔账号，字段内部字符保持原样。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TY_ACCOUNTS`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：在天翼云盘官方客户端确认登录用户名和账号密码；仅有短信登录时先在官方客户端设置密码。每个账号将用户名和密码合在一行添加到青龙环境变量。需要验证码时先人工完成官方登录，本脚本不绕过验证码。原私有 CLOUD189 配置的 phone/password 须迁移到此变量。
- 填写格式：`每个非空行一个账号：用户名|密码；仅切分第一个竖线，密码内的竖线、&、@和空格原样保留；账号之间只能换行`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `tyqhCookie`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：登录统一茄皇小程序，使用本机 HTTPS 抓包查看官方 public/api/login 请求 JSON 的 thirdId 和 wid；必须使用同一账号的配套字段，不要分享抓包。
- 填写格式：`每个非空行 thirdId#wid#备注；备注可省略。先在首个 # 拆分 thirdId，再在剩余内容首个 # 拆分 wid 与备注，保留备注后续文本。不再使用 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VALORANT_COOKIE`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：在本人授权设备上登录掌上无畏契约，通过合法抓包方式取得 app.mval.qq.com 每日商店请求的完整 Cookie，并从 refresh_client_ticket 请求体取得同一账号的 ct。将 ct 追加为 Cookie 字段；票据过期后重新抓包。不要公开或发送给他人。
- 填写格式：`每个非空行一个账号；字段以分号分隔、名称与值以第一个等号分隔，后续等号原样保留。至少包含 userId、openid、access_token、ct，保留 tid、acctype 等其他原始 Cookie 字段。不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_ACCOUNTS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：在 https://www.vortexa.cloud 注册并登录。密码使用本人账号密码；Token 从开发者工具网络面板的 Authorization Bearer 或 /auth/login 响应 accessToken 获取；cookie 从官网 API 请求 Cookie 获取；refresh 使用 openbot_refresh Cookie 的值；fingerprint 从同一会话 x-fingerprint 请求头获取。不得公开这些凭据。建议使用此规范变量；未设置时兼容下列旧变量。
- 填写格式：`每个非空行一个 JSON 对象，不使用任何符号分隔账号。支持 account/password、token、cookie、refresh；至少提供一组可用凭据。可选 fingerprint/userAgent 绑定同一账号；JSON 字符串保留密码中的分隔符。Cookie 仅填写请求头值，不包含 Cookie: 前缀；token 不含 Bearer 前缀。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WangChao`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：在官方望潮 App 注册并设置登录密码，填写本人登录手机号与密码。进入首页“阅读有礼”，按官方要求点击右下角抽奖并绑定本人支付宝账号；脚本不会自动绑定或修改支付信息。
- 填写格式：`每个非空行一个“登录手机号#密码”。仅按第一个 # 切分，密码中的后续 #、&、@ 等字符完整保留。密码 UTF-8 长度不超过 117 字节。旧版 && 多账号分隔须手动迁移为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WENTIWEILAIHUI_ACCOUNTS`

- 所属脚本：`scripts/wentiweilaihui.py`
- 获取或设置：微信打开文体未来荟小程序并登录本人账号，使用本人授权的抓包工具读取 wlhmobile.crland.com.cn 请求头 Authorization 中的 Wechat 登录令牌。保留完整令牌，不向他人发送；过期时重新登录获取。会员积分查询需要令牌载荷含 openid。
- 填写格式：`每个非空行一个账号，可填裸 JWT 或完整 Wechat JWT；也可每行一个 JSON 对象，字段 token 必填，account_name、mobile、user_agent 可选，沿用上游字段名。JSON 不跨行；手机号兼容输入不发送不输出，账号名称不作为官方身份。不得用 &、@ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_ACCOUNTS`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：登录官方 WorkBuddy／CodeBuddy CN 客户端，在本人授权的接口请求中取得 Authorization 的 Bearer 令牌。可选 refresh_token 来自本人可读取的官方登录态 auth.refreshToken；uid、enterprise_id、domain 分别对应 X-User-Id、X-Enterprise-Id、X-Domain。可手动将旧配置 workbuddy.accounts 的对象逐行复制到此变量。不自动解密登录态、不要求安装其他工具或读取私有仓库。加密字段不可直接填写，应重新登录并取得可用凭据。
- 填写格式：`每个非空行一个 JSON 对象；access_token 为必填字符串，refresh_token、uid、enterprise_id、domain、user_agent 为同账号的可选字符串。兼容 accessToken、refreshToken、enterpriseId、userAgent。JSON 保留完整字段内容，不按 &、@ 或其他字符分割账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_REFRESH_TOKEN`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：国内版账号必填；从本人官方登录授权响应获取明文 accessToken（AT）与 refreshToken（RT）；不得使用加密信封、他人凭据或把真实值提交仓库。可读取本人已登录客户端的明文认证信息；若加密则使用官方授权响应。国际版单独运行时改填 WORKBUDDY_INTL_TOKENS。
- 填写格式：`每个非空行一个账号：手机号:AT:RT、AT:RT、手机号:RT 或单个明文 JWT；手机号只作为兼容备注，不输出；字段仅逐次切分首个冒号，保留末尾 RT 完整内容。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_INTL_TOKENS`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：仅 --intl 国际版账号必填；从本人官方登录授权响应获取明文 accessToken（AT）与 refreshToken（RT）；不得使用加密信封、他人凭据或把真实值提交仓库。登录域为 www.workbuddy.ai，与国内版凭据不通用；UID 取本人授权信息中的公开账号标识。国内版运行时无需此变量。
- 填写格式：`每个非空行一个账号：AT、备注|AT、备注|AT|uid 或 备注|AT|uid|RT；逐次切分首个竖线，保留末尾 RT 完整内容。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `wps_ck`

- 所属脚本：`scripts/wps_clock_in.py`
- 获取或设置：在WPS主页或微信小程序【我的WPS超级会员】登录，从本人授权的 *.wps.cn 请求Cookie中取得wps_sid参数的值。不要填写整个Cookie。
- 填写格式：`每个非空行一个wps_sid值；只按换行分隔账号，不使用&或@分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `Yht_token`

- 所属脚本：`scripts/yht.py`
- 获取或设置：在微信益禾堂手机点单小程序登录，用自己的授权抓包工具查看发往 webapi.qmai.cn 的请求头 qm-user-token；只复制该字段值，不复制手机号、Cookie 或整段请求头。失效后重新登录获取。
- 填写格式：`每个非空行一个完整令牌；保留大小写；不使用 #、&、@ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YOUDAO_COOKIE`

- 所属脚本：`scripts/youdao.py`
- 获取或设置：浏览器登录 https://note.youdao.com 后打开开发者工具网络面板，复制发往 note.youdao.com 已登录请求的完整 Cookie 请求头，不含 Cookie: 前缀。必须包含 YNOTE_PERS；过期后重新登录获取，勿公开凭据。
- 填写格式：`每个非空行一个账号；Cookie 字段用分号分隔，字段仅按第一个等号拆分，保留值中的后续等号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YYS_HUIJUAN_OUTPUT`

- 所属脚本：`scripts/yyshuijuantime.py`
- 获取或设置：在青龙环境变量中自行填写授权写入的 JSON 绝对路径。无需登录、抓包或账号凭据。兼容原数据时填写原脚本目录下的 config/yys_huijuan_time.json 绝对路径。请使用独立文件，已有文件须符合原脚本数据结构。
- 填写格式：`以 .json 结尾的绝对文件路径；每次运行使用一个路径，不按账号拆分`

#### `ZCODE_CN_TOKENS`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：默认国内版任务必填。在官方 ZCode 国内版完成登录，在浏览器网络面板查看 billing/preview 或 billing/claim 请求，取 Authorization 的 Bearer 后套餐 JWT、X-Device-Mid 设备值及 claim 的 X-Aliyun-Captcha-Verify-Param。不可使用推理 API Key。选择 intl 时改用国际版账号变量。
- 填写格式：`每行一个账号：jwt、jwt|device_mid、jwt|device_mid|captcha_param 或 备注|jwt|device_mid|captcha_param。验证码保留后续竖线，不用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `zippoCookie`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：登录微信小程序 Zippo会员中心，用自己的抓包工具获取 wx-center.zippo.com.cn 请求头 authorization 完整值，保留授权前缀。
- 填写格式：`每个非空行一个账号；不使用 #、& 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZODGAME_COOKIE`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：在浏览器登录 https://zodgame.xyz，打开开发者工具的网络面板，选择该站已登录页面请求，从请求头复制完整 Cookie 值。会话失效或遇到人机验证时，在浏览器完成登录与验证后重新复制。不要复制 Cookie: 前缀，不要公开该值。
- 填写格式：`每个非空行一个账号，行内为完整 Cookie 请求头值，字段用分号分隔，字段仅在第一个等号处分割，保留值中后续等号。账号间只用换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。


### 可选参数说明

#### `YDYP_PHONE`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：旧版单账号兼容变量；从本人中国移动云盘登录账号获取。未设置 YDYP_ACCOUNTS 时与 YDYP_AUTH 配套使用。
- 填写格式：`中国大陆11位手机号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YDYP_AUTH`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：登录中国移动云盘网页版 https://yun.139.com，打开开发者工具的网络面板，刷新页面，在 api.yun.139.com 或 yun.139.com 请求头中复制 Authorization；手机号使用该登录账号的手机号。凭据仅填入青龙环境变量，不要提交或分享。这是旧版单账号兼容变量，与 YDYP_PHONE 配套；优先使用 YDYP_ACCOUNTS。
- 填写格式：`Authorization 请求头值，可省略 Basic 前缀`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `YDYP_TRY_ALL`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：默认关闭；了解任务风险后自行开启，只调用未完成任务的点击接口，不自动生成发布文本。
- 填写格式：`布尔值，默认0；1、true、yes、on开启；0、false、no、off关闭`

#### `YDYP_INTERACT_LIMIT`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：自行设置小云互动礼单次执行的最大点击次数。每次点击后复查任务完成状态。
- 填写格式：`1至100的整数，默认30`

#### `YDYP_UPLOAD`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：默认关闭；同意在云盘根目录创建10字节随机任务文件后设置为1。仅任务106未完成时上传。
- 填写格式：`布尔值，默认0`

#### `YDYP_DELETE_AFTER`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：默认关闭；同意将本轮上传的任务文件移入回收站后设置为1。只对本轮已确认上传的文件生效。
- 填写格式：`布尔值，默认0`

#### `YDYP_DRY_RUN`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：无网络预演时设置为1。只检查配置与展示流程，不验证账号有效性或真实业务。
- 填写格式：`布尔值，默认0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：青龙通知总开关，默认开启；通知失败不改变业务退出码。预演会尝试通知模块，网络调用被禁止。
- 填写格式：`默认1；0、false、no、off关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：可选填写已有青龙 notify.py 或 sendNotify.js 所在目录；未填写时尝试导入 notify 和青龙标准脚本目录。
- 填写格式：`已有通知模块所在目录，不需要其他仓库`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：可选：在本人 PushPlus 管理页面获取推送令牌；青龙通知不可用时尝试 HTTPS 推送，预演不推送。
- 填写格式：`本人推送令牌`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SENDKEY`

- 所属脚本：`scripts/139_yunduo.py`
- 获取或设置：可选：在本人 Server酱管理页面获取 SendKey；青龙和 PushPlus 不可用时尝试，预演不推送。
- 填写格式：`本人 SendKey`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CYCD_DRY_RUN`

- 所属脚本：`scripts/2cycdx.py`
- 获取或设置：需要完全断网预演时自行设置为 1。
- 填写格式：`1、true、yes、on 表示开启；默认 0。`

#### `CYCD_LOCAL_TEXT`

- 所属脚本：`scripts/2cycdx.py`
- 获取或设置：可自行填写一言不可用时使用的本地签到文案。
- 填写格式：`可选纯文本，合并空白后最多 280 字；空值使用内置文案。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/2cycdx.py`
- 获取或设置：使用青龙现有通知设置；需要关闭时自行设置为 0。
- 填写格式：`默认 1；0、false、no、off 关闭通知。断网预演只模拟通知，不调用通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/2cycdx.py`
- 获取或设置：可选填入青龙现有 notify.py 所在目录；未设置时自动查找标准通知位置。
- 填写格式：`本机目录路径，仅用于可选通知，不影响业务退出码。`

#### `ICTO_BLOG_DRY_RUN`

- 所属脚本：`scripts/51cto_sign.js`
- 获取或设置：由用户设置，预演时填1。
- 填写格式：`1开启完全断网预演；其他值为真实运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/51cto_sign.js`
- 获取或设置：青龙面板按需设置，默认开启。
- 填写格式：`0、false、no、off关闭通知，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/51cto_sign.js`
- 获取或设置：填写已有青龙sendNotify.js所在目录，不需另一个项目仓库。
- 填写格式：`可选本地目录；同时自动查找青龙标准脚本目录和当前目录。`

#### `HRT999_DRY_RUN`

- 所属脚本：`scripts/999.py`
- 获取或设置：本地预演时设置为 1，正式执行时设为 0 或不设置。
- 填写格式：`1、true、yes、on 启用完全断网预演，其余值正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/999.py`
- 获取或设置：使用青龙现有通知配置；默认开启，关闭时设置为 0。
- 填写格式：`0、false、no、off 关闭，其他值开启；断网预演仅在日志输出通知摘要，不外发。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/999.py`
- 获取或设置：可选，填写青龙 notify.py 或 sendNotify.js 所在目录；默认自动发现常用青龙目录。
- 填写格式：`本地通知模块目录；缺失或发送失败不改变业务退出码。`

#### `ACFUN_TASKS`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：按需要在青龙中设置；默认 sign,info。公开发布、消费香蕉和点赞操作均须显式选择。
- 填写格式：`逗号分隔 sign（签到）、info（等级和香蕉余额查询）、like（点赞）、like-cycle（点赞后取消）、danmu（公开弹幕）、banana（投一根香蕉）、share（分享任务上报）；不得重复，like 与 like-cycle 不可同时选择。`

#### `ACFUN_LOCAL_TEXT`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：可选本地弹幕备用文案；默认“今天也要保持好心情。”；一言不可用或内容校验失败时使用。
- 填写格式：`空白合并后须为 1 至 280 字符，仅 danmu 使用。`

#### `ACFUN_DRY_RUN`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：离线验证时设置为 1；正式任务不设置或设为 0。
- 填写格式：`1 开启完全断网预演；0、false、no、off 或空值关闭。预演不验证真实业务。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：使用青龙自带通知配置；默认开启。离线烟雾测试设为 0；开启时预演仍尝试通知入口，但禁止网络和外部进程。
- 填写格式：`0、false、no、off 关闭，其余值开启，默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/acfun.py`
- 获取或设置：若青龙的 notify.py 不在常规路径，可设置其所在目录；无需私有工作流仓库。
- 填写格式：`可选目录路径；依次尝试导入 notify.send、此目录的 notify.py、/ql/data/scripts/notify.py、/ql/scripts/notify.py。通知不可用或失败不改变业务退出码。`

#### `AGENTROUTER_CONFIG`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选兼容输入：显式指定原配置文件路径；AGENTROUTER_ACCOUNTS 非空时优先使用账号变量。文件内容无需另一仓库。
- 填写格式：`本地 JSON 文件路径，结构为 agentrouter.accounts 数组；账号字段与账号变量的 JSON 对象相同。user_id 可从站点用户信息取得，正常登录自动获取；verify 只允许 true 或可信 CA 文件路径，不接受 false。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AGENTROUTER_BASE_URL`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：默认使用上游备用站点；需要时从本人使用的 AgentRouter 站点确认根地址。
- 填写格式：`HTTPS 根地址，默认 https://ps.air-outer.com；账号 base_url 优先。`

#### `AGENTROUTER_PROXY`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，从自己的代理服务取得；账号 proxy 优先。
- 填写格式：`HTTP 或 HTTPS 代理地址，可含代理认证；仅用于请求，不输出。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HTTPS_PROXY`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，从自己的代理服务取得；无显式代理时由 requests 使用系统代理环境。
- 填写格式：`HTTP 或 HTTPS 代理地址；支持标准小写变量及 NO_PROXY。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HTTP_PROXY`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，从自己的代理服务取得；保留标准 requests 代理环境兼容。
- 填写格式：`HTTP 或 HTTPS 代理地址。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NO_PROXY`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，按代理服务要求填写无需代理的主机；沿用 requests 标准行为。
- 填写格式：`逗号分隔的主机名或域名规则。`

#### `AGENTROUTER_CA_BUNDLE`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，从可信证书管理员获取 PEM CA 文件；默认使用 requests 受信任证书，并在 Windows 合并系统根证书。
- 填写格式：`本地 CA 文件路径；账号 verify 路径优先，始终开启 TLS 校验。`

#### `AGENTROUTER_ALLOW_AUTHORIZE`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：仅在理解 GitHub 应用授权权限后自行启用；默认要求先在浏览器手动授权。
- 填写格式：`默认 0；设为 1 允许首次授权表单提交，会授予应用权限。`

#### `AGENTROUTER_DRY_RUN`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：验证配置时设为 1；也支持 --dry-run。
- 填写格式：`1 为完全断网预演，不登录、不查询、不发送通知。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：使用青龙自带通知配置，默认开启；不需要填写通知凭据到本脚本。
- 填写格式：`默认 1；0、false、no、off 关闭；预演只展示通知摘要。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/agentrouter.py`
- 获取或设置：可选，指定青龙 notify.py 或 sendNotify.js 所在目录；默认自动查找标准青龙目录。
- 填写格式：`本地目录路径，通知失败或不可用不影响业务退出码。`

#### `SUYING_USERNAME`

- 所属脚本：`scripts/airport.py`
- 获取或设置：旧版兼容输入：本人速鹰666登录邮箱，仅在未设置 SUYING_ACCOUNTS 时生效。
- 填写格式：`一个账号的登录邮箱，须配套 SUYING_PASSWORD。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SUYING_PASSWORD`

- 所属脚本：`scripts/airport.py`
- 获取或设置：旧版兼容输入：本人速鹰666登录密码，仅在未设置 SUYING_ACCOUNTS 时生效。
- 填写格式：`一个账号的完整密码，须配套 SUYING_USERNAME。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SUYING_DRY_RUN`

- 所属脚本：`scripts/airport.py`
- 获取或设置：自行设置；预演时设为 1，正式执行时设为 0 或不设置。
- 填写格式：`1、true、yes、on 启用完全断网预演。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/airport.py`
- 获取或设置：青龙全局通知开关，默认开启。预演仅生成通知总结，不调用通知渠道。
- 填写格式：`0、false、no、off 关闭；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/airport.py`
- 获取或设置：可选：填写青龙现有 notify.py 所在目录；默认尝试导入 notify.send 及青龙标准脚本目录。缺失或投递失败不会改变业务退出码。
- 填写格式：`本机青龙通知模块所在目录。`

#### `AKILE_DRY_RUN`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：预演时手动设为 1。
- 填写格式：`1 开启断网预演，默认 0。`

#### `AKILE_REFRESH_TOKEN`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：需要保活时手动开启，并先配置青龙应用凭证。
- 填写格式：`1 开启刷新及回写，默认 0；仅查询模式不刷新。`

#### `CLIENT_ID`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：青龙系统设置→应用设置创建应用并授予环境变量权限；开启保活时必填。
- 填写格式：`青龙应用标识。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CLIENT_SECRET`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：与 CLIENT_ID 同一青龙应用的密钥；开启保活时必填。
- 填写格式：`青龙应用密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AKILE_STATE_FILE`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：按需指定可写统计文件路径。
- 填写格式：`默认同目录 state.json；保存时保留其他分区，禁止符号链接。`

#### `DAILY_ALL_CHILD`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：合集调用时设为 1。
- 填写格式：`1 输出兼容的 __DAILY_ALL_RESULT__ JSON。`

#### `DAILY_ALL_DISABLED`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：需要停用时配置。
- 填写格式：`包含 akile、akile_checkin 或 akilecloud 时跳过；用逗号、分号、竖线或换行列出服务。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：在青龙环境变量中设置通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭；预演只模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/akile_checkin.py`
- 获取或设置：使用自定义青龙通知目录时填写。
- 填写格式：`包含 notify.py 或 sendNotify.js 的目录；通知不可用不改变业务退出码。`

#### `ALIYUNDRIVE_DRY_RUN`

- 所属脚本：`scripts/aliyundrive_checkin.js`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`1 表示完全断网预演，其他值或未设置表示正式执行。`

#### `ALIYUN_PUSH_PLUS`

- 所属脚本：`scripts/aliyundrive_checkin.js`
- 获取或设置：从 PushPlus 官网账户获取推送令牌，存入青龙私密环境变量。
- 填写格式：`单个 PushPlus 推送令牌；未设置时只使用青龙通知。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aliyundrive_checkin.js`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`默认 1；0、false、no、off 关闭全部通知，大小写不敏感。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aliyundrive_checkin.js`
- 获取或设置：如默认青龙路径未找到通知模块，填写本机青龙 sendNotify.js 所在目录。业务执行不依赖此目录。
- 填写格式：`可选通知模块目录；默认依次查找 /ql/data/scripts、/ql/scripts 和候选脚本所在目录。`

#### `refreshToken`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：原脚本凭据变量的兼容别名，获取方式同 ALIYUN_REFRESH_TOKEN；规范变量未设置时才使用。
- 填写格式：`每个非空行一个刷新令牌；旧的 & 分隔格式须改为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ALIYUN_CLAIM_REWARD`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：按是否领奖自行设置，默认 1。
- 填写格式：`1 领取奖励；0 只签到，不领取任何奖励。`

#### `ALIYUN_CLAIM_ALL_REWARDS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：需要补领本月全部已签到未领奖励时显式设为 1，默认 0。
- 填写格式：`0 保留当日领奖；1 领取 status 为 normal 且 isReward 为 false 的全部签到奖励；ALIYUN_CLAIM_REWARD=0 优先关闭领奖。`

#### `ALIYUN_DRIVE_DRY_RUN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：本地预演时设置为 1，默认关闭。
- 填写格式：`1 启用完全断网预演、模拟通知，不等待、不写凭据文件、不注册设备。`

#### `ALIYUN_MAX_DELAY_SECONDS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：需要执行前随机等待时自行设置，默认 0，优先于 MAX_RANDOM_DELAY。
- 填写格式：`非负整数秒。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：旧延迟参数兼容项，未设置 ALIYUN_MAX_DELAY_SECONDS 时使用，默认 0。
- 填写格式：`非负整数秒。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：旧随机延迟控制兼容项，显式关闭时禁用随机等待。
- 填写格式：`1 启用配置的延迟；0 关闭；未设置时不覆盖延迟配置。`

#### `ENABLE_DEVICE_SESSION`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：仅在需要设备签名领奖时显式设置为 1，并通过公共 PyPI 安装 ecdsa；默认关闭。
- 填写格式：`1 注册设备会话并签名领奖；0 不注册。`

#### `ALIYUN_PERSIST_ROTATED_TOKENS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：需要保存轮换令牌时显式设为 1 并指定 ALIYUN_TOKEN_OUTPUT_FILE，默认关闭。
- 填写格式：`1 开启安全文件持久化；0 关闭；预演始终不写文件。`

#### `ALIYUN_TOKEN_OUTPUT_FILE`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：自行选择已存在父目录下的安全绝对路径，仅用于显式开启的持久化。
- 填写格式：`绝对文件路径，原子写入权限 0600，每行对应原账号顺序的最新刷新令牌，请安全更新青龙凭据。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：默认启用青龙通知，需要关闭时自行设置。
- 填写格式：`默认 1；0、false、no、off 关闭；通知缺失或失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：如通知组件不在默认位置，指定 notify.py 所在目录；默认尝试导入 notify.send 及 /ql/data/scripts/notify.py、/ql/scripts/notify.py。
- 填写格式：`目录路径，仅用于可选通知组件，核心账号任务不依赖私有仓库。`

#### `AUTO_UPDATE_TOKEN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：旧变量兼容说明，不用于自动改写面板，请使用显式安全文件持久化。
- 填写格式：`不改变运行行为。`

#### `PRIVACY_MODE`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：旧变量兼容说明，不放宽凭据保护。
- 填写格式：`不改变运行行为，凭据始终隐藏。`

#### `SHOW_TOKEN_IN_NOTIFICATION`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：旧变量兼容说明，不允许在通知中输出令牌。
- 填写格式：`不改变运行行为，凭据始终隐藏。`

#### `AOLAXING`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：兼容上游配置键名，将原 config.json 中 AOLAXING 数组复制为此环境变量；仅在 AOLAXING_COOKIE 未设置时使用。不读取本地私有配置文件。
- 填写格式：`JSON 数组，每项为包含 cookie 字段的对象。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AOLAXING_TASK_IDS`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：在浏览器网络面板查看每日任务列表返回的 taskID，并人工审阅任务实际行为后填写。默认留空，仅查询；多个账号使用相同任务选择。
- 填写格式：`逗号分隔的不重复数字任务 ID。仅执行列表中未完成的指定任务。`

#### `AOLAXING_DRY_RUN`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：预演时设为 1，不调用业务接口或通知网络；在线运行留空或设为 0。
- 填写格式：`1 开启；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：青龙通知默认开启，设为 0、false、no、off 可关闭。预演仅打印脱敏通知摘要。
- 填写格式：`默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aolaxing.py`
- 获取或设置：可选填写青龙已有 notify.py 所在目录；也会查找 Python notify 模块及青龙标准脚本目录。仅通知依赖青龙，业务独立运行。
- 填写格式：`本机通知模块目录路径。`

#### `HAX_DRY_RUN`

- 所属脚本：`scripts/api_hax.py`
- 获取或设置：手动设置为 1 进行断网预演。
- 填写格式：`默认 0；1 使用内置样本且不加载通知模块。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/api_hax.py`
- 获取或设置：使用青龙全局通知开关，默认启用。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/api_hax.py`
- 获取或设置：可选填写青龙已有 notify.py 所在目录；默认自动查找标准目录或导入 notify。
- 填写格式：`本地目录路径，仅用于可选通知，不是业务运行依赖。`

#### `ARKNIGHTS_DRY_RUN`

- 所属脚本：`scripts/arknightsbanner.py`
- 获取或设置：测试时设置为 1，正式运行设为 0 或不设置。
- 填写格式：`1 表示断网预演；0、false、no、off 表示正式运行。`

#### `ARKNIGHTS_TELEGRAM`

- 所属脚本：`scripts/arknightsbanner.py`
- 获取或设置：可选封面图片补充通道：通过 Telegram 的 BotFather 创建自己的机器人并取得 Token，通过自己的机器人 getUpdates 接口取得聊天 ID；确保机器人有发送权限。文字公告仍由青龙通知发送。不得公开或上传 Token。
- 填写格式：`每个非空行一个机器人 Token|聊天 ID，只在第一个 | 拆分字段；多个接收目标用换行分隔，支持负数群组 ID。图片失败独立记录，任一目标失败则本次非零退出并保留公告重试。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/arknightsbanner.py`
- 获取或设置：使用青龙既有通知配置；默认启用，设置为 0 可关闭全部通知和图片。关闭期间不把待推送卡池标为已处理，重新开启后重试。
- 填写格式：`默认 1；0、false、no、off 关闭。断网预演仅模拟通知，不加载通知代码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/arknightsbanner.py`
- 获取或设置：如青龙通知脚本不在默认位置，指定包含 notify.py 的目录。也会查找可导入的 notify 模块以及 /ql/data/scripts/notify.py、/ql/scripts/notify.py。通知渠道凭据在青龙通知配置中设置，不需要游戏凭据。
- 填写格式：`一个本地目录路径；不需要其他仓库、程序或安装引导。通知模块缺失不阻止扫描，但待推送公告会失败并保留重试；最终总结通知故障保持业务退出码。`

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

#### `SHYP_TASK`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：在青龙任务环境中选择商城抢购或积分任务；两类任务时间、凭据不同，请分别调度同一脚本。
- 填写格式：`buy（默认）或 points；商城计划 0 0 10 * * *，积分原计划 1 1 1 1 1`

#### `SHYP_BUY_NUM`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：从自己的商品请求 num 获取，按需选择数量。
- 填写格式：`1 至 100 的整数，默认 1`

#### `SHYP_BUY_PROMOTION_TYPE`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：从自己的商品请求 promotion_type 获取。
- 填写格式：`大写字母和下划线，最长 40 字符，默认 EXCHANGE`

#### `SHYP_BUY_ENABLE`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：确认商品、数量及费用后显式开启；默认不消费。
- 填写格式：`仅 1 允许真实抢购，默认 0`

#### `SHYP_BUY_TARGET_TIME`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按商品开放时间设置，运行环境使用本地时区，建议 Asia/Shanghai。
- 填写格式：`默认 10:00:00；支持 YYYY-MM-DD HH:MM:SS 或 immediate；仅时间已过等待次日，完整日期过期拒绝`

#### `SHYP_BUY_RETRY_TIMES`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按需设置，仅明确 success=false 时重试，未知结果不重试。
- 填写格式：`1 至 100 的整数，默认 10`

#### `SHYP_BUY_RETRY_INTERVAL`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按需设置明确拒绝后的重试间隔。
- 填写格式：`0.1 至 60 秒，默认 0.3`

#### `SHYP_BUY_TIMEOUT`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按需设置商城 HTTP 超时。
- 填写格式：`1 至 60 秒，默认 10`

#### `SHYP_BUY_DRY_RUN`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：进行无网络抢购预演时设置。
- 填写格式：`1、true、yes、on 开启，默认 0`

#### `SHYP_POINTS_ENABLE`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：确认需要提交积分动作后显式开启；默认仅查询积分、签到状态和任务列表。
- 填写格式：`仅 1 开启，默认 0`

#### `SHYP_POINTS_ACTIONS`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按需选择积分动作，执行顺序按配置保留；不包含商城抢购。
- 填写格式：`逗号分隔 read、video、favor、comment、share，默认全部五项；无需用逗号分隔账号`

#### `SHYP_POINTS_UNFAVOR`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：需恢复取消收藏行为时显式开启；可能移除原有收藏，默认保留收藏。
- 填写格式：`仅 1 开启，默认 0`

#### `SHYP_POINTS_TIMEOUT`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：按需设置积分服务 HTTP 超时。
- 填写格式：`1 至 60 秒，默认 30`

#### `SHYP_POINTS_LOCAL_TEXT`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：可选自定义评论本地回退短句，不要填写凭据；一言不可用时采用，否则使用内置原始短句。
- 填写格式：`去除首尾空白并合并连续空白，最长 280 字`

#### `SHYP_POINTS_DRY_RUN`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：进行无网络积分任务预演时设置。
- 填写格式：`1、true、yes、on 开启，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：使用青龙全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭；预演只生成摘要，不调用联网通知模块`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/auto_buy.py`
- 获取或设置：如青龙 notify.py 不在默认位置，可配置通知模块所在目录；通知不可用保留业务退出码。
- 填写格式：`可选目录；优先 import notify.send，再检查此目录、/ql/data/scripts、/ql/scripts`

#### `AUTOCLAW_INTL_TOKENS`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：选择 intl 或 both 时必填。在国际版官方桌面端登录，提取自己的登录响应；也可在自己的电脑检查 ~/.openclaw-autoclaw/openclaw.json，定位 models.providers 下 models[].headers.X-Authorization 并移除 Bearer 前缀。脚本运行不读取该文件或依赖桌面端。该来源通常没有续期登录态，失效后重新登录并更新变量。
- 填写格式：`每个非空行一个账号；字段和国内变量相同，推荐 JSON 对象。无续期登录态时只填 access，不伪造 refresh。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AUTOCLAW_REGION`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：按登录态所属地区自行设置，命令 --region 优先。
- 填写格式：`cn 默认国内版；intl 国际版；both 两地区执行，先国内后国际，所选每个地区均须配置账号。`

#### `AUTOCLAW_CN_DRY_RUN`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：预演时自行启用；默认关闭。
- 填写格式：`1、true、yes、on 启用全任务断网预演，不请求接口、不读写缓存、不实际推送。`

#### `AUTOCLAW_INTL_DRY_RUN`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：国际版兼容预演开关，任一地区开关启用均使整个任务断网。
- 填写格式：`1、true、yes、on 启用；默认关闭。`

#### `AUTOCLAW_CN_STORE_FILE`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：需要保存续期结果时显式选择私有缓存路径，排除出订阅和仓库；默认不落盘。
- 填写格式：`非符号链接的私有绝对路径；已有文件须为 0600，父目录须存在；以 0600 原子写入。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AUTOCLAW_INTL_STORE_FILE`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：需要保存国际版续期结果时显式选择独立私有缓存路径，不与国内版共用；默认不落盘。
- 填写格式：`非符号链接的私有绝对路径；已有文件须为 0600，父目录须存在；以 0600 原子写入。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：使用青龙已配置通知渠道，默认开启；--no-notify 也可关闭。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选指定现有青龙通知组件目录；默认发现可导入 notify、/ql/data/scripts、/ql/scripts。
- 填写格式：`目录内为 notify.py 或 sendNotify.js，不下载或安装组件。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选从自己的 PushPlus 官方账号获取，青龙组件不可用时备用。
- 填写格式：`单个推送令牌。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选从自己的 Bark 客户端获取推送地址。
- 填写格式：`含推送密钥的完整 HTTPS 地址。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECOM_WEBHOOK`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选从自己的企业微信群机器人配置页获取。
- 填写格式：`完整 HTTPS 机器人地址或机器人密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_WEBHOOK`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选从自己的钉钉群机器人配置页获取。
- 填写格式：`完整 HTTPS 机器人地址。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_SECRET`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：启用加签时从同一钉钉机器人配置页获取。
- 填写格式：`与 DINGTALK_WEBHOOK 配套的加签密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QL_URL`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选显式配置支持原通知接口的青龙面板地址，仅作为组件备用通道。
- 填写格式：`HTTPS 面板根地址，需配套 QL_TOKEN。`

#### `QL_TOKEN`

- 所属脚本：`scripts/autoclaw_cn_daily.py`
- 获取或设置：可选从自己的青龙面板获取对应 API 令牌。
- 填写格式：`与 QL_URL 配套的访问令牌。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `refreshToken`

- 所属脚本：`scripts/autosignin.js`
- 获取或设置：旧变量兼容输入，获取方式与 ALIYUN_REFRESH_TOKEN 相同，仅在规范变量未设置时使用。
- 填写格式：`每个非空行一个刷新令牌，旧版 & 分隔格式需改为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ALIYUN_DRY_RUN`

- 所属脚本：`scripts/autosignin.js`
- 获取或设置：断网验证时设置为 1；正式运行设为 0 或不设置。
- 填写格式：`1 为断网预演，不调用业务接口及外部通知。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/autosignin.js`
- 获取或设置：青龙全局通知开关，默认开启；可设置关闭值。
- 填写格式：`默认 1；0、false、no、off 关闭，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/autosignin.js`
- 获取或设置：可选，填写已配置的青龙 sendNotify.js 所在目录；默认依次查找 /ql/data/scripts、/ql/scripts。
- 填写格式：`本机目录路径；模块不可用或失败不改变业务退出码。`

#### `E_PROXY`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：可选，从自己有权使用的 HTTP 或 HTTPS 代理服务获取；默认直连，不读取系统代理。
- 填写格式：`HTTP 或 HTTPS 代理地址，所有账号共用；可包含代理认证信息但不会输出。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `E_USER_AGENT`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：可选，从浏览器 news.php 请求头复制 User-Agent；不设置时沿用上游浏览器标识。
- 填写格式：`单行浏览器标识，禁止换行和空字符。`

#### `E_DRY_RUN`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：预演时设置为 1；正式运行不设置或设为 0。
- 填写格式：`1、true、yes、on 启用完全断网预演，其他值正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：默认启用青龙通知；不需要通知时设为 0。
- 填写格式：`0、false、no、off 关闭；预演始终只生成通知摘要，不调用外部通知提供方。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/autosignin.py`
- 获取或设置：可选，填写青龙已有 notify.py 或 sendNotify.js 所在目录；默认尝试导入 notify 及青龙标准脚本目录。无需此目录即可执行业务。
- 填写格式：`本机通知模块目录路径；通知失败保持业务退出码。`

#### `BAIDU_DRY_RUN`

- 所属脚本：`scripts/baidu.py`
- 获取或设置：在青龙环境变量中设置为 1 即可完全离线预演。
- 填写格式：`1、true、yes、on 开启，其他值关闭，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/baidu.py`
- 获取或设置：使用青龙已有 notify.py 通知配置；本变量可关闭通知。离线预演生成通知摘要但不发送，保证不联网。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/baidu.py`
- 获取或设置：仅当通知文件位于自定义目录时填写该目录；自动兼容可导入的 notify.send 和青龙标准脚本目录。
- 填写格式：`含 notify.py 的目录绝对路径；可留空。`

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

#### `BAIDUWP_TASKS`

- 所属脚本：`scripts/baiduwp.py`
- 获取或设置：按需设置任务选择；不设置时依次执行会员签到、每日答题和会员信息查询。
- 填写格式：`英文逗号分隔 signin,quiz,info；可单独选择；重复项只执行一次。`

#### `BAIDUWP_DRY_RUN`

- 所属脚本：`scripts/baiduwp.py`
- 获取或设置：预演时设为 1；正式执行时设为 0 或不设置。
- 填写格式：`1、true、yes、on 启用完全断网预演；预演不验证实际登录状态，通知也仅模拟。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/baiduwp.py`
- 获取或设置：默认启用青龙通知，使用青龙现有通知配置；需要禁用时设置为 0。
- 填写格式：`0、false、no、off 禁用；其余值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/baiduwp.py`
- 获取或设置：可选填写已有青龙 notify.py 所在目录；默认自动查找可导入的 notify 模块及 /ql/data/scripts、/ql/scripts。
- 填写格式：`本地目录路径，仅用于可选通知，不是业务执行依赖。`

#### `BILIBILI_COIN_NUM`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：自行设置每日目标投币数，默认 0 不支出硬币。按照今日投币经验每 10 点折算一枚；余额不足或不能核实时失败闭合。
- 填写格式：`0 至 5 的整数，默认 0`

#### `BILIBILI_COIN_TYPE`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：沿用上游参数：1 优先关注 UP 主投稿，使用热门候选补充；2 使用热门候选。热门请求失败时改用排行榜。
- 填写格式：`1 或 2，默认 1`

#### `BILIBILI_MANGA`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：控制漫画签到。
- 填写格式：`布尔值，默认 1；支持 1/true/yes/on 和 0/false/no/off`

#### `BILIBILI_WATCH`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：控制上报视频观看进度 300 秒。
- 填写格式：`布尔值，默认 1；支持 1/true/yes/on 和 0/false/no/off`

#### `BILIBILI_SHARE`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：明确同意调用视频分享接口后设置为 1，默认关闭以避免自动分享。仅上报视频分享，不发布文字。
- 填写格式：`布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off`

#### `BILIBILI_SELECT_LIKE`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：明确同意投币时同时点赞后设置为 1，默认关闭上游投币附带点赞行为。
- 填写格式：`布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off`

#### `BILIBILI_SILVER2COIN`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：明确同意将银瓜子兑换为硬币后开启；沿用上游默认关闭。
- 填写格式：`布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off`

#### `BILIBILI_DRY_RUN`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：设置为 1 完全断网预演，检查参数与任务计划，不验证真实登录或业务成功。
- 填写格式：`布尔值，默认 0；支持 1/true/yes/on 和 0/false/no/off`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：青龙通知全局开关；实际运行发现 notify.py 并调用 send，通知故障不改变业务退出码；离线预演只生成脱敏摘要，不调用可能联网的通知传输。
- 填写格式：`默认 1；0/false/no/off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/bilibili.py`
- 获取或设置：可选，填写青龙公共 notify.py 所在目录；优先 import notify，再尝试本目录及 /ql/data/scripts、/ql/scripts。不需要项目私有模块。
- 填写格式：`本地目录路径，不含凭据`

#### `BSLY_DRY_RUN`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：自行设置；离线测试时设置为 1。
- 填写格式：`1 为完全断网预演，其他值为实跑；预演仅在本地展示通知摘要。`

#### `BSLY_ENABLE_DRAW`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：确认允许消耗抽奖机会后自行设置为 1；默认 0，实跑未开启时作为配置错误非零退出。
- 填写格式：`仅 1 允许实际抽奖；预演无需开启。`

#### `BSLY_MAX_DRAWS`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：按活动规则自行设置单账号请求次数上限；默认 1。
- 填写格式：`1 至 100 的整数；达到上限即停止，任何未验证成功的请求立即停止该账号，不自动重试。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：使用青龙既有通知配置；默认 1。
- 填写格式：`0、false、no、off（忽略大小写）关闭通知；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/bsly_draw.py`
- 获取或设置：可选填写青龙公共 notify.py 或 sendNotify.js 所在目录；留空自动发现。
- 填写格式：`本地目录路径；优先 notify.py，失败后尝试其他可用桥接及 sendNotify.js，后者需要青龙环境已有 Node.js。业务 HTTP 不依赖这些桥接。`

#### `BUGUTV_DRY_RUN`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：离线预演时设置为1；正式运行设置为0或删除。离线模式阻止网络连接，模拟结果不代表真实业务成功。
- 填写格式：`默认0；1开启，0、false、no、off关闭。`

#### `BUGUTV_LOGOUT`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：默认保留原脚本的退出登录行为。需要关闭退出登录时手动设置为0。退出失败会计入账号失败。
- 填写格式：`默认1；0、false、no、off关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：青龙全局通知开关，默认调用青龙notify.py发送脱敏总结。通知失败不影响业务退出码；离线预演也调用本地通知模块，但禁止其网络连接。
- 填写格式：`默认1；0、false、no、off关闭全部通知，包括可选Server酱。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：如青龙通知文件不在标准位置，可填写本地notify.py所在目录。默认尝试导入notify.send和青龙标准脚本目录；没有通知模块时脚本仍可独立完成业务。
- 填写格式：`本地目录路径，目录内应有notify.py及send函数。`

#### `BUGUTV_SERVER_SEND_KEY`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：可选：从本人Server酱账户获取SendKey，用于保留原脚本的额外通知能力。不填写时不调用Server酱。不要公开或提交该值。
- 填写格式：`单个SendKey，允许字母、数字、下划线和短横线；通知失败不改变业务退出码。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `sever_jiang_send_key`

- 所属脚本：`scripts/bugutv.py`
- 获取或设置：原脚本配置名称的可选环境兼容输入，迁移原有Server酱SendKey时使用；建议改用BUGUTV_SERVER_SEND_KEY。
- 填写格式：`单个SendKey，仅在未设置BUGUTV_SERVER_SEND_KEY时使用。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

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

#### `CAIGAMER_DRY_RUN`

- 所属脚本：`scripts/caigamer.js`
- 获取或设置：手动设置为 1 进行完全断网预演，正式执行时删除或设置为 0。
- 填写格式：`1、true、yes、on 开启；默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/caigamer.js`
- 获取或设置：在青龙环境变量中按需设置，默认开启通知。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/caigamer.js`
- 获取或设置：可填写本机青龙 sendNotify.js 所在目录；未设置时查找 /ql/data/scripts 与 /ql/scripts。
- 填写格式：`本机通知目录的绝对路径，仅用于可选通知，不影响业务独立运行。`

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

#### `xflCookie`

- 所属脚本：`scripts/chevrolet.js`
- 获取或设置：上游旧参数，获取方式同 CHEVROLET_ACCOUNTS；未设置规范变量时自动兼容。
- 填写格式：`每个非空行填写一个 cpctoken；规范变量即使为空也优先，不回退旧变量。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CHEVROLET_DRY_RUN`

- 所属脚本：`scripts/chevrolet.js`
- 获取或设置：需要离线检查时手动设置。
- 填写格式：`1 表示断网预演，其他值表示实际签到。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/chevrolet.js`
- 获取或设置：使用青龙已有通知渠道配置；需要关闭通知时手动设置本开关。
- 填写格式：`默认 1；0、false、no、off（不区分大小写）关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/chevrolet.js`
- 获取或设置：通常无需设置；自定义安装时填写本地青龙 sendNotify.js 所在目录。
- 填写格式：`本地目录路径；同时自动查找 /ql/data/scripts 和 /ql/scripts。`

#### `NZZ_DRY_RUN`

- 所属脚本：`scripts/ck_2nzz.py`
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演；正式执行时删除或设为 0。
- 填写格式：`1、true、yes、on 开启，默认 0；预演仅校验凭据格式，不验证真实业务成功。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ck_2nzz.py`
- 获取或设置：青龙全局通知开关，默认开启；按需要在环境变量中关闭。
- 填写格式：`默认 1；0、false、no、off 关闭，忽略大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ck_2nzz.py`
- 获取或设置：可选，填写青龙已有 notify.py 所在目录；留空时先尝试导入 notify，再查找青龙标准脚本目录。
- 填写格式：`本机目录路径；仅用于通知，不是业务依赖；通知故障不改变业务退出码。`

#### `ACFUN`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：兼容原配置 ACFUN 中的 phone 和 password，手动将账号数据填入环境变量，不再读取私有配置文件；优先使用 ACFUN_ACCOUNTS。
- 填写格式：`每个非空行 手机号|密码，或旧账号数组的 JSON，每项包含字符串 phone 和 password。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ACFUN_ACTIONS`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：按需在青龙设置任务开关。默认 sign,info；like、danmu、banana 均须主动启用。
- 填写格式：`逗号分隔的任务名，不重复：sign 签到，info 信息查询，like 点赞后取消，danmu 公开弹幕，banana 投一根香蕉。`

#### `ACFUN_DANMU_FALLBACK`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：启用弹幕时可在青龙填写公开备用文本，不要填入任何秘密。默认：欣赏作品，感谢分享。
- 填写格式：`归一化空白后 1 至 280 个字符，一言网络、超时、HTTP、大小、JSON、正文或长度异常时使用。`

#### `ACFUN_DRY_RUN`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：在青龙设为 1 进行完全断网预演；正式运行设为 0。
- 填写格式：`1 启用；0、false、no、off 或空值关闭。预演也不调用通知插件。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：青龙全局通知开关，默认开启；在青龙配置 notify.py 的通知渠道。
- 填写格式：`0、false、no、off 或空值关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ck_acfun.py`
- 获取或设置：如青龙通知模块不在默认位置，可填写已有 notify.py 所在目录；通知模块是可选集成，缺失不影响业务退出码。
- 填写格式：`本地目录路径，不是下载地址。`

#### `CODEARTS_DRY_RUN`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：自行设置为 1 启用完全断网预演，不读写状态，不发送通知，不验证真实业务。
- 填写格式：`1、true、yes、on 启用，其余关闭`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：青龙通知总开关，默认 1。
- 填写格式：`0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：可选：指定青龙已有 notify.py 所在目录；否则自动发现标准路径。
- 填写格式：`目录路径`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：从 PushPlus 个人设置取得推送令牌；作为原有备用推送渠道，不输出配置。
- 填写格式：`单个渠道配置值；地址必须为 HTTPS`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：从自己的 Bark 客户端取得 HTTPS 推送地址；作为原有备用推送渠道，不输出配置。
- 填写格式：`单个渠道配置值；地址必须为 HTTPS`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECOM_WEBHOOK`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：从企业微信群机器人设置取得 HTTPS 地址或机器人密钥；作为原有备用推送渠道，不输出配置。
- 填写格式：`单个渠道配置值；地址必须为 HTTPS`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_WEBHOOK`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：从钉钉群自定义机器人设置取得 HTTPS 地址；作为原有备用推送渠道，不输出配置。
- 填写格式：`单个渠道配置值；地址必须为 HTTPS`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_SECRET`

- 所属脚本：`scripts/codearts_daily.py`
- 获取或设置：从同一钉钉机器人取得可选加签密钥；作为原有备用推送渠道，不输出配置。
- 填写格式：`单个渠道配置值；地址必须为 HTTPS`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `comicai_Token`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：旧变量兼容入口，从本人登录后的 ComicAI API 请求头读取 Token。
- 填写格式：`仅当 COMICAI_ACCOUNTS 未设置时生效；每个非空行一个 Token，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `comicai_Cookie`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：旧变量兼容入口，从本人登录后的 ComicAI 网页请求头读取 Cookie。
- 填写格式：`仅当规范变量未设置时生效；每个非空行一个完整 Cookie，行数必须与旧 Token 变量一致；可以不设置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `COMICAI_DRY_RUN`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：在青龙中自行设置以预演配置。
- 填写格式：`1 启用完全断网预演，默认 0；预演不调用业务接口，不表示真实签到成功。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：在青龙中自行设置全局通知开关，默认启用。
- 填写格式：`0、false、no、off 关闭通知，默认 1；通知失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/comicai_ai_cookie.py`
- 获取或设置：如已有青龙 notify.py 不在常规目录，可填写其所在目录，无需安装额外应用。
- 填写格式：`本地目录路径；依次尝试导入 notify、指定目录及 /ql/data/scripts、/ql/scripts 的 notify.py。`

#### `CREALITY_DRY_RUN`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：预演时手动设置为 1，正式运行不设置或设为 0。
- 填写格式：`1、true、yes、on 开启断网预演；预演成功只说明本地参数和流程检查通过，不表示真实签到成功。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：按需手动配置，保留上游默认 true。
- 填写格式：`true 开启整体随机延时，其他值关闭；预演无延时。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：按需手动配置随机延时上限。
- 填写格式：`整数秒，默认 3600；非正数关闭整体延时，非法值沿用默认；多个账号正式运行间隔 10 至 30 秒。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：默认开启；按需设置全局通知开关。
- 填写格式：`0、false、no、off 关闭，其他值开启；通知不可用或失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/crealitycloud_checkin.py`
- 获取或设置：若青龙 notify.py 不在脚本目录或标准目录，填写其所在目录；由青龙管理通知凭据。
- 填写格式：`可选本地目录，搜索 notify.py；另支持脚本目录、/ql/data/scripts 和 /ql/scripts。预演禁止通知模块联网或运行外部命令。`

#### `DACHAO_MODE`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：自行选择需要运行的任务；也可使用 --mode 参数。
- 填写格式：`all（默认签到和阅读）、sign（签到）、read（阅读）`

#### `DACHAO_MAX_ARTICLES`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：自行设置单次阅读上限；兼容 --max-articles。
- 填写格式：`1 至 100 的整数，默认 6`

#### `DACHAO_LOTTERY`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：确认允许使用活动抽奖次数后开启。签到抽奖需在账号 JSON 中填本人活动页面的 sign_lottery_id；阅读抽奖编号由官方阅读列表获取。
- 填写格式：`默认 0；1 开启签到和阅读抽奖`

#### `DACHAO_REDEEM`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：确认允许兑换现金红包后开启，同时填写账号 JSON 内的 redeem_member；仅抽到现金红包时使用。
- 填写格式：`默认 0；1 开启兑换，需同时开启抽奖`

#### `DACHAO_DRY_RUN`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：验证配置时设为 1；无需安装业务依赖即可运行预演。
- 填写格式：`1 为完全断网预演；默认 0 为实际执行`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：青龙通知全局开关。实际执行时尝试 notify.send 或青龙 notify.py；缺失、失败或超过20秒只记录通知失败，保留业务退出码。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/dachao.py`
- 获取或设置：通知模块不在标准青龙目录时填写 notify.py 所在目录。
- 填写格式：`可选目录路径，仅用于青龙通知；业务运行不依赖私有文件`

#### `WPS_TASKS`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：按需选择任务；默认 checkin,reward。trial 会申请会员试用，lottery 和 task_center_lottery 会消耗抽奖机会，task_center 会执行加密签到及查询积分，需显式启用。
- 填写格式：`逗号分隔任务名称：checkin,reward,trial,lottery,task_center,task_center_lottery；账号仍按换行分隔。`

#### `WPS_RESTART_SERIES`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：只有愿意在签到系列断签失效后重开时设为 1，默认关闭。
- 填写格式：`1 启用；0 关闭。仅对服务端明确返回系列失效重试一次。`

#### `WPS_USER_AGENT`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：可从本人浏览器官方请求头获取 User-Agent，默认使用原福利脚本浏览器头；每行 JSON 的 user_agent 优先。
- 填写格式：`单行浏览器 User-Agent，不含 Cookie 或凭据。`

#### `WPS_DRY_RUN`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：验证配置和任务计划时设为 1，不访问 WPS 或通知网络，不判断凭据有效性。
- 填写格式：`1 开启完全断网预演；默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：默认启用 Qinglong 脱敏汇总通知；断网预演仅展示通知正文，正式运行调用通知模块。
- 填写格式：`0、false、no、off 关闭，其余启用，默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/daily_benefits.py`
- 获取或设置：可填写青龙平台 notify.py 或 sendNotify.js 所在目录，默认自动寻找标准通知位置；业务运行不依赖通知模块。
- 填写格式：`本机通知模块目录，不填则尝试导入 notify 和 /ql/data/scripts、/ql/scripts。`

#### `DAILYNEWSCN_TASK`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙同文件的各定时任务中手工设置；默认 dailynewscn。
- 填写格式：`可选：dailynewscn、bdhot、chouq、day60s、dyhot、jitang、kfc、meiju、miyu、oilprice`

#### `DAILYNEWSCN_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；对所有模式生效。`

#### `BDHOT_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 bdhot 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `BDHOT_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 bdhot 模式生效。`

#### `CHOUQ_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 chouq 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `CHOUQ_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 chouq 模式生效。`

#### `DAY60S_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 day60s 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `DAY60S_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 day60s 模式生效。`

#### `DYHOT_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 dyhot 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `DYHOT_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 dyhot 模式生效。`

#### `JITANG_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 jitang 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `JITANG_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 jitang 模式生效。`

#### `KFC_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 kfc 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `KFC_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 kfc 模式生效。`

#### `MEIJU_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 meiju 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `MEIJU_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 meiju 模式生效。`

#### `MIYU_LIST`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：无需账号或凭据；在青龙手工填写 1；仅选择此任务时必填，其他任务不读取。
- 填写格式：`仅 miyu 模式必填；每个非空行一个本地执行标记，兼容旧非空值；多个标记仍仅获取一次。`

#### `MIYU_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 miyu 模式生效。`

#### `OILPRICE_DRY_RUN`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：在青龙手工设置，无需从接口获取。
- 填写格式：`1 启用断网预演；仅对 oilprice 模式生效。`

#### `OILPRICE_AREA`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：手工填写原工作表 D 列中文地区，仅用于兼容标记 1。
- 填写格式：`中文地区，例如北京；地区行或 JSON area 优先。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：手工设置全局通知开关。
- 填写格式：`默认 1；0、false、no、off 禁用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/dailynewscn.js`
- 获取或设置：可选，填写青龙自身 sendNotify.js 所在目录；默认发现 /ql/data/scripts 或 /ql/scripts。
- 填写格式：`本机目录路径；缺失或通知失败保持业务退出码。`

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

#### `DEEPFLOOD_DRY_RUN`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：手动设为 1 进行完全断网预演；正式运行设为 0 或不设置。
- 填写格式：`1/true/yes/on 开启，0/false/no/off 关闭；默认关闭。`

#### `DF_RANDOM`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：兼容原脚本的签到接口 random 查询参数；无需获取额外凭据。
- 填写格式：`字符串，默认 true；仅传给签到接口，不控制本地等待。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：需要随机延迟时手动启用；维护版本默认关闭。
- 填写格式：`1/true/yes/on 开启，0/false/no/off 关闭；预演不等待。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：手动配置随机等待的最大秒数。
- 填写格式：`0 至 86400 的整数，默认 3600；仅 RANDOM_SIGNIN 开启时等待。`

#### `DEEPFLOOD_STATS_DAYS`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：手动设置收益查询时间窗口。
- 填写格式：`1 至 365 的整数，默认 30；以北京时间计算滚动窗口，最多查询 10 页。`

#### `DEEPFLOOD_TIMEOUT`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：手动设置每次 HTTP 请求超时秒数。
- 填写格式：`1 至 120 的整数，默认 15。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：使用青龙全局通知开关；通知渠道在青龙面板配置。
- 填写格式：`默认 1；0/false/no/off 关闭通知。预演仅显示脱敏通知预览，不加载模块、不发送网络通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/deepflood_checkin.py`
- 获取或设置：可选填写青龙 notify.py 所在目录；优先使用可导入的 notify.send，其次此目录，再尝试青龙标准目录。
- 填写格式：`本地目录路径；不安装或下载通知模块，通知不可用不影响业务退出码。`

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

#### `enshan_cookie`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：旧版 Cookie 参数兼容输入；优先使用 ENSHAN_COOKIE，其次 enshan_cookie，最后 EST_cookie。由浏览器登录后的论坛请求头获取。
- 填写格式：`与 ENSHAN_COOKIE 相同，每行一个账号；不从 config.json 读取或写回凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `EST_cookie`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：旧版 Cookie 参数兼容输入；优先使用 ENSHAN_COOKIE，其次 enshan_cookie，最后 EST_cookie。由浏览器登录后的论坛请求头获取。
- 填写格式：`与 ENSHAN_COOKIE 相同，每行一个账号；不从 config.json 读取或写回凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ENSHAN_DRY_RUN`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：在青龙设置为 1 开启完全断网预演，只校验配置并生成通知预览。
- 填写格式：`1、true、yes、on 开启；默认关闭。`

#### `ENSHAN_HTTP_TIMEOUT`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：可选 HTTP 请求超时；无需从账号获取。
- 填写格式：`5 至 120 的整数秒，默认 20。`

#### `ENSHAN_MAX_RANDOM_DELAY`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：可选启动随机等待上限；无需从账号获取。
- 填写格式：`0 至 3600 的整数秒，默认 0；优先于 MAX_RANDOM_DELAY 和 EST_ENABLE_RANDOM_WAIT。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：旧版等待上限兼容参数；未配置 ENSHAN_MAX_RANDOM_DELAY 时使用。
- 填写格式：`0 至 3600 的整数秒，默认 0。`

#### `EST_ENABLE_RANDOM_WAIT`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：上游随机延迟兼容开关；仅在两个等待上限都未配置时使用；维护版本默认无等待。
- 填写格式：`1、true、yes、on 开启 0 至 900 秒等待；默认关闭，断网预演始终不等待。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：旧版随机等待开关；无需从账号获取。
- 填写格式：`默认开启；0、false、no、off 禁用等待。`

#### `ENSHAN_PRIVACY_MODE`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：保留旧版隐私参数兼容；凭据及手机号始终隐藏，官方公开用户名按返回值展示。
- 填写格式：`布尔值；ENSHAN_PRIVACY_MODE 优先，默认开启；不会隐藏公开昵称。`

#### `PRIVACY_MODE`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：保留旧版隐私参数兼容；凭据及手机号始终隐藏，官方公开用户名按返回值展示。
- 填写格式：`布尔值；ENSHAN_PRIVACY_MODE 优先，默认开启；不会隐藏公开昵称。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：青龙全局通知开关；正式模式通过已有 notify.py 发送脱敏摘要，预演只生成摘要。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/enshan_checkin.py`
- 获取或设置：可选青龙 notify.py 所在目录；未配置时尝试导入 notify 并发现青龙标准目录。通知不可用不会改变业务退出码。
- 填写格式：`本地目录路径，非必填；脚本业务不依赖通知模块。`

#### `TG_BOT_TOKEN`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：旧版兼容输入，通过 Telegram 的 BotFather 获取；仅在 EPIC_TG_ACCOUNTS 为空时使用，需同时配置 TG_USER_ID。
- 填写格式：`单个机器人令牌，不支持用符号分隔多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TG_USER_ID`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：旧版兼容输入，从官方 Bot API getUpdates 的 message.chat.id 获取，或填写机器人有权限发送消息的公开频道用户名。
- 填写格式：`单个数字会话编号或公开频道用户名，配合 TG_BOT_TOKEN 使用。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `EPIC_LOCALE`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：按 Epic 商店支持的语言地区填写；默认 zh-CN。
- 填写格式：`双字母语言代码或语言代码-地区代码。`

#### `EPIC_COUNTRY`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：按实际所在地区填写 Epic 商店国家代码；默认 CN。
- 填写格式：`双字母国家代码。`

#### `EPIC_FONT_PATH`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：可选填写自行安装的中文字体文件路径；也会尝试常见系统中文字体。不自动下载或安装字体，缺少时推送文字。
- 填写格式：`本地字体文件路径。`

#### `EPIC_DRY_RUN`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：离线验证设置为 1；真实运行设置为 0 或不设置。
- 填写格式：`1/true/yes/on 开启完全断网预演。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：默认 1，调用青龙 notify.py 发送脱敏任务汇总；断网预演只模拟通知。
- 填写格式：`0/false/no/off 关闭汇总通知，不影响 Telegram 游戏提醒。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/epicfreegames.py`
- 获取或设置：可选指定已有青龙 notify.py 的目录；也自动查找脚本目录及青龙标准目录。
- 填写格式：`包含 notify.py 的本地目录。`

#### `ERKE_DRY_RUN`

- 所属脚本：`scripts/erke.py`
- 获取或设置：在青龙环境变量中设置；首次使用建议设为 1。
- 填写格式：`1、true、yes、on 启用完全断网预演；默认 0 正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/erke.py`
- 获取或设置：使用青龙已有通知配置；在青龙环境变量中控制通知。
- 填写格式：`默认 1；0、false、no、off 关闭。断网预演仅生成通知摘要并记录未投递，不调用可能联网的通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/erke.py`
- 获取或设置：如通知模块不在默认位置，填写本人青龙通知模块所在目录。
- 填写格式：`可选目录，含 notify.py 或 sendNotify.js；通知不可用不改变业务退出码。`

#### `SKYLAND_TOKEN_FILE`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：可选兼容输入：自行创建并保护本地凭据文件，填入其路径；可与 SKYLAND_TOKENS 合并去重，也兼容仅从文件读取。脚本不创建或修改此文件。
- 填写格式：`文件路径，支持 ~；文件每行一个账号，支持以 # 开头的注释。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKYLAND_DRY_RUN`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：离线测试时设为 1；实际签到时设为 0。
- 填写格式：`默认 0；1 启用，0/false/no/off 关闭。`

#### `SKYLAND_MODE`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：按执行环境选填；自动模式根据可发现的青龙通知模块选择日志输出流。
- 填写格式：`auto（默认）、qinglong 或 hermes。`

#### `SKYLAND_SILENT_OK`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：希望全部成功时抑制 Hermes 投递正文可设为 on；统计记录仍保留。
- 填写格式：`on 启用；默认 off。`

#### `USE_PROXY`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：仅需使用自己配置的系统代理时设为 on。
- 填写格式：`默认 off，忽略系统代理；on 使用系统代理。`

#### `NOTIFY_TITLE`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：可选填写通知标题，不得填入凭据。
- 填写格式：`默认“森空岛自动签到”。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：青龙全局通知开关；离线预演只生成脱敏通知正文，禁止调用可能联网的通知模块。
- 填写格式：`默认 1；0/false/no/off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：可选填写青龙 notify.py 所在目录；同时自动检查脚本目录、Python 模块与 /ql/data/scripts、/ql/scripts。
- 填写格式：`本地目录路径；通知模块不可用或失败不改变业务退出码。`

#### `EXIT_WHEN_FAIL`

- 所属脚本：`scripts/f1owkang_qingskyland_skyland.py`
- 获取或设置：仅为旧配置兼容保留；任意账号失败始终非零退出，无需设置此变量。
- 填写格式：`旧版 on/off 输入不再允许失败返回零。`

#### `FNNASCLUB_DRY_RUN`

- 所属脚本：`scripts/fnnasclub.py`
- 获取或设置：在青龙环境变量中手动设置，预演设为 1。
- 填写格式：`1、true、yes、on 开启断网预演，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/fnnasclub.py`
- 获取或设置：在青龙环境变量中设置全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/fnnasclub.py`
- 获取或设置：可选，填写已有青龙 notify.py 或 sendNotify.js 所在目录；未设置时自动寻找青龙标准目录及可导入的 notify 模块。
- 填写格式：`现有通知模块所在目录路径；业务运行不依赖通知模块。`

#### `FORUM_TASKS`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：按需选择动作，两个签到入口择一；完整打工流程可选 visit,work,credits。
- 填写格式：`逗号分隔 visit、credits、download、sign、sign_plus、work；默认 visit,credits。`

#### `FORUM_ALLOW_DOWNLOAD`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：确认下载可能消耗积分后显式开启。
- 填写格式：`1 开启；默认 0。`

#### `FORUM_ALLOW_WORK`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：确认站点安装 np_cliworkdz 并允许广告点击及领取奖励后显式开启。
- 填写格式：`1 开启；默认 0；work 动作必须开启。`

#### `FORUM_DRY_RUN`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：开启无网络参数和流程预演，不代表真实业务成功。
- 填写格式：`1 开启；默认 0；不访问论坛或发送网络通知。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：使用青龙已有 notify.py 发送脱敏总结；预演仅打印通知内容。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/forum_download.py`
- 获取或设置：可指定青龙 notify.py 所在目录；默认尝试导入 notify 及 /ql/data/scripts、/ql/scripts。
- 填写格式：`可选本地目录；通知失败保留业务退出码。`

#### `FWXS_DRY_RUN`

- 所属脚本：`scripts/fwxs_checkin.js`
- 获取或设置：在青龙环境变量中手动设置；预演用 1，正式执行用 0 或留空。
- 填写格式：`1 表示完全断网预演，包括模拟通知；不会验证真实账号或执行签到。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/fwxs_checkin.js`
- 获取或设置：按需在青龙环境变量中设置，默认启用。
- 填写格式：`0、false、no、off 关闭通知，其他值启用；断网预演仅模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/fwxs_checkin.js`
- 获取或设置：可选填写青龙公共通知模块 sendNotify.js 所在目录；默认查找 /ql/data/scripts、/ql/scripts 和脚本目录。
- 填写格式：`本机目录路径；通知模块不可用或失败时不改变业务退出码。`

#### `FXH_DRY_RUN`

- 所属脚本：`scripts/fxh.js`
- 获取或设置：在青龙环境变量中手动设置。
- 填写格式：`1 表示完全断网预演；其他值表示实际执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/fxh.js`
- 获取或设置：在青龙环境变量中手动设置，默认启用。
- 填写格式：`0、false、no、off 关闭通知，不区分大小写。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/fxh.js`
- 获取或设置：可选，填写青龙现有通知模块所在目录；默认查找 /ql/data/scripts 与 /ql/scripts。
- 填写格式：`包含 sendNotify.js 或 notify.py 的目录，不是业务依赖。`

#### `YYS_TASKS`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：根据资源需求选择任务，默认仅视频。
- 填写格式：`video、image 或 video,image；默认 video`

#### `YYS_DOWNLOAD`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：需要下载并写入资源时主动设置为 1；默认只解析资源。
- 填写格式：`1 开启下载；其他值仅列出，默认 0`

#### `YYS_LIMIT`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：自行设置每项任务本次最大新增下载数量；已验证文件不占限额。
- 填写格式：`非负整数；0 表示全部，默认 0`

#### `YYS_DRY_RUN`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：验证参数及内置页面解析时设置；不联网、不写资源、不调用外部通知模块。
- 填写格式：`1 开启断网预演，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：青龙全局通知开关。实际运行发送摘要；预演模拟通知。
- 填写格式：`0、false、no、off 关闭，默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/get_yys_cgvideo.py`
- 获取或设置：通知模块不在常规青龙路径时指定含 notify.py 的目录。
- 填写格式：`可选本地目录路径`

#### `YYS_TASKS`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：无需账号。在青龙环境变量中选择原画、CG视频或两者。
- 填写格式：`images（默认）、videos 或 images,videos`

#### `YYS_DOWNLOAD`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：无需从官网获取。确认下载目录与磁盘空间后自行显式开启。
- 填写格式：`1 开启下载；0 默认仅解析并列出素材；兼容 true/false、yes/no、on/off`

#### `YYS_IMAGE_DIR`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：自行选择有写入权限的原画保存目录。
- 填写格式：`目录路径，默认 ./yys原画`

#### `YYS_VIDEO_DIR`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：自行选择有写入权限的视频保存目录，标题历史也保存在该目录。
- 填写格式：`目录路径，默认 ./yys视频`

#### `YYS_VIDEO_LIMIT`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：自行设置本次成功下载的新视频数量上限。
- 填写格式：`非负整数，默认 0 表示全部；已有文件不计入上限`

#### `YYS_VIDEO_INTERVAL`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：自行设置每个新视频成功下载后的等待时间。
- 填写格式：`0 至 3600 的秒数，默认 2`

#### `YYS_DRY_RUN`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：自行设置断网预演开关；无需任何凭据。
- 填写格式：`1 使用内置页面样本且不联网、不写素材、不调用通知服务；默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：青龙全局通知开关，自行设置。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/get_yys_imagelinks.py`
- 获取或设置：选填青龙自带 notify.py 所在目录；未设置则自动发现 notify 模块及青龙常用目录。
- 填写格式：`目录路径；通知模块不可用不改变任务退出码`

#### `HELLOGITHUB_DRY_RUN`

- 所属脚本：`scripts/hellogithub.py`
- 获取或设置：预演时设置为 1。
- 填写格式：`1 启用完全断网预演，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/hellogithub.py`
- 获取或设置：使用青龙全局通知开关，渠道凭据在青龙 notify.py 内配置。
- 填写格式：`默认 1；0、false、no、off 禁用；新刊未提交通知时不更新状态且退出非零。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/hellogithub.py`
- 获取或设置：需要时填写青龙 notify.py 所在目录；默认查找脚本同目录及青龙标准目录，也支持导入 notify.send。
- 填写格式：`本地目录路径。`

#### `HIFIHI_COOKIE`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：在浏览器登录 https://hifihi.com/，从开发者工具网络面板复制该站点已登录请求的完整 Cookie 请求头。可单独使用，或与 HiFiTi_COOKIE 同时配置。
- 填写格式：`每个非空行一个账号；完整 Cookie 或旧版 cloudmusic.net 的值，不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HIFITI_DRY_RUN`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：青龙环境变量中设置为 1 开启断网预演。
- 填写格式：`1/0、true/false、yes/no 或 on/off；默认 0。预演不请求站点或通知服务，不等待。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：在青龙环境变量中按需配置随机启动等待；默认保留上游 true。
- 填写格式：`1/0、true/false、yes/no 或 on/off；多个账号时生效。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：青龙环境变量中设置随机启动等待上限，默认 3600 秒。
- 填写格式：`非负整数，实际最大等待 3600 秒；设置 0 关闭启动等待。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：青龙中默认启用通知，沿用面板 notify.py 或 sendNotify.js 配置。
- 填写格式：`默认 1；0、false、no、off 关闭。通知不可用或失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/hifiti_checkin.py`
- 获取或设置：若面板通知模块不在默认脚本目录，可设置其所在目录；独立运行无需配置。
- 填写格式：`包含 notify.py 或 sendNotify.js 的目录路径，仅用于可选青龙通知。`

#### `HLYL_DRY_RUN`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：在青龙环境变量中自行设置；断网预演不代表真实业务成功。
- 填写格式：`1、true、yes、on 开启，默认 0。`

#### `HLYL_LOTTERY_ATTEMPTS`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：确认活动可用及可能消耗次数或积分后自行设置；默认关闭抽奖。
- 填写格式：`0 至 10 的整数；0 关闭，正数为每账号最大抽奖请求数，失败立即停止该账号抽奖，不自动重试。`

#### `HLYL_LOTTERY_ACTIVITY_ID`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：在本人小程序目标活动的 luckDraw 请求查询参数 activityId 中核对；默认保留上游编号，无法离线确认活动是否仍有效。
- 填写格式：`1 至 30 位数字，默认 1796131190130262018。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：使用青龙统一通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，其余值开启；通知不可用不改变业务退出码。断网预演仅在封锁套接字的 Python 通知环境中尝试，不进行远程投递。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/hlyl.py`
- 获取或设置：可选，填写本人青龙 notify.py 或 sendNotify.js 所在目录；未设置时自动查找标准目录和 notify 模块。
- 填写格式：`本地目录路径，仅用于可选通知，不是业务运行依赖。`

#### `HSAYCookie`

- 所属脚本：`scripts/hsay.py`
- 获取或设置：与 hsayCookie 相同，仅在 hsayCookie 为空时读取；两者任选其一。
- 填写格式：`每个非空行一个完整 Token。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HSAY_DRY_RUN`

- 所属脚本：`scripts/hsay.py`
- 获取或设置：自行设置为 1 开启完全断网预演。
- 填写格式：`1、true、yes、on 开启；默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/hsay.py`
- 获取或设置：青龙环境变量中设置；默认开启。
- 填写格式：`0、false、no、off 关闭，其余值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/hsay.py`
- 获取或设置：如通知模块不在标准青龙脚本目录，填写包含 notify.py 的现有本地目录。仅通知可选，业务不依赖该文件。
- 填写格式：`本地目录路径。`

#### `HRT_WX_DRY_RUN`

- 所属脚本：`scripts/huaruntong_wx.py`
- 获取或设置：青龙环境变量中自行设置。
- 填写格式：`1、true、yes 或 on 启用断网预演，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/huaruntong_wx.py`
- 获取或设置：青龙环境变量中自行设置。
- 填写格式：`默认 1；0、false、no、off 关闭通知。断网预演仅模拟发送通知，不调用任何通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/huaruntong_wx.py`
- 获取或设置：可选，填写青龙现有 notify.py 或 sendNotify.js 所在目录。默认尝试导入 notify，再查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径；不下载或安装通知程序。`

#### `HYKB_DRY_RUN`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：本地预演时设为 1，真实运行时设为 0 或不设置。
- 填写格式：`1 或 0；默认 0。预演不请求业务接口，也不载入通知发送模块。`

#### `HYKB_ALLOW_EXPERIENCE`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：只有明确同意向官方活动记录试玩动作时才设为 1。遇到试玩前置条件后记录试玩、等待 65 秒并再次核验签到；预演不实际等待。
- 填写格式：`1 或 0，默认 0。关闭时如活动要求试玩则记失败，不伪报已签到。`

#### `HYKB_ALLOW_SHARE`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：只有明确同意向官方活动记录分享动作时才设为 1。遇到分享前置条件后记录分享，再登录并核验签到。
- 填写格式：`1 或 0，默认 0。仅记录官方 sharelimit 动作，不发布公开文本；关闭时如需分享则记失败。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：使用青龙现有通知配置，默认开启；可设为 0、false、no 或 off 关闭。
- 填写格式：`1、true、yes、on 开启；0、false、no、off 关闭。通知不可用或失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/hykb_gamesign.js`
- 获取或设置：可选填写青龙现有 sendNotify.js 所在目录；不填写时依次查找 /ql/data/scripts/sendNotify.js 和 /ql/scripts/sendNotify.js。无需另行安装或下载。
- 填写格式：`本地目录路径，只用于可选通知；业务功能不依赖该文件。`

#### `ikuuu`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：旧规范脚本的兼容邮箱密码输入，凭据获取方式同 IKUUU_ACCOUNT；仅未设置 IKUUU_ACCOUNT 时读取。
- 填写格式：`每行邮箱#密码，仅在第一个 # 处分割，保留后续密码字符。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IKUUU_COOKIES`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：兼容上游 Cookie 输入；在浏览器官网登录后复制 /user 请求的 Cookie 头，与 IKUUU_ACCOUNT 同时设置时追加处理，不自动去重。
- 填写格式：`每行完整 Cookie 或 备注||完整 Cookie，只在第一个 || 处分割；备注不输出，# 开头行跳过；每个 Cookie 必须包含 uid、email、key，不用 & 分隔字段或账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IKUUU_HOST`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：在浏览器核对 iKuuu 官方当前域名后填写。仅使用自己信任的官方域名，所有账号凭据都会发送到该站点。
- 填写格式：`仅 HTTPS 主机名，不含协议、端口或路径；未设置时邮箱模式用 ikuuu.nl，Cookie 模式用 ikuuu.win。`

#### `IKUUU_PROFILE`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：按需在青龙环境变量中开启资料读取。
- 填写格式：`默认 0；设 1 开启，资料失败仍尝试签到，但该账号整体失败。`

#### `IKUUU_FLOW`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：按需在青龙环境变量中控制剩余流量查询；查询在签到之后执行。
- 填写格式：`未设置时仅 Cookie 模式开启；设 1 全部开启，设 0/false/no/off 全部关闭。查询失败仍保留签到结果，但账号整体失败。`

#### `IKUUU_MAX_RANDOM_DELAY`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：按需配置签到前随机错峰等待。
- 填写格式：`0 至 3600 整数秒，默认 0；断网预演不等待。`

#### `IKUUU_DRY_RUN`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：离线验证时设置为 1。
- 填写格式：`默认 0；设 1 仅验证参数与请求计划，不请求、不等待、不导入或投递通知。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：使用青龙现有通知配置；可通过此总开关同时控制青龙与 PushPlus 通知。
- 填写格式：`默认 1；0/false/no/off 关闭；预演仅展示通知摘要。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：当青龙未自动提供 notify 模块时，填写包含现有 notify.py 的通知目录；业务请求本身不依赖该目录。
- 填写格式：`可选本地目录；否则尝试 import notify.send、/ql/data/scripts/notify.py、/ql/scripts/notify.py。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/ikuuu_checkin.py`
- 获取或设置：可选，在 PushPlus 官网个人账号获取推送 Token；无需配置即可使用青龙现有通知。
- 填写格式：`单个通知 Token；仅向 HTTPS PushPlus 通知接口发送，不进入日志；受 QINGLONG_NOTIFY 控制，预演不投递。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IMAOTAI_RESERVE`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：在青龙环境变量中按需开启，显式授权申购。
- 填写格式：`默认 0；1 开启，0、false、no、off 关闭；商品编号按实际活动更新。`

#### `IMAOTAI_ENERGY`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：在青龙环境变量中选择是否领取耐力。
- 填写格式：`默认 1；0、false、no、off 关闭；至少启用一项任务。申购模式每个商品请求后等待 20 秒领取耐力。`

#### `IMAOTAI_DRY_RUN`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：验证配置时设置为 1。
- 填写格式：`默认 0；1 完全断网预演，不查询接口、不申购、不领奖。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：青龙全局通知开关，通知渠道通过青龙配置。
- 填写格式：`默认 1；0、false、no、off 禁用。断网预演仅展示本地脱敏通知总结。正式运行通知失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/imaotai.py`
- 获取或设置：可选，填写现有青龙通知模块目录。
- 填写格式：`notify.py 或 sendNotify.js 所在目录；默认查找标准青龙路径和可导入的 notify 模块。`

#### `PIXIV_OUTPUT`

- 所属脚本：`scripts/index.js`
- 获取或设置：自行指定本地可写图片目录；正式下载必须明确设置本变量或当前工作目录 config.json 的 output 字段。预演无需设置。
- 填写格式：`目录路径；新图片保存为 标题_作品ID/标题_页码.扩展名，兼容检查旧版 标题/标题_页码.扩展名。`

#### `PIXIV_DRY_RUN`

- 所属脚本：`scripts/index.js`
- 获取或设置：在青龙环境变量中设为 1 开启完全断网预演；不创建下载目录或图片文件。
- 填写格式：`1 为预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/index.js`
- 获取或设置：使用青龙已有通知配置；默认开启，可主动关闭。预演调用可用通知组件时阻断网络，不进行外部投递。
- 填写格式：`0、false、no、off 关闭，大小写不敏感；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/index.js`
- 获取或设置：可选，指定青龙 sendNotify.js 所在目录；未设置时依次检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知组件目录路径。`

#### `IQIYI_COOKIE`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：兼容旧版参数；获取方式与 IQIYI_COOKIES 相同。IQIYI_COOKIES 非空时优先使用规范变量。
- 填写格式：`每个非空行一个账号，形如 P00001=<登录凭据>; P00003=<用户编号>; __dfp=<设备字段>。分号分隔同账号字段，每个字段仅按第一个等号拆分；保留值中其余等号。设备字段仅使用 @ 前段，@ 不分隔账号。优先使用 __dfp；P00002、QC005 等额外 Cookie 字段允许保留，不单独要求。# 开头的行作为注释。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IQIYI_CHANCES`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；查询普通抽奖剩余次数，不消耗机会。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_LOTTERY`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；执行单次会员抽奖，消耗机会。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_LOTTERY_ALL`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；先查询次数再用完普通抽奖机会，单轮最多二十次；优先于单次模式。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_SHAKE`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；执行单次摇一摇，消耗活动机会。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_SHAKE_ALL`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；连续摇一摇直到官方确认机会耗尽，单轮最多二十次；优先于单次模式。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_GIVE_TIMES`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；通过两次浏览和一次预约电影领取白金抽奖次数。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_PLATINUM`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；执行五次白金抽奖，消耗活动机会。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_V7`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；领取 V7 免费升级星钻权益，可能改变会员类型或权益。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_VIP_SIGN`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；执行上游 VIP 自动签到并查看当月成长值。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_DAILY_TASKS`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：在青龙环境变量中按需设置；执行上游每日成长任务查询、加入、完成通知和奖励领取，最多六轮；可能记录任务参与、浏览或预约并增加成长值。请先确认活动资格及影响。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `IQIYI_DRY_RUN`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：设为 1 启用完全断网预演，仅检查配置和请求构造，不发送签到、抽奖、成长任务或通知请求。
- 填写格式：`默认 0；支持 1/0、true/false、yes/no、on/off。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：青龙通知总开关，影响青龙通知及全部通知后备渠道；预演只生成总结。
- 填写格式：`默认 1；0、false、no、off 关闭；1、true、yes、on 开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：可选，填写青龙已有 notify.py 所在目录；也自动发现当前目录及青龙标准通知目录。业务不依赖通知模块。
- 填写格式：`可选目录路径，不安装或下载任何文件。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：从自己配置的 PushPlus 账号取得推送令牌，作为青龙通知不可用时的第一后备渠道。
- 填写格式：`单个令牌，不按账号拆分。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SENDKEY`

- 所属脚本：`scripts/iqiyi_checkin.py`
- 获取或设置：从自己配置的 Server酱账号取得 SendKey，作为青龙和 PushPlus 均不可用时的后备渠道。
- 填写格式：`单个推送密钥，不按账号拆分。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `EMAIL`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：兼容上游单账号邮箱；未配置 JC_ACCOUNTS 时与 PASSWORD 配套使用。
- 填写格式：`单个注册邮箱`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PASSWORD`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：兼容上游单账号密码，取自本人面板登录密码。
- 填写格式：`单个密码，不可用换行分隔多个账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JC_DRY_RUN`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：设置为 1 启用断网预演，默认 0。
- 填写格式：`1/0、true/false、yes/no 或 on/off`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：默认 1；设置为 0、false、no 或 off 关闭所有通知；通知失败不改变业务退出码。
- 填写格式：`通知开关`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：可选：设置青龙 notify.py 所在目录；也尝试导入 notify 及青龙标准脚本目录。
- 填写格式：`本地通知模块目录`

#### `JC_PUSHPLUS`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：设置为 1 开启原 SCKEY 的推送功能，改为 HTTPS，默认关闭；受 QINGLONG_NOTIFY 总开关控制。
- 填写格式：`1/0、true/false、yes/no 或 on/off`

#### `SCKEY`

- 所属脚本：`scripts/jc_checkin.py`
- 获取或设置：从本人 PushPlus 控制台获取 token，仅在 JC_PUSHPLUS=1 时必须提供。
- 填写格式：`PushPlus 推送令牌，不放入请求 URL`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `jcuname`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：兼容上游单账号登录邮箱；未设置 JCQD_ACCOUNTS 时必须与 jcpasswd 一起提供。
- 填写格式：`单账号登录邮箱`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `jcpasswd`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：本人站点登录密码，与 jcuname 配套。
- 填写格式：`单账号完整密码`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JCQD_TASKS`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：按需配置，仅选择本人授权签到的站点，默认只执行 ikuuu。
- 填写格式：`ikuuu、v2free、gw，可用逗号组合；默认 ikuuu`

#### `IKUUU_BASE_URL`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：导航失效或官方更换域名时，人工核实官方 HTTPS 域名后填写；该地址会接收登录凭据。默认从 ikuuu.club 导航页仅接受 ikuuu.art 或 ikuuu.club。
- 填写格式：`仅 HTTPS 域名，无路径、查询参数、用户信息或非标准端口`

#### `JCQD_DRY_RUN`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：离线检查时设置为 1，业务请求与通知模块均不调用。
- 填写格式：`1/true/yes/on 开启，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0/false/no/off 关闭，默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/jcqd.py`
- 获取或设置：可选填写现有青龙 notify.py 所在目录；也自动尝试导入 notify 和青龙标准目录。
- 填写格式：`本机通知模块目录路径`

#### `JYLT_RATE`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：需要延续上游热门帖评分功能时手动设为 1；默认 0，避免自动消耗评分额度或更改帖子评分。
- 填写格式：`1 开启热门帖逐帖 +1 评分，0 关闭；评分失败或额度受限时停止该账号评分并返回失败。`

#### `JYLT_LOCAL_TEXT`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：可自行填写评分附言的本地备用文字；不要填写凭据或个人敏感信息。优先使用一言及出处，提供方异常时回退本地文字。
- 填写格式：`归一化后不超过 280 字；空值或超长时使用内置文字。`

#### `JYLT_DRY_RUN`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：离线检查时设为 1，正式运行时移除或设为 0。
- 填写格式：`1 完全断网模拟所有请求和通知，0 正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：沿用青龙全局通知设置；默认开启。
- 填写格式：`0、false、no、off 关闭，其余值开启；通知失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/jingyiluntan_sign.py`
- 获取或设置：可填写本机青龙 notify.py 或 sendNotify.js 所在目录；默认尝试导入 notify 和青龙标准目录。
- 填写格式：`本地通知模块目录；脚本业务不依赖此目录。`

#### `JSB_DRY_RUN`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：在青龙环境变量中配置；预演不会验证真实业务。
- 填写格式：`1启用断网预演；0实际执行，默认0。`

#### `JSB_LOTTERY`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：确认活动仍开放并接受消耗积分或抽奖机会后自行配置。
- 填写格式：`1启用抽奖；默认0关闭。`

#### `JSB_LOTTERY_COUNT`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：根据期望的最大抽奖次数配置。
- 填写格式：`1至10的整数，默认10；次数已用完或失败立即停止抽奖。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：使用青龙现有通知设置；通知缺失或失败不改变业务退出码。
- 填写格式：`默认1；0、false、no、off关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/jissbon.py`
- 获取或设置：可选填写青龙notify.py所在目录；未配置时尝试导入及标准青龙路径。
- 填写格式：`本地目录路径；只用于可选通知，不是业务运行依赖。`

#### `jyjlatlon`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：从本人小程序请求取得真实位置。默认每日水滴及庄园、运动和活动任务必需；仅查询、签到、拍一拍、转盘、点赞或打卡查询时可不设置。
- 填写格式：`纬度#经度；分别在[-90,90]和[-180,180]内，所有账号共用本人授权位置。沿用原执行代码顺序，修正原说明文字错误。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JYJ_TASKS`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：按需选择动作；默认sign,daily-water。历史活动仅在确认仍开放后显式开启。
- 填写格式：`逗号分隔：info,sign,beat,turntable,like,subscribe,survey,share,run,garden,daily-water,photo,photo-query,health-draw,red-rain,herb-game。`

#### `jyjRun`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：仅在本人完成健康运动后设置，兼容原字段，默认关闭。
- 填写格式：`1开启运动奖励领取；其他值关闭。`

#### `JYJ_PLANT_TYPE`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：从劲友家game/medicineType响应选择想种植的medicineType，程序核对use=true且未种植；仅garden使用。
- 填写格式：`正整数；留空不自动种植。`

#### `JYJ_WATER_LIMIT`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：自行决定本轮最多消耗水滴的次数；仅garden使用。
- 填写格式：`0至100整数，默认0，不自动消耗水滴。`

#### `JYJ_PHOTO_PATH`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：提供本人真实活动照片的本地路径；photo任务必需，不下载照片或使用固定私有文件。
- 填写格式：`已有JPEG照片路径，非空且不超过10MB。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JYJ_HERB_SCORE`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：填写本人本次药材游戏实际成绩；herb-game任务必需，禁止伪造成绩。
- 填写格式：`非负整数；未设置则不允许执行herb-game。`

#### `JYJ_DRY_RUN`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：维护和导入验证时设置1，全程禁止网络，不验证真实业务。
- 填写格式：`1开启；0、false、no、off关闭，默认0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：青龙通知配置完成后默认启用，需要关闭时设0。
- 填写格式：`默认1；0、false、no、off关闭。预演调用本地适配器但阻断网络。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/jyj.py`
- 获取或设置：可选填写青龙通知模块所在目录，也自动查找脚本同目录和青龙标准目录。
- 填写格式：`包含notify.py或sendNotify.js的目录路径；通知失败保留业务退出码。`

#### `KGQQ_COOKIES`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：与 KGQQ_COOKIE 相同，仅作为兼容别名；优先使用 KGQQ_COOKIE。
- 填写格式：`与 KGQQ_COOKIE 相同；规范变量有值时不读取此别名。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KGQQ_DRY_RUN`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：由用户设置为 1 开启完全断网预演。
- 填写格式：`1/true/yes/on 开启，0/false/no/off 关闭，默认 0；预演只检查凭据结构及任务计划，不校验账号真实性、不发送通知。`

#### `KGQQ_LOTTERY`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：确认账号对应抽奖规则、次数及潜在消耗后，由用户显式设置为 1。
- 填写格式：`布尔开关，默认 0；开启四类上游抽奖入口。`

#### `KGQQ_MUSIC_REWARDS`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：确认音乐卡片互动奖励规则后，由用户显式设置为 1，并在账号行补充同账号真实 g_tk_openkey。
- 填写格式：`布尔开关，默认 0；每个账号一次读取卡片并按上游档位领取最高奖励，不枚举鉴权参数。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：由用户配置青龙通知服务；设为 0 可关闭全局通知。
- 填写格式：`默认 1，0/false/no/off 关闭；通知失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kgqq.py`
- 获取或设置：可选填写现有青龙 notify.py 或 sendNotify.js 所在目录；未设置时尝试导入 notify 和标准青龙目录。
- 填写格式：`本机通知模块目录；业务执行无此模块也能独立运行。`

#### `KJWJ_DRY_RUN`

- 所属脚本：`scripts/kjwj.py`
- 获取或设置：手动设置为 1 开启完全断网预演，默认 0 正式执行。
- 填写格式：`1、true、yes、on 开启；其他值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kjwj.py`
- 获取或设置：青龙全局通知开关，默认 1；通知渠道在青龙 notify.py 中配置。
- 填写格式：`0、false、no、off 关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kjwj.py`
- 获取或设置：可选：填写青龙官方 notify.py 所在目录；未设置时尝试导入 notify 或标准青龙脚本目录。
- 填写格式：`本地目录路径；不是业务运行依赖。`

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

#### `KUKU_COOKIES`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：兼容旧单账号输入，从官方业务请求复制 Cookie；与同账号 KUKU_STOKEN 配套。配置规范变量或 KUKU_TOKENS 时忽略此项。
- 填写格式：`Cookie 请求头、编辑器 JSON 或键值对象，包含 BDUSS。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUKU_STOKEN`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：兼容旧单账号输入，从官方客户端同账号业务请求获取 genflowpro 产品作用域 STOKEN；脚本不调用 DLL。
- 填写格式：`完整产品会话令牌，与 KUKU_COOKIES 配套。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUKU_TOKENS`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：兼容旧多账号输入，按各账号官方会话信息填写；没有规范变量时使用，不输出备注。
- 填写格式：`每个非空行：备注|BDUSS|PTOKEN|STOKEN；最多分割前三个竖线。不支持用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUKU_PROXY`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：可选，自行填写可信代理；代理地址可能含认证信息，日志不输出。
- 填写格式：`HTTP 或 HTTPS 代理地址；不支持 SOCKS。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUKU_DRY_RUN`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：预演时设置为 1。
- 填写格式：`1 开启完全断网预演，0 正式领取。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：青龙通知全局开关，默认开启。
- 填写格式：`0、false、no、off 关闭，其余非空值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：可选，填写青龙 notify.py 所在目录；也自动查找青龙标准目录或可导入通知模块。
- 填写格式：`本机通知模块目录，仅用于可选通知，不是业务依赖。`

#### `KUKU_NO_NOTIFY`

- 所属脚本：`scripts/kuku_daily.py`
- 获取或设置：兼容旧通知关闭开关。
- 填写格式：`1 关闭通知。`

#### `kurobbs`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：旧变量兼容输入：官方库街区 App 请求头 token；仅在 KUROBBS_ACCOUNTS 未配置时与 kuro_uid 配对。
- 填写格式：`单账号 Token，不支持旧式账号分隔符`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `kuro_uid`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：旧变量兼容输入：从本人官方请求的 queryUserId 或 userId 获取社区 UID。
- 填写格式：`单账号数字社区 UID，与 kurobbs 配对`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUROBBS_DRY_RUN`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：在青龙环境变量中设为 1，断网预演不会调用业务或通知网络。
- 填写格式：`1 开启；0 关闭，默认 0`

#### `KUROBBS_LIKE`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：明确同意脚本点赞他人帖子后设为 1；不会取消已有点赞。
- 填写格式：`1 开启；0 关闭，默认 0`

#### `KUROBBS_SHARE`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：明确同意提交帖子分享任务进度后设为 1；不发布分享文字。
- 填写格式：`1 开启；0 关闭，默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：青龙全局通知开关；默认尝试 notify.py，通知不可用不改变业务退出码。
- 填写格式：`默认 1；0、false、no、off 禁用`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kurobbs_sign.py`
- 获取或设置：可选：青龙现有 notify.py 所在目录；未配置时尝试导入 notify 和青龙标准目录，不需私人仓库。
- 填写格式：`通知模块目录路径`

#### `BROWSE_ENABLED`

- 所属脚本：`scripts/l.py`
- 获取或设置：按需要自行设置，兼容上游变量，默认 true。
- 填写格式：`true、1、yes、on 启用；false、0、no、off 关闭。`

#### `TOPIC_LIMIT`

- 所属脚本：`scripts/l.py`
- 获取或设置：自行设置首页候选话题上限，默认 50。
- 填写格式：`1 至 500 的整数；HTTP 首页无动态滚动，实际数量受返回页面限制。`

#### `BROWSE_COUNT`

- 所属脚本：`scripts/l.py`
- 获取或设置：自行设置随机读取话题数，默认 20；实际数量不超过发现数量。
- 填写格式：`0 至 500 的整数，0 跳过浏览。`

#### `LINUXDO_DRY_RUN`

- 所属脚本：`scripts/l.py`
- 获取或设置：预演时设为 1；默认 0。
- 填写格式：`1 完全断网，包括通知；使用本地样例，不验证账号或真实业务。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/l.py`
- 获取或设置：使用青龙全局通知开关，默认 1；通知渠道在青龙通知设置中配置。
- 填写格式：`0、false、no、off 关闭，其余值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/l.py`
- 获取或设置：可选，设为青龙 notify.py 所在目录；未设置时检查脚本目录及青龙标准目录。
- 填写格式：`通知模块目录的绝对路径；不属于业务运行依赖。`

#### `LEAFLOW_DRY_RUN`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：需要断网预演时设置为 1。
- 填写格式：`1/true/yes/on 开启；默认关闭。`

#### `LEAFLOW_BASE`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：默认使用原站点，仅在确认可信部署的情况下修改；兼容旧名 LEAFFLOW_BASE。
- 填写格式：`HTTPS 根地址，无用户名、密码、路径、查询或片段；默认 https://checkin.leaflow.net。`

#### `LEAFLOW_TIMEOUT`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：按需要设置单次请求超时，兼容 TIMEOUT。
- 填写格式：`1 至 120 的整数秒，默认 20；维护参数优先。`

#### `LEAFLOW_RETRIES`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：按需要设置每账号最大尝试次数，兼容 RETRY_TIMES。
- 填写格式：`1 至 5 的整数，默认 3；维护参数优先。`

#### `LEAFLOW_RETRY_DELAY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：按需要设置重试间隔，兼容 RETRY_DELAY。
- 填写格式：`0 至 60 的整数秒，默认 3；维护参数优先。`

#### `LEAFLOW_MAX_DELAY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：按需要设置本轮随机执行窗口，兼容 MAX_RANDOM_DELAY 与 RANDOM_SIGNIN。
- 填写格式：`0 至 3600 的整数秒，维护版默认 0；维护参数优先。`

#### `LEAFFLOW_BASE`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：旧脚本基础地址参数，推荐使用 LEAFLOW_BASE。
- 填写格式：`与 LEAFLOW_BASE 相同；新参数未设置时生效。`

#### `TIMEOUT`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：旧脚本超时参数，推荐使用 LEAFLOW_TIMEOUT。
- 填写格式：`1 至 120 的整数秒；新参数未设置时生效。`

#### `RETRY_TIMES`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：旧脚本重试次数参数，推荐使用 LEAFLOW_RETRIES。
- 填写格式：`1 至 5 的整数；新参数未设置时生效。`

#### `RETRY_DELAY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：旧脚本重试间隔参数，推荐使用 LEAFLOW_RETRY_DELAY。
- 填写格式：`0 至 60 的整数秒；新参数未设置时生效。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：旧脚本随机窗口参数，推荐使用 LEAFLOW_MAX_DELAY。
- 填写格式：`0 至 3600 的整数秒；新参数未设置时生效。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：沿用旧脚本随机签到开关，推荐直接设置 LEAFLOW_MAX_DELAY。
- 填写格式：`显式 true 开启旧随机窗口，窗口未设置时为 3600 秒；显式其他值关闭；新窗口参数优先。`

#### `NOTIFY_ON_ALREADY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：按需要控制已签到账号是否加入通知明细。
- 填写格式：`默认 true；其他值关闭此类明细，仍发送任务总数汇总。`

#### `DEBUG_MODE`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：兼容旧参数；本维护版始终提供脱敏阶段日志。
- 填写格式：`接受旧值但不保存原始响应，也不显示页面片段。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：通过青龙环境变量控制任务汇总通知。
- 填写格式：`默认 1；0/false/no/off 关闭；预演只生成本地通知内容，不加载或调用通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：如通知模块不在默认目录，填写青龙 notify.py 的所在目录。
- 填写格式：`本机目录，可选；亦支持 import notify.send、/ql/data/scripts/notify.py 和 /ql/scripts/notify.py。`

#### `HTTP_PROXY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：需要代理时按运行环境配置，脚本不记录代理值。
- 填写格式：`标准库支持的代理地址；兼容 http_proxy。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HTTPS_PROXY`

- 所属脚本：`scripts/leaflow_checkin_pyleaflow_checkin.py`
- 获取或设置：需要代理时按运行环境配置，脚本不记录代理值。
- 填写格式：`标准库支持的代理地址；兼容 https_proxy。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NZZ_DRY_RUN`

- 所属脚本：`scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`
- 获取或设置：自行设置为 1 开启完全断网预演；默认 0 正式签到。
- 填写格式：`1、true、yes、on 开启；其他值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`
- 获取或设置：青龙环境变量中设置；默认 1，关闭时设为 0。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`
- 获取或设置：可选：填写青龙现有 notify.py 所在目录；默认依次查找青龙标准脚本目录和可导入的 notify 模块。无需另行下载依赖，缺失时只记录通知不可用。
- 填写格式：`本机目录路径，不含 notify.py 文件名。`

#### `NS_RANDOM`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：按需要在青龙环境变量中设置；默认 true，保留上游随机签到奖励模式。
- 填写格式：`布尔值：true/false，也支持 1/0、yes/no、on/off。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：按需要在青龙环境变量中设置；默认 true，在随机时间窗口内签到。
- 填写格式：`布尔值；false 表示立即签到。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：按需要在青龙环境变量中设置；默认 3600 秒。
- 填写格式：`非负整数秒；账号按随机计划时间排序，等待使用同一起点，避免累积延时。`

#### `NODESEEK_DRY_RUN`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：无网络验证时设置为 1；正式运行默认 0。
- 填写格式：`布尔值；开启后不加载 HTTP 依赖、不请求接口、不等待、不执行签到，通知器在禁止网络的子进程中尝试发送。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：全局通知开关，默认 1；通知渠道在青龙自身通知配置中设置。
- 填写格式：`0、false、no、off 关闭通知；其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/lizhixu_ql_script_hub_nodeseek.py`
- 获取或设置：可选：填写青龙 notify.py 所在目录；也支持导入 notify.send 及标准青龙脚本目录。
- 填写格式：`本地目录路径；通知组件不可用或失败不改变业务退出码。`

#### `YOUDAO_DRY_RUN`

- 所属脚本：`scripts/lizhixu_ql_script_hub_youdao.py`
- 获取或设置：自行设置为 1 开启断网预演，默认 0；预演仅检查参数和执行计划，不确认真实业务成功，也不调用通知模块。
- 填写格式：`1 或 0，也支持 true/false、yes/no、on/off。`

#### `YOUDAO_AD_REWARDS`

- 所属脚本：`scripts/lizhixu_ql_script_hub_youdao.py`
- 获取或设置：自行设置；默认 1 保留三次广告空间奖励，设为 0 关闭该动作，签到和同步仍执行。
- 填写格式：`1 或 0，也支持 true/false、yes/no、on/off。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/lizhixu_ql_script_hub_youdao.py`
- 获取或设置：青龙全局通知开关，默认 1；0、false、no、off 关闭通知。配置通知渠道使用青龙通知模块自身设置。
- 填写格式：`默认 1，关闭值为 0、false、no、off。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/lizhixu_ql_script_hub_youdao.py`
- 获取或设置：可选指定青龙 notify.py 或 sendNotify.js 所在目录；未设置时自动查找青龙标准目录及可导入的 notify 模块。业务请求不依赖通知模块；缺失、失败或超时均保留业务退出码。
- 填写格式：`本机通知模块目录路径；只用于可选通知。`

#### `LOBSTERAI_DRY_RUN`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：自行设置为 1 开启完全离线预演；默认 0。
- 填写格式：`1、true、yes、on 开启，其他值关闭。`

#### `LOBSTERAI_REFRESH_STORE`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：可自行指定缓存文件位置；默认脚本目录 lb_refresh_tokens.json。目录需已存在且可写，缓存含敏感凭据，请勿上传仓库。
- 填写格式：`本机文件路径；文件使用 0600 权限原子保存。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：青龙通知默认启用；自行设置 0 关闭青龙和 PushPlus 通知。预演仅生成通知摘要，不发送。
- 填写格式：`默认 1；0、false、no、off 禁用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：可指定青龙平台 notify.py 所在目录；默认检测脚本目录、/ql/data/scripts、/ql/scripts 和 Python 模块路径。通知失败不改变业务退出码。
- 填写格式：`可信本机通知模块目录。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/lobsterai_checkin.py`
- 获取或设置：可选：在本人 PushPlus 管理页获取推送令牌，添加到青龙私密变量；保留上游微信推送功能。
- 填写格式：`单个推送令牌，不是账号凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LOOMY_ONBOARDING`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：用户自行设置；默认关闭。仅在实际完成任务并确认领取时启用。
- 填写格式：`0（默认，仅每日积分）或 1（批量领取）；--no-onboarding 优先关闭`

#### `LOOMY_DRY_RUN`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：预演时自行设置；不会发出请求、调用通知组件或写入结清记录。
- 填写格式：`1 启用，0 默认正式执行`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：用户自行设置青龙全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：可选，填写青龙 notify.py 或 sendNotify.js 所在目录；同时自动发现标准青龙目录及可导入的 notify 模块。
- 填写格式：`本机通知目录路径`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：从本人 PushPlus 后台获取推送令牌。 青龙通知不可用时作为兼容推送通道。
- 填写格式：`推送令牌`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：从本人 Bark 应用获取 HTTPS 推送地址。 青龙通知不可用时作为兼容推送通道。
- 填写格式：`完整 HTTPS 地址`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECOM_WEBHOOK`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：从本人企业微信群机器人设置获取 Webhook 地址或 key。 青龙通知不可用时作为兼容推送通道。
- 填写格式：`HTTPS Webhook 地址或机器人 key`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_WEBHOOK`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：从本人钉钉群机器人设置获取 HTTPS Webhook 地址。 青龙通知不可用时作为兼容推送通道。
- 填写格式：`完整 HTTPS 地址`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_SECRET`

- 所属脚本：`scripts/loomy_daily.py`
- 获取或设置：从本人钉钉群机器人的加签设置获取密钥，仅和相应 Webhook 配套使用。 青龙通知不可用时作为兼容推送通道。
- 填写格式：`加签密钥`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_REFRESH_TOKEN`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：`每行一个刷新令牌，与设备标识按行配对。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_DEVICE_ID`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：`每行一个同账号deviceId，不广播单个设备标识。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_TOKEN`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：兼容旧输入，从本人App登录响应或刷新请求取得；设置LYNKCO_ACCOUNTS后忽略旧账号变量。
- 填写格式：`每行一个静态令牌，按行配对回退；可单独使用，兼容bearer无空格前缀。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_NATIVE_APP_KEY`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：`单个字符串，对应nativeAppKey；不分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_NATIVE_APP_SECRET`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：`单个字符串，对应nativeAppSecret；不分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_NATIVE_APP_CODE`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：`单个字符串，对应nativeAppCode；不分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_LOGIN_APP_CODE`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：`单个字符串，对应loginAppCode；不分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_NATIVE_GL_DEV_ID`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人合法取得的App配置或授权抓包取得，优先于整合配置对应字段。
- 填写格式：`单个字符串，对应glDevId；不分账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_DO_SHARE`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：按需要设置，保留原默认1。
- 填写格式：`1签到并分享；0、false、no、off关闭分享。`

#### `LYNKCO_SHARE_MODE`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：按需要选择原有分享链。
- 填写格式：`默认simple两步链；full完整三步链，必须设置LYNKCO_CONTENT_ID。`

#### `LYNKCO_CONTENT_ID`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人App文章分享请求的contentId取得，用于完整链或两步失败回退。
- 填写格式：`单个文章内容编号，不是账号凭据。`

#### `LYNKCO_ARTICLE_ID`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从App文章页面获取articleId；不设置则保留五页动态查找和上游备用文章。
- 填写格式：`单个文章编号，不是账号凭据。`

#### `LYNKCO_TIMEOUT`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：按网络情况设置。
- 填写格式：`请求超时秒数，默认30，范围大于0且不超过120。`

#### `LYNKCO_ENERGY_DELAY`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：按积分异步到账情况设置。
- 填写格式：`积分查询等待秒数，默认5，范围0至120。`

#### `LYNKCO_ENV_FILE`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：显式兼容已有配置，不依赖外部仓库；仅只读，不回写。
- 填写格式：`可选JSON文件路径，包含secrets、user；只有无账号环境输入时才使用单账号user。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_DRY_RUN`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：无网络预演时设1。
- 填写格式：`默认0；1完全断网，不发送请求，不验证真实业务成功。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：青龙全局通知开关，默认1。
- 填写格式：`0、false、no、off关闭全部通知，其余开启；通知失败不改变业务退出码。`

#### `LYNKCO_QL_NOTIFY`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：兼容上游青龙通知开关。
- 填写格式：`默认1；0、false、no、off关闭青龙渠道，Bark仍受全局开关控制。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：青龙已有notify.py或sendNotify.js所在目录；未设置仍探测标准路径及可导入notify模块。
- 填写格式：`可选目录；预演只尝试禁止联网的Python通知，不启动Node通知。`

#### `LYNKCO_BARK_KEY`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：从本人Bark客户端取得推送Key，留空则不发送Bark。
- 填写格式：`单个推送Key，仅向固定Bark服务发送脱敏总结。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LYNKCO_BARK_ICON`

- 所属脚本：`scripts/lynkco_qinglong_single.py`
- 获取或设置：自行配置通知图标地址，可留空。
- 填写格式：`可选图标URL。`

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

#### `MIFAN_USER`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：旧版兼容输入，与MIFAN_PASSWORD配套；MIFAN_ACCOUNTS优先。
- 填写格式：`每个非空行一个用户名；不支持旧版分号多账号分隔。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIFAN_PASSWORD`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：本人账户登录密码，与MIFAN_USER逐行对应。
- 填写格式：`每个非空行一个密码，行数必须与用户名一致。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIFAN_TASKS`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：在青龙环境变量中按所需操作设置；默认仅每日签到，公开操作需要显式选择。
- 填写格式：`sign、like、comment、repair 用逗号组合；默认sign；点赞每次最多20条，评论每次最多10条。`

#### `ENABLE_REPAIR`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：旧版补签开关；补签可能消耗账户资源，仅按本人意愿开启。
- 填写格式：`true或1开启补签；默认false。`

#### `MIFAN_DRY_RUN`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：在青龙环境变量中设置，用于断网预演。
- 填写格式：`1开启；默认0；不调用业务、文本提供商或通知网络，不读写进度。`

#### `MIFAN_LOCAL_TEXT`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：自行填写失败回退时使用的公开评论文本；默认使用脚本内置短句。
- 填写格式：`单段文本，空白折叠后最多280字；不要填写任何隐私或凭据。`

#### `MIFAN_STATE_DIR`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：可选指定本机可写进度目录；默认脚本旁的.mifan-state。
- 填写格式：`目录路径；按账号哈希隔离点赞和评论进度，不保存密码或Token。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：青龙全局通知开关；配置青龙自身的通知渠道。
- 填写格式：`默认1；0、false、no、off关闭；预演仅记录通知摘要准备状态。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/mifan_optimized.py`
- 获取或设置：可选填写青龙已有notify.py或sendNotify.js所在目录；不需要下载其他仓库。
- 填写格式：`本机目录路径；通知组件可选，缺失或失败不改变业务退出码。`

#### `MIMOTION`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：可选旧版账号环境变量；仅在 MIMOTION_ACCOUNTS 为空时使用。将原配置中的 MIMOTION 账号数组复制为该环境变量，不再读取 config.json。
- 填写格式：`JSON 数组；每个对象支持 phone、password、min_step、max_step；上传仍须本人 data_json、last_deviceid。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIMOTION_ACTION`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：按需要设置；默认 login 仅验证账号，upload 显式授权修改本人当天步数。
- 填写格式：`login 或 upload，默认 login。`

#### `MIMOTION_MIN_STEP`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：可选最小步数；只在明确开启上传时使用，账号 min_step 优先。
- 填写格式：`整数，默认 10000；0≤最小值≤最大值≤100000。`

#### `MIMOTION_MAX_STEP`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：可选最大步数；只在明确开启上传时使用，账号 max_step 优先。
- 填写格式：`整数，默认 19999；与最小步数构成含两端的随机范围。`

#### `MIMOTION_DRY_RUN`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：设为 1 启用完全断网预演，验证参数和执行计划，不登录、不上传；通知也禁止联网。
- 填写格式：`1 启用；0、false、no、off 或空值关闭，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：青龙通知总开关；默认调用 notify.py，缺失、超时或发送失败仅记录，不覆盖业务退出码。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/mimotion.py`
- 获取或设置：可选青龙通知模块目录；自动优先导入 notify，再查该目录以及 /ql/data/scripts、/ql/scripts。
- 填写格式：`包含 notify.py 的本地目录；不是业务脚本依赖。`

#### `NETEASE_COOKIES`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：旧版多账号 Cookie 兼容输入，获取方法同 NETEASE_COOKIE。
- 填写格式：`每个非空行一条 Cookie，支持 # 注释和包裹整行的引号；非空时优先于 NETEASE_COOKIE。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NETEASE_WEB_SIGN_WEAPI`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：在青龙环境变量中按需开启；从公开 Python 包仓库安装 pycryptodome。
- 填写格式：`1 使用官方 weapi 网页签到并显示积分；默认 0 保留原 API 方式，其他阶段不变。`

#### `NETEASE_SCROBBLE`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：按需在青龙环境变量中显式开启，知悉会修改播放历史。
- 填写格式：`默认 0；只有 1 开启随机模拟听歌记录，最多 300 首。`

#### `NETEASE_DRY_RUN`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：在青龙环境变量或本地测试环境设置。
- 填写格式：`1 为完全断网预演，默认 0 为正式执行；预演不验证真实账号。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：青龙环境变量中设置全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭通知，预演只模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：可选指定青龙通知模块目录；默认自动查找 notify 模块及 /ql/data/scripts、/ql/scripts。
- 填写格式：`包含 notify.py 的目录路径。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：登录 PushPlus 官网，在个人中心获取推送令牌。
- 填写格式：`单个令牌；青龙通知失败时使用 HTTPS JSON 接口，业务码 200 才确认送达。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SENDKEY`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：登录 Server酱官网获取 SendKey。
- 填写格式：`单个 SendKey；青龙与 PushPlus 均不可用时使用，业务码 0 才确认送达。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/netease_task.py`
- 获取或设置：在 Bark 应用中复制可信 HTTPS 推送地址，包含推送密钥。
- 填写格式：`HTTPS 地址，不含查询参数或片段；保留独立推送，受全局通知开关控制。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `nga_uid`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：旧版兼容输入：从自己授权的 NGA iOS 签到请求获取 access_uid；仅未设置 NGA_ACCOUNT 时生效，建议迁移为 NGA_ACCOUNT 单行 JSON。
- 填写格式：`每行一个值，三个旧版变量必须逐行对应同一账号；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `nga_cookie`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：旧版兼容输入：从自己授权的 NGA iOS 签到请求获取 access_token；仅未设置 NGA_ACCOUNT 时生效，建议迁移为 NGA_ACCOUNT 单行 JSON。
- 填写格式：`每行一个值，三个旧版变量必须逐行对应同一账号；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `nga_client_checksum`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：旧版兼容输入：从自己授权的 NGA iOS 签到请求获取 __ngaClientChecksum；仅未设置 NGA_ACCOUNT 时生效，建议迁移为 NGA_ACCOUNT 单行 JSON。
- 填写格式：`每行一个值，三个旧版变量必须逐行对应同一账号；不使用 & 或 @ 分隔账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NGA_UA`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：客户端请求的 User-Agent；无 iOS 校验码时生效，原默认值保持不变。
- 填写格式：`默认 Nga_Official/90409`

#### `NGA_DRY_RUN`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：设为 1 时只检查配置与动作计划；不请求接口、不延时，也不调用可能联网的通知器。
- 填写格式：`默认 0`

#### `NGA_ENABLE_DAILY_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：显式开启日常任务 2、131、30，会改变任务及奖励状态。
- 填写格式：`默认 0`

#### `NGA_ENABLE_VIDEO_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：显式开启免广告初始化、四次免广告视频任务和五次 N币视频任务。
- 填写格式：`默认 0`

#### `NGA_ENABLE_SHARE_MISSIONS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：显式开启五次分享记录及分享奖励，不发布文字内容。
- 填写格式：`默认 0`

#### `NGA_QUERY_STATS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：查询资产统计，不改变账号状态。
- 填写格式：`默认 1`

#### `NGA_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：正式运行前随机等待的最大秒数，范围 0 至 21600。
- 填写格式：`默认 0`

#### `NGA_ACTION_DELAY_SECONDS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：日常与分享动作间隔秒数，范围 0 至 30。
- 填写格式：`默认 1`

#### `NGA_VIDEO_DELAY_SECONDS`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：视频动作间隔秒数，范围 0 至 120。
- 填写格式：`默认 30`

#### `NGA_HTTP_TIMEOUT`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：每次 HTTP 请求超时秒数，范围 3 至 60。
- 填写格式：`默认 20`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：青龙全局通知开关；0、false、no、off 关闭，通知失败不影响业务退出码。
- 填写格式：`默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/nga_checkin.py`
- 获取或设置：可选青龙通知模块目录，含 notify.py 或 sendNotify.js；业务运行不依赖该目录。
- 填写格式：`默认 未设置`

#### `NS_RANDOM`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：自行选择签到奖励模式；默认 true；其他值按 true 处理，兼容原脚本。
- 填写格式：`true 随机奖励，false 固定奖励。`

#### `NS_IMPERSONATE`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：按所安装 curl_cffi 支持的浏览器指纹设置，默认 chrome110。
- 填写格式：`curl_cffi 支持的浏览器指纹名称。`

#### `NS_DRY_RUN`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：预演时设为 1；不发 HTTP 请求、不等待、不调用外部通知助手。
- 填写格式：`1、true、yes、on 启用，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：默认 1，正式运行调用青龙 notify.py；预演仅输出脱敏通知摘要。
- 填写格式：`0、false、no、off 关闭；其他值启用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/nodeseek.py`
- 获取或设置：可填青龙通知模块目录；默认先导入 notify.send，再查找 /ql/data/scripts/notify.py 和 /ql/scripts/notify.py。
- 填写格式：`包含 notify.py 的本地目录；通知不可用或失败不影响业务退出码。`

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

#### `TOKEN`

- 所属脚本：`scripts/nte.py`
- 获取或设置：旧版兼容输入，获取方法同 NTE_TOKEN；仅在 NTE_TOKEN 未设置时读取。
- 填写格式：`每个非空行一个账号，格式同 NTE_TOKEN。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TGD_GAME_ID`

- 所属脚本：`scripts/nte.py`
- 获取或设置：从本人塔吉多角色接口的 gameId 获取；默认异环编号 1289。
- 填写格式：`单个游戏编号，默认 1289；账号对象 gameId 优先。`

#### `TGD_SIGN_GAME_IDS`

- 所属脚本：`scripts/nte.py`
- 获取或设置：按本人角色和官方签到接口核对可用游戏编号；沿用上游回退链。
- 填写格式：`逗号分隔编号；尝试顺序为本变量、账号 gameId、默认编号、1289、1257，去重。`

#### `TGD_ROLE_IDS`

- 所属脚本：`scripts/nte.py`
- 获取或设置：在本人塔吉多绑定角色后，从角色列表响应取得 roleId。多账号推荐在各账号 JSON 中设置 roleIds。
- 填写格式：`逗号分隔角色编号，追加到各账号角色列表；留空自动发现。`

#### `NTE_DRY_RUN`

- 所属脚本：`scripts/nte.py`
- 获取或设置：预演时设置为 1；正式签到时关闭。
- 填写格式：`1、true、yes、on 开启断网预演；其余值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/nte.py`
- 获取或设置：使用青龙全局通知配置。预演仅生成脱敏摘要，不请求通知服务。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/nte.py`
- 获取或设置：可选：填写青龙现有通知模块目录；不可用时保留业务退出码。
- 填写格式：`包含 notify.py 的目录；未设置时尝试 import notify、/ql/data/scripts/notify.py、/ql/scripts/notify.py。`

#### `OFFICEACE_AK`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：`临时 AK`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_SK`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：`临时 SK`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_STS`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：`临时 security_token`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_PROJECT_ID`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：`项目 ID`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_BASE_URL`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从已登录果办客户端或控制台授权控制面请求获取同一账号的临时 AK、SK、security_token、project_id 和网关地址；上游说明约两小时有效，运行前刷新。桌面 models.json 的 Basic 网关凭据不能用于签到。 仅在 OFFICEACE_TOKENS 为空时使用全部五个兼容单账号变量。
- 填写格式：`网关地址`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OFFICEACE_DRY_RUN`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：开启完全离线预演，不调用业务和通知组件。
- 填写格式：`1、true、yes、on 开启，默认关闭`

#### `OFFICEACE_RETRIES`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：设置幂等奖励请求的额外重试次数。
- 填写格式：`0 到 5 的整数，默认 2`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：使用青龙已有通知配置，默认开启。
- 填写格式：`0、false、no、off 关闭，默认 1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：可选指定青龙 notify.py 所在目录，默认使用标准青龙位置或 notify 模块。
- 填写格式：`目录路径`

#### `NO_NOTIFY`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：旧版兼容通知关闭开关。
- 填写格式：`1、true、yes、on 关闭全部推送`

#### `QYWX_TOKEN`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从自己的企业微信群机器人配置获取推送密钥。
- 填写格式：`机器人密钥或 webhook 地址，优先于 WECHAT_WEBHOOK`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECHAT_WEBHOOK`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从自己的企业微信群机器人配置获取 webhook，兼容 QYWX_TOKEN。
- 填写格式：`机器人密钥或 webhook 地址`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PLUSPLUS_TOKEN`

- 所属脚本：`scripts/officeace_daily.py`
- 获取或设置：从自己的 PushPlus 管理页面获取推送令牌。
- 填写格式：`推送令牌，通过 HTTPS 投递`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OLE_CONFIG_JSON`

- 所属脚本：`scripts/ole.py`
- 获取或设置：可将既有 token.json 内容复制到此变量，作为旧配置结构兼容输入；配置 OLE_ACCOUNTS 时优先使用后者。
- 填写格式：`JSON 对象，结构为 huaruntong.ole.accounts 数组；数组内保留原账号字段。无需私有文件路径。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `OLE_DRY_RUN`

- 所属脚本：`scripts/ole.py`
- 获取或设置：在青龙环境变量中设置，用于完全断网预演。
- 填写格式：`1、true、yes、on 启用；默认 0。预演不代表真实业务成功。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ole.py`
- 获取或设置：在青龙环境变量中设置全局通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭。断网预演生成摘要并模拟投递，不运行通知模块。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ole.py`
- 获取或设置：如青龙通知模块不在默认路径，将 notify.py 所在目录填入；无需配置即可尝试导入 notify 和青龙常见目录。
- 填写格式：`可选本地目录路径，仅用于青龙通知；不可用或失败不会改变业务退出码。`

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

#### `PSNID`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：可选单账号兼容输入，取自本站 Cookie 的 __Psnine_psnid；规范变量非空时忽略。
- 填写格式：`单账号 psnid，必须配合 SHELL。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHELL`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：可选单账号兼容输入，取自本站 Cookie 的 __Psnine_shell；使用 PSNID 时须显式覆盖此值，不能使用系统默认登录 shell 路径。
- 填写格式：`单账号 shell 凭据，必须配合 PSNID。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PSNINE_DRY_RUN`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：自行设置为 1 启用完全断网预演。
- 填写格式：`1、true、yes、on 启用；默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：青龙全局通知开关；实时运行通过 notify.py 发送，预演仅打印本地摘要以保证断网。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/psnine.py`
- 获取或设置：可选填写青龙现有 notify.py 所在目录；也会尝试直接导入 notify 和青龙标准目录。
- 填写格式：`本地目录路径；通知不可用或失败不改变业务退出码。`

#### `PT_SITE_HDKYL_URL`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；默认使用 https://www.hdkyl.in/attendance.php；仅在站点迁移后填写可信签到页地址。
- 填写格式：`无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。`

#### `PT_SITE_CARPT_URL`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；默认使用 https://carpt.net/attendance.php；仅在站点迁移后填写可信签到页地址。
- 填写格式：`无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。`

#### `PT_SITE_AFUN_URL`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；默认使用 https://www.ptlover.cc/attendance.php；仅在站点迁移后填写可信签到页地址。
- 填写格式：`无内嵌用户名或密码的 HTTPS 完整地址；不允许跨域重定向传递凭据。`

#### `PT_SITES`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：默认运行 hdkyl、carpt、afun。只运行部分站点时，在青龙环境变量中设置要运行的站点键。
- 填写格式：`逗号分隔的站点键，例如 hdkyl,carpt；这是站点选择设置，不是账号分隔符。`

#### `PT_DRY_RUN`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：在青龙环境变量中设为 1 启用完全断网预演。
- 填写格式：`1、true、yes、on 启用；默认实际签到；预演仍校验必需凭据的格式，但不验证真实账号。`

#### `PT_WEBHOOK_URL`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；在自己的飞书、Bark、Server 酱、钉钉、企业微信或自定义推送服务创建推送地址。青龙通知自动发现，不依赖此变量。
- 填写格式：`无内嵌用户名或密码的 HTTPS 完整地址；不要公开其中的推送密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_WEBHOOK_TYPE`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：根据已配置的推送服务填写类型；保留原上游载荷格式。
- 填写格式：`feishu、bark、sct、ding、wx、custom；默认 custom。`

#### `PT_PROXY`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；填写自己已有的 HTTP 或 HTTPS 代理地址；不会下载或启动代理程序。
- 填写格式：`HTTP 或 HTTPS 代理地址，可含代理认证信息；默认直接连接。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_RETRY`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；在青龙环境变量中设置获取页面失败时的最多尝试次数。
- 填写格式：`1 至 10 的整数，默认 3；签到提交超时或业务状态未知时停止自动重试，避免重复提交。`

#### `PT_TIMEOUT`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；按网络状况设置每次请求的超时毫秒数。
- 填写格式：`1000 至 120000 的整数，默认 20000；Webhook 固定 8000 毫秒；青龙通知最多等待 15000 毫秒。`

#### `PT_SAFELINE`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；默认启用上游 SafeLine 云端挑战流程，失败时在浏览器完成验证并更新完整 Cookie。
- 填写格式：`0 关闭，其他值启用；仅向挑战服务发送挑战令牌和浏览器属性，不发送账号 Cookie 或额外认证头。`

#### `PT_EXTRA_HEADERS`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；从本人站点请求中获取必要的额外请求头，通常无需设置。
- 填写格式：`key1:value1|key2:value2；仅在第一个冒号处分割；禁止 Cookie、认证、代理认证、Host、内容长度、Origin、Referer、Content-Type 和伪造来源 IP 等受保护字段。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PT_DEBUG`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；设为 1 显示请求状态码、响应长度和解析步骤。
- 填写格式：`1、true、yes、on 启用；不输出 HTML、表单令牌、Cookie、代理地址或原始响应。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：青龙通知全局开关，默认开启。
- 填写格式：`0、false、no、off 关闭青龙通知及可选 Webhook；其他值开启。断网预演只模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/pt_sign_v5.js`
- 获取或设置：可选；指向本人青龙安装中已有 sendNotify.js 的目录；否则检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；通知模块不可用、失败或超时只记录状态，不改变签到退出码。`

#### `QODER_ACCOUNTS_FILE`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：自行配置私有账号 JSONL 文件的路径；只在显式指定时读取及原子写回轮换令牌，文件权限设为 0600。未设置时完全使用环境变量并仅在内存保存新令牌。
- 填写格式：`可选私有 JSONL 文件路径，内容与 QODER_ACCOUNTS 相同，设置后优先读取此文件作为兼容输入。`

#### `QODER_REGION`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：按本人账号所属地区设置。
- 填写格式：`cn 或 global，默认 cn；账号 region 优先。`

#### `QODER_ACTION`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：按需指定任务动作；也可用命令行 --refresh-only。
- 填写格式：`checkin（默认）查询并领取活动；refresh 仅刷新令牌，仍须显式启用账号。`

#### `QODER_ONLY`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：从账号列表确定需要执行的序号；命令行 --only 的设置优先。
- 填写格式：`可选从 1 开始的正整数，留空表示全部账号。`

#### `QODER_DRY_RUN`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：测试时设为 1。
- 填写格式：`1/true/yes/on 为断网预演，不请求业务或通知接口，不写回文件。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：按青龙通知需求设置，默认开启。
- 填写格式：`0/false/no/off 关闭全部通知；--no-notify 同样关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/qoder_airscript.js`
- 获取或设置：可选填写青龙中含 sendNotify.js 的通知目录；未设置时查找 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`通知模块所在目录，仅用于通知，业务独立运行；模块不存在或投递失败不改变业务退出码。`

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

#### `RACCOON_DRY_RUN`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：预演设置为 1，正式运行不设置或设为 0。
- 填写格式：`1 完全断网、通知模拟、不写台账；0 正式执行。`

#### `RACCOON_STATE_FILE`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，填写脚本运行用户可写的台账路径。
- 填写格式：`默认脚本旁 raccoon_onboarding.json，仅保存令牌哈希和奖励结算时间。`

#### `RACCOON_MAIN_SITE_URL`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：通常无需设置，仅在确认官方站点变化时调整。
- 填写格式：`默认 https://xiaohuanxiong.com；无内嵌凭据、无路径及查询串的 HTTPS 站点。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭；其他非空值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，填写青龙 notify.py 所在目录。
- 填写格式：`目录路径；也尝试导入 notify.send 和标准青龙目录。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，在 PushPlus 管理页面获取推送令牌。
- 填写格式：`单个推送令牌，仅用于通知。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，在 Bark 应用获取推送地址。
- 填写格式：`完整 HTTPS 推送地址，仅用于通知。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECOM_WEBHOOK`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，在企业微信群机器人设置获取 Webhook。
- 填写格式：`完整 HTTPS Webhook 或机器人密钥，仅用于通知。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_WEBHOOK`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，在钉钉机器人设置获取 Webhook。
- 填写格式：`完整 HTTPS Webhook，仅用于通知。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_SECRET`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，在同一钉钉机器人安全设置获取加签密钥。
- 填写格式：`与 DINGTALK_WEBHOOK 配套，仅用于通知签名。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QL_URL`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，填写本人青龙面板 HTTPS 地址，优先配置 notify.py。
- 填写格式：`完整 HTTPS 面板地址，不包含登录凭据。`

#### `QL_TOKEN`

- 所属脚本：`scripts/raccoon_daily.py`
- 获取或设置：可选，从本人青龙合法授权会话获取通知接口令牌，通常只需配置 notify.py。
- 填写格式：`与 QL_URL 配套，仅用于兼容通知接口。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `RAINYUN_DRY_RUN`

- 所属脚本：`scripts/rainyun.py`
- 获取或设置：在青龙环境变量中自行设置，预演时设置为 1。
- 填写格式：`默认 0；设置 1 开启完全断网预演，仅验证参数与执行计划，跳过业务请求和通知实际发送。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/rainyun.py`
- 获取或设置：使用青龙的全局通知开关，默认开启。
- 填写格式：`默认 1；0、false、no、off 关闭通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/rainyun.py`
- 获取或设置：如通知模块不在默认路径，将本机青龙 notify.py 所在目录填入此变量；未配置则尝试导入 notify 并搜索 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本机目录路径，可选。业务脚本不依赖通知模块存在，通知失败保留业务退出码。`

#### `ROUSI_COOKIE`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版凭据兼容输入，每个非空行一个完整 Cookie；不拆分 Cookie 内的 &、@、分号或等号。Token 与 Cookie 为可替换认证方式，无需配对，同一账号请只选一种。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_1`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_2`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_3`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_4`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_5`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_6`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_7`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_8`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_9`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_10`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_11`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_12`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_13`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_14`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_15`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_16`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_17`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_18`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_19`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_TOKEN_20`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_1`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_2`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_3`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_4`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_5`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_6`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_7`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_8`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_9`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_10`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_11`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_12`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_13`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_14`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_15`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_16`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_17`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_18`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_19`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_COOKIE_20`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。规范凭据变量，每个非空行一个账号 Token，可带 Bearer 前缀；禁止用 & 或 @ 分隔账号。已有兼容变量也能独立提供凭据，无需同时配置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版凭据兼容输入，每个非空行一个完整 Cookie；不拆分 Cookie 内的 &、@、分号或等号。Token 与 Cookie 为可替换认证方式，无需配对，同一账号请只选一种。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_1`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_2`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_3`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_4`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_5`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_6`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_7`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_8`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_9`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_10`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_11`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_12`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_13`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_14`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_15`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_16`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_17`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_18`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_19`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_token_20`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，打开浏览器开发者工具的网络面板，查看站内 API 请求头 Authorization，复制 Bearer 后的值；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_TOKEN 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_1`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_2`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_3`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_4`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_5`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_6`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_7`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_8`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_9`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_10`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_11`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_12`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_13`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_14`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_15`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_16`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_17`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_18`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_19`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `rousi_cookie_20`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 https://rousi.pro/，在浏览器开发者工具网络面板中查看站内 API 请求头，复制完整 Cookie；不要分享凭据。
- 填写格式：`小写兼容输入；同名大写变量非空时优先使用大写值。旧版编号兼容输入，解析规则与 ROUSI_COOKIE 相同，每个非空行一个账号；可单独提供凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ROUSI_DRY_RUN`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：在青龙环境变量中自行设置。
- 填写格式：`1、true、yes、on 表示完全断网预演；默认关闭。预演只验证参数和流程，不代表真实业务成功，通知仅模拟。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：在青龙环境变量中自行设置通知开关。
- 填写格式：`默认 1；0、false、no、off 关闭青龙与 PushPlus 通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：填写当前青龙通知模块 sendNotify.js 的所在目录；不设置则尝试标准青龙目录。
- 填写格式：`本机目录路径；仅通知扩展使用，业务不依赖该目录或私有仓库。缺失或失败仅记录，不改变业务退出码。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：登录 PushPlus 官方服务，在账号页面获取自己的推送令牌。
- 填写格式：`一个推送令牌，用于可选 HTTPS 通知，不是 Rousi 账号凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `pushplus_token`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：与 PUSHPLUS_TOKEN 相同，从 PushPlus 官方服务获取。
- 填写格式：`旧版小写兼容输入，PUSHPLUS_TOKEN 非空时优先使用大写变量。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PUSHPLUS_TYPE`

- 所属脚本：`scripts/rousi_checkin.js`
- 获取或设置：根据自己的 PushPlus 推送渠道设置。
- 填写格式：`默认 wechat；兼容 pushplusvip、wxgo、qywxgo、email、feishu、dingtalk、bark，其余值按上游使用 send。`

#### `SF_CONFIG`

- 所属脚本：`scripts/sf.py`
- 获取或设置：可选兼容输入：显式填写自己旧 token.json 文件的位置，不依赖上游项目目录；SF_ACCOUNTS 非空时优先使用。
- 填写格式：`文件路径，文件结构为 sf.accounts 数组，沿用 sign、channel、device_id、user_agent、account_name 字段。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SF_TASK_CODES`

- 所属脚本：`scripts/sf.py`
- 获取或设置：在自己的积分任务列表响应 taskTitleLevels 中读取 taskCode，或从 buttonRedirect 的 _ug_view_param 中读取 taskId。先确认任务仅为允许的日常积分动作；不可加入花费积分、下单、修改资料或发布内容任务。
- 填写格式：`逗号分隔任务代码，默认空；空时仅签到、任务查询和积分查询。非日常任务始终跳过。`

#### `SF_DRY_RUN`

- 所属脚本：`scripts/sf.py`
- 获取或设置：青龙环境变量中设为 1 启用断网预演。
- 填写格式：`1 启用；0、false、no、off 或空值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sf.py`
- 获取或设置：青龙全局通知开关，默认 1。断网预演只记录本地脱敏通知汇总，以保证不联网。
- 填写格式：`0、false、no、off 或空值关闭；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sf.py`
- 获取或设置：可选指定青龙 notify.py 所在目录；否则尝试导入 notify，再检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地目录路径；通知缺失或失败不改变业务退出码。`

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

#### `SGS_TASKS`

- 所属脚本：`scripts/sgs.py`
- 获取或设置：按需要在青龙配置；默认 info,sign。阅读与服务、活动计数需要显式开启。
- 填写格式：`逗号分隔，无重复：info（账号信息）、sign（签到）、read（最多五篇阅读）、service（五次服务计数）、activity（五次活动计数）。`

#### `SGS_DRY_RUN`

- 所属脚本：`scripts/sgs.py`
- 获取或设置：设置为 1 进行断网预演；正式运行设为 0 或删除。
- 填写格式：`1、true、yes、on 开启，其他值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sgs.py`
- 获取或设置：默认调用青龙通知模块；需要关闭时设置为 0。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sgs.py`
- 获取或设置：可填写现有 notify.py 所在目录；也自动查找青龙标准目录。
- 填写格式：`本机通知模块目录，无需业务仓库或安装器。`

#### `SHUYI_DRY_RUN`

- 所属脚本：`scripts/shuyi.py`
- 获取或设置：在青龙环境变量中设置；验证时填 1，实际执行填 0 或不设置。
- 填写格式：`1、true、yes、on 表示完全断网预演，其他值表示实际执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/shuyi.py`
- 获取或设置：青龙通知默认开启；需要关闭时设置为 0。
- 填写格式：`0、false、no、off 关闭；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/shuyi.py`
- 获取或设置：可选，填写自己青龙实例中 notify.py 所在目录；默认尝试导入 notify 并查找青龙标准脚本目录。
- 填写格式：`本机通知模块目录路径；业务功能不依赖此目录。`

#### `PUSH_PLUS_TOKEN`

- 所属脚本：`scripts/shuyi.py`
- 获取或设置：可选，登录自己的 PushPlus 控制台获取推送令牌；仅用于既有可选通知，不作为业务凭据。
- 填写格式：`单个 PushPlus 令牌；不设置则不请求该推送接口。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KANXUE_CONFIG`

- 所属脚本：`scripts/sign_in.py`
- 获取或设置：仅用于迁移已有 token.json，指定自己保管的文件路径；无需原仓库。KANXUE_ACCOUNTS 非空时优先使用账号变量。
- 填写格式：`本地文件路径；文件含 kanxue.accounts 或 kanxue.kanxue.accounts 数组，每个对象包含 cookie、csrf_token，可选 user_agent、account_name。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KANXUE_DRY_RUN`

- 所属脚本：`scripts/sign_in.py`
- 获取或设置：在青龙环境变量中设置为 1 开启完全离线预演；正式执行设置为 0。
- 填写格式：`1 开启，0、false、no、off 或空值关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sign_in.py`
- 获取或设置：默认开启青龙通知；如需关闭，在青龙环境变量设置为 0。预演只模拟通知，不调用通知模块。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sign_in.py`
- 获取或设置：若 notify.py 无法直接导入且不在青龙标准脚本目录，可指定自己信任的通知模块目录。无需安装其他仓库；通知不可用不影响业务退出码。
- 填写格式：`包含 notify.py 的本地目录路径。`

#### `SKLAND_PHONE`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：兼容旧输入，填写本人鹰角通行证手机号，建议迁移至 SKLAND_TOKEN 单行 JSON。
- 填写格式：`与 SKLAND_PASSWORD 成对设置，一个账号；不能用作多账号分隔输入。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_PASSWORD`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：兼容旧输入，填写本人鹰角通行证密码，建议迁移至 SKLAND_TOKEN 单行 JSON。
- 填写格式：`与 SKLAND_PHONE 成对设置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_TOKEN_N`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：兼容旧序号输入，获取方式同 SKLAND_TOKEN；N 替换为数字。
- 填写格式：`每个序号变量仍按非空行解析账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_PHONE_N`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：兼容旧序号输入，填写本人鹰角通行证手机号；N 替换为数字。
- 填写格式：`与同序号 SKLAND_PASSWORD_N 成对设置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_PASSWORD_N`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：兼容旧序号输入，填写本人鹰角通行证密码；N 替换为数字。
- 填写格式：`与同序号 SKLAND_PHONE_N 成对设置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_DID`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：从本人森空岛官方客户端请求头获取 dId；不填写时沿用维护版本的临时设备标识注册功能，值仅保存在内存。
- 填写格式：`单个设备标识，不输出到日志。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_ACTIONS`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：按需要选择任务，默认 checkin,view；like、share、attendance、endfield 须显式添加。
- 填写格式：`逗号分隔 checkin、view、like、share、attendance、endfield；attendance 仅明日方舟，endfield 仅终末地；原源游戏签到可设置 attendance,endfield。`

#### `SKLAND_ZONE_IDS`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：从官方版区列表接口读取 gameId，不设置时处理全部社区版区。
- 填写格式：`逗号分隔版区编号；只筛选社区动作，不筛选游戏签到角色。`

#### `SKLAND_VIEW_COUNT`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：按需要配置每个版区的浏览数量，默认 5。
- 填写格式：`非负整数。`

#### `SKLAND_LIKE_COUNT`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：按需要配置每个版区的点赞数量，默认 10，只有显式选择 like 才生效。
- 填写格式：`非负整数。`

#### `SKLAND_SHARE_COUNT`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：按需要配置每个版区的分享任务计数，默认 1，只有显式选择 share 才生效。
- 填写格式：`非负整数；接口只计数，不发布文本。`

#### `SKYLAND_TYPE`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：历史兼容变量，无业务效果，无需设置。
- 填写格式：`不参与任务选择。`

#### `SKLAND_NOTIFY_URL`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：可选本人维护的 HTTPS 通知服务地址，正式运行发送脱敏摘要；与青龙通知模块兼容。
- 填写格式：`HTTPS 地址，禁止重定向和 URL 用户名密码；不得填写账号凭据。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_DRY_RUN`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：预演时设置为 1，也支持 --dry-run 参数。
- 填写格式：`1、true、yes、on 启用完全断网预演，默认关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：青龙通知总开关，默认 1；预演只生成本地脱敏摘要，不调用网络通知。
- 填写格式：`0、false、no、off 关闭；其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/skland_daily.py`
- 获取或设置：填写青龙 notify.py 所在目录；可省略以自动查找 notify 模块及青龙标准目录。
- 填写格式：`目录路径；通知模块不可用、超时或失败时保留业务退出码。`

#### `TOKEN`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：旧版通行证环境变量兼容入口，获取方法同 SKLAND_ACCOUNTS；仅在规范变量为空时采用。
- 填写格式：`每个非空行一个通行证或单行 JSON；旧版逗号分隔需改为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SKLAND_ACTION`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：按需要设置；定时任务默认 sign。
- 填写格式：`sign：登录并签到；send-code：显式发送短信，不签到。`

#### `SKYLAND_TYPE`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：旧版动作变量兼容，仅在 SKLAND_ACTION 未设置时采用。
- 填写格式：`sign 或 send-code；add_account 已移除，不再保存凭据文件。`

#### `SKLAND_GAMES`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：根据绑定游戏选择，默认同时签到两款游戏。
- 填写格式：`arknights,endfield，或其中任意一个；逗号仅用于游戏选项。`

#### `SKLAND_REFRESH`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：需要主动刷新签名令牌时设置，默认关闭。
- 填写格式：`1 开启；0、false、no、off 关闭。`

#### `SKLAND_DRY_RUN`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：验证配置时设置为 1，预演不代表真实业务成功。
- 填写格式：`1 开启断网预演；默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：青龙全局通知开关，默认启用；预演也准备并尝试发送脱敏总结，但网络连接被禁止。
- 填写格式：`0、false、no、off 关闭；默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/skland_demo.py`
- 获取或设置：仅当青龙通知模块不在默认路径或导入路径时，填写现有 notify.py 所在目录。
- 填写格式：`本地目录路径；通知不可用不影响业务退出码。`

#### `SKYLAND_DRY_RUN`

- 所属脚本：`scripts/skyland.py`
- 获取或设置：在青龙环境变量中设置为 1 开启完全断网预演。
- 填写格式：`1、true、yes、on 开启，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/skyland.py`
- 获取或设置：青龙通知默认开启；需要关闭时设置为 0。
- 填写格式：`0、false、no、off 关闭，默认 1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/skyland.py`
- 获取或设置：可选，填写青龙已有 notify.py 所在目录；默认发现青龙标准路径或导入 notify.send，无通知模块仍可执行签到。
- 填写格式：`本地通知模块目录路径。`

#### `SMZDM_COOKIE_LIST`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：兼容原固定抽奖变量；从本人已登录什么值得买网页请求头复制完整 Cookie。
- 填写格式：`每个非空行一个完整 Cookie，必须含 sess；固定活动模式下优先于其他旧 Cookie 变量。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_COOKIE`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：旧变量兼容入口；从本人已登录网页或客户端请求头获取完整 Cookie。
- 填写格式：`每个非空行一个完整 Cookie，至少含 sess；客户端签到另配同顺序 SMZDM_SK，或 Cookie 内带 sk。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_COOKIES`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：旧复数变量兼容入口；从本人已登录网页或客户端请求头获取完整 Cookie。
- 填写格式：`每个非空行一个完整 Cookie；可用 # 开头的注释行；客户端签到另配配套 sk。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_SK`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：从本人客户端签到请求取得 sk，与旧 Cookie 变量的账号逐行对应；不使用他人或共享默认值。
- 填写格式：`每个非空行一个 sk；需要 sk 时行数须与旧 Cookie 账号数相同。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_ACTION`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：按需要在青龙环境中选择；默认 checkin，不自动执行转盘或固定活动。
- 填写格式：`checkin：签到；lottery：既有会员转盘；all：签到和既有会员转盘；upstream-lottery：仅原固定活动一次抽奖。固定活动原调度为 45 0 15 * * *，会员转盘原独立调度为 20 8 * * *，需在相应任务环境中选择模式。`

#### `SMZDM_TOKEN_MODE`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：保留默认 sess；需要原 Robot Token 或网页 Cookie 签到时显式选择。
- 填写格式：`sess、robot 或 web；默认 sess。网页模式无需 sk。`

#### `SMZDM_INTERACTION`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：仅希望执行点赞或点值时开启；默认不互动。
- 填写格式：`none、value、article 或 both；默认 none，每类最多七条，原互动调度 29 0-23/8 * * * 可自定义。`

#### `SMZDM_LOTTERY_LIFE`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：显式启用原生活频道入口；仅影响 lottery 或 all，不影响固定活动模式。
- 填写格式：`1、true、yes、on 启用；默认关闭。`

#### `SMZDM_USER_AGENT_APP`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：可从本人什么值得买请求头复制客户端 User-Agent；不要填入凭据或设备标识。
- 填写格式：`可选请求头字符串；未配置时使用各模式既有客户端配置。`

#### `SMZDM_DRY_RUN`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：验证配置时设为 1，完全离线，不调用任何联网通知组件。
- 填写格式：`1、true、yes、on 启用；默认正式执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：青龙全局通知开关；未配置时尝试青龙通知，失败后保留既有推送回退。
- 填写格式：`默认 1；0、false、no、off 关闭。离线预演仅生成脱敏通知摘要。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：可指定青龙已有 sendNotify.js 所在目录；也会查找青龙标准脚本目录。
- 填写格式：`可选目录；组件缺失或发送失败只记录通知状态，不改变业务退出码。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：在本人 PushPlus 账户取得推送令牌，仅用于青龙通知不可用或失败时回退。
- 填写格式：`可选推送令牌，受 QINGLONG_NOTIFY 控制。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SENDKEY`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：在本人 Server酱账户取得 SendKey，仅用于前两种通知不可用或失败时回退。
- 填写格式：`可选推送密钥，受 QINGLONG_NOTIFY 控制。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CF_API_TOKEN`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：兼容旧版单账号：在 Cloudflare 个人资料创建具有区域 DNS Read 权限的 API Token。SSL_ACCOUNTS 非空时忽略旧版变量。
- 填写格式：`单账号令牌，优先于 CF_API_EMAIL 和 CF_API_KEY`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CF_API_EMAIL`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：兼容旧版：填写 Cloudflare 登录邮箱，必须与 CF_API_KEY 属于同一账号。
- 填写格式：`单账号邮箱；无需与令牌同时填写`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CF_API_KEY`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：兼容旧版：在 Cloudflare 个人资料获取 Global API Key，与 CF_API_EMAIL 配套。
- 填写格式：`单账号全局密钥`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CF_ZONE_IDS`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：兼容旧版：各区域概览页面的 Zone ID；使用旧版认证时必填。
- 填写格式：`逗号分隔32位十六进制标识，与 CF_DOMAINS 顺序对应`

#### `CF_DOMAINS`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：兼容旧版：填写各区域的主域名；使用旧版认证时必填。
- 填写格式：`逗号分隔主域名，与 CF_ZONE_IDS 顺序对应`

#### `SSL_WARNING_DAYS`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：自行设置证书到期警告阈值，默认保留上游30天。
- 填写格式：`非负整数；警告证书通过验证则检查成功，过期或检查失败返回非零`

#### `SSL_DRY_RUN`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：设置为1执行完全断网预演，配置仍须完整；不验证实际凭据或证书。
- 填写格式：`1、true、yes、on 启用，默认关闭`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：青龙通知全局开关，默认1；断网预演只生成摘要并记录通知预览。
- 填写格式：`0、false、no、off 关闭，其他值启用`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ssl.py`
- 获取或设置：可选：填写青龙已有 notify.py 所在目录；否则自动发现标准青龙位置或可导入的 notify 模块。
- 填写格式：`本地通知目录；不影响独立业务运行，通知失败不更改业务退出码`

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

#### `ALL_GIRLS_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录所有女生，在本人 https://7.wawo.cc/api/account/wx/member/base 请求中获取authorization 请求头中 bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `AMX_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录安慕希，在本人 https://amxshop.yili.com/api/user/getUser 请求中获取accesstoken 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BW_TEA_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录霸王茶姬，在本人 https://webapi2.qmai.cn/web/catering2-apiserver/crm/customer-center?appid=wxafec6f8422cb357b 请求中获取qm-user-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `FN_NAS_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录飞牛私有云，在本人 https://club.fnnas.com 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `GYJ_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录国乐酱酒，在本人 https://member.guoyuejiu.com/api/user/info 请求中获取Authorization 请求头完整值（保留认证前缀）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HGF_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录厚工坊，在本人 https://api.hgf1862.com/YUN//Game/2021/QianDao/QianDaoAjax_By28.aspx?op=now&vers= 请求中获取Cookie 中 user=SessionID= 后的会话值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HLZJ_UNID`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录海澜之家-游戏，在本人 https://gmdevpro.hlzjppgl.cn/server/api/authorized-login 请求中获取请求体 union_id；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `HZHFP_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录媓钻护肤品，在本人 https://servicewechat.com/wx3df7476c42cace5d/377/page-frame.html 请求中获取Authorization 请求头 Bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `INSTAX_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录玩拍由我俱乐部，在本人 https://instax.app.xcxd.net.cn/api/me 请求中获取Authorization 请求头 Bearer 后的 token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JINDIAN_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录金典有机生活+，在本人 https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info 请求中获取access-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JLC_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录嘉立创，在本人 https://m.jlc.com/api/appPlatform/center/setting/selectPersonalInfo 请求中获取x-jlc-accesstoken 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KOZBS_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录植白说官方商城，在本人 https://www.kozbs.com/demo/wx/user/getUserIntegral 请求中获取x-dts-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KTGZS_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录开天工作室，在本人 https://api.box.vipinfinity.com/user 请求中获取Authorization 请求头完整值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KURO_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录库街区，在本人 https://api.kurobbs.com/gamer/widget/game3/refresh 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LAOBAN_OPENID`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录老板电器服务微商城，在本人 https://vip.foxech.com/index.php/api/member/get_member_info 请求中获取请求体 openid；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `LONG_FOR_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录龙湖天街，在本人 https://gw2c-hw-open.longfor.com/riyuehu-miniapp-prod/service/ryh/user/info 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MALLCOO_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录欣都龙城，在本人 https://m.mallcoo.cn/api/user/user/GetUserAndMallCard 请求中获取JSON 请求体 Header.Token；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MAWUW_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录馬伍旺饮料厂，在本人 https://webapi.qmai.cn/web/catering/crm/customer-center?appid=wxc1381dc6f2213b72 请求中获取qm-user-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号；兼容 token#附加字段，首个 # 前为 token`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MIDEA_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录美的会员，在本人 https://mvip.midea.cn/next/mucuserinfo/getmucuserinfo 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `MOTO_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录摩托范，在本人 https://api.58moto.com/user/center/info/v2/principal 请求中获取请求头 token 与请求体 uid；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：`token#uid，只在首个 # 分割`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `NFHK_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录南方航空，在本人 https://wxapi.csair.com/marketing-tools/activity/join?type=APPTYPE&chanel=ss&lang=zh 请求中获取Cookie 中 sign_user_token 的值（须与 TOKEN、cs1246643sso 同属该账号）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PANG_GE_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录胖哥俩肉蟹煲，在本人 https://servicewechat.com/wxe61905cae01a6c7d/67/page-frame.html 请求中获取token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PPX_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录皮皮世界，在本人 https://api.pipix.com/bds/user/user_profile/ 请求中获取Cookie 中 sessionid 的值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SHUI_FEI_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录水费易签到，在本人 https://m.ipaiyun.cn/PersonalCenter/PersonalCenter/GetShopMemberDetail 请求中获取请求头 Cookie 与请求体 memberId；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：`Cookie#memberId，只在首个 # 分割`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TEBU_JSON`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录特步会员中心，在本人 https://servicewechat.com/wx12e1cb3b09a0e6f0/121/page-frame.html 请求中获取完整认证请求头（JSON 对象）；通过授权抓包或浏览器开发者工具查看，勿分享凭据。
- 填写格式：`一行一个认证请求头 JSON 对象`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIE_BA_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录贴吧签到，在本人 https://tieba.baidu.com/dc/common/tbs 请求中获取完整 Cookie（普通接口也接受单独 BDUSS；任务接口需要 CUID）；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `V2EX_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录V2EX每日签到，在本人 https://www.v2ex.com 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XINXI_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录心喜，在本人 https://api.xinc818.com/mini/user 请求中获取sso 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XPFARM_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录兴攀农场，在本人 https://p.xpfarm.cn/treemp/user.PersonalCenter/getInfo 请求中获取authorization 请求头完整值；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZNDS_COOKIE`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录智能电视，在本人 https://www.znds.com/ 请求中获取完整 Cookie 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZX_ICE_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：兼容输入：登录甄稀冰淇淋，在本人 https://msmarket.msx.digitalyili.com/gateway/api/auth/account/user/info 请求中获取access-token 请求头；使用本人授权抓包或开发者工具查看，不分享凭据。
- 填写格式：`每行一个账号的完整凭据，不使用 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ENABLE_CHECK_TOKEN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：手动设置为 true 才进行在线检查；预演无需开启
- 填写格式：`true 开启；默认关闭`

#### `AUTH_CHECK_DRY_RUN`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：手动设置为 1
- 填写格式：`1 为断网预演；默认关闭`

#### `AUTH_CHECK_ALLOW_MUTATIONS`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：仅在理解登录、刷新、同步和活动参与风险后开启；缺少成功证据的三项检查仍拒绝执行
- 填写格式：`true 显式允许；默认关闭`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：使用青龙全局通知开关
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_authcheck.js`
- 获取或设置：可选，使用青龙已有通知模块所在目录，不安装或下载模块
- 填写格式：`含 sendNotify.js 的本地目录`

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

#### `OSHW_COOKIE`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：按 JLC_COOKIE 的方法获取；原 Python 脚本变量兼容输入。
- 填写格式：`每行一个完整 Cookie；仅在 JLC_COOKIE 未设置时使用；忽略以 # 开头的注释行`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JLC_TOKEN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：登录 https://m.jlc.com/mapp/ 或嘉立创下单助手小程序，在 m.jlc.com 已登录请求头复制 x-jlc-accesstoken 和 secretkey。JLC_TASKS=mapp 或 all 时此项必填。
- 填写格式：`令牌#密钥，每行一个账号；只在第一个 # 切分，保留密钥后续字符；不以 & 或 @ 分隔账号`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `JLC_TASKS`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：按需选择流程；默认 oshwhub。保留维护版调度 44 5 * * *；原 Python 调度 10 8 * * * 可为同文件设置；下单助手原调度 30 6 * * * 可为同文件设置并选择 mapp。
- 填写格式：`oshwhub、mapp 或 all，两套流程凭据独立`

#### `JLC_CLAIM_REWARD`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：确认下单助手 receiveVoucher 默认奖励语义后手动设置为 1；默认 0，不擅自选择奖励。
- 填写格式：`0 或 1；未授权待选奖励则任务未完成并非零退出；领取后最多补签一次`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：按需开启开源平台签到前随机等待；维护版默认 false；兼容原 Python 参数。
- 填写格式：`true 或 false；已签到不等待；预演不等待`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：启用 RANDOM_SIGNIN 时设置最大随机等待秒数；默认 1800。
- 填写格式：`0 至 1800 的整数秒，仅启用延迟时校验`

#### `JLC_YJ_DRY_RUN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：设置为 1 启用完全断网预演。
- 填写格式：`1 为预演，其他值为正式运行`

#### `JLC_DRY_RUN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：维护版离线开关兼容输入。
- 填写格式：`1 为完全断网预演`

#### `OSHW_DRY_RUN`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：开源平台离线开关兼容输入。
- 填写格式：`1 为完全断网预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：默认开启青龙通知；按需关闭。
- 填写格式：`0、false、no、off 关闭，不区分大小写；其他值开启`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_jlc_yj.js`
- 获取或设置：可选指定青龙 sendNotify.js 所在目录；同时自动检查 /ql/data/scripts 和 /ql/scripts。
- 填写格式：`本地通知模块目录；通知失败不改变业务退出码`

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

#### `V2EX_PROXY`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：从自己的代理服务获取 HTTP 或 HTTPS 代理地址。可省略；原 Python 配置中的 proxy 可迁移到账号 JSON 的 proxy 字段。青龙依赖管理安装公开 npm 包 https-proxy-agent 7.x，脚本不自动安装。
- 填写格式：`HTTP/HTTPS URL，可含代理认证；账号 JSON 的 proxy 优先于全局值，显式空字符串表示直连。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `V2EX_DRY_RUN`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：在青龙环境变量中设为 1 开启完全断网预演。
- 填写格式：`1 为预演，其他值为正式运行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：青龙全局通知开关，默认 1；预演只模拟通知。
- 填写格式：`0、false、no、off 关闭通知，大小写不敏感。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_v2ex.js`
- 获取或设置：可指定青龙 sendNotify.js 所在目录；未配置时搜索 /ql/data/scripts 和 /ql/scripts。通知模块缺失或发送失败不会改变业务退出码。
- 填写格式：`可选目录路径，仅用于通知，不影响独立 HTTP 业务。`

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

#### `xx_sso`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：旧脚本凭据变量，获取方式与 XINXI_TOKEN 相同；仅当 XINXI_TOKEN 未设置时生效。
- 填写格式：`每个非空行一个完整 sso；旧 # 分隔需迁移为换行。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `XINXI_DRY_RUN`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设为 1 启用完全断网预演，通知仅生成预览。
- 填写格式：`0 或 1，默认 0。`

#### `XINXI_FREE_DRAW`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设为 1 启用最多一次免费抽奖，不执行积分抽奖。
- 填写格式：`0 或 1，默认 0。`

#### `XINXI_REWARD_TASKS`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设为 1 启用分享任务记账和商城浏览奖励，各最多两次，浏览提交前等待三十秒。
- 填写格式：`0 或 1，默认 0。`

#### `XINXI_DAILY_TASKS`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设为 1 查询每日任务，不自动执行返回的任务。
- 填写格式：`0 或 1，默认 0。`

#### `XINXI_MEMBER_BENEFITS`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：设为 1 查看会员权益并领取任务奖励。
- 填写格式：`0 或 1，默认 0。`

#### `xx_del_topic`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：旧批量删除开关；本维护版禁止批量删帖，设为 1 时以配置错误退出。
- 填写格式：`移除该变量或设为 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：青龙全局通知开关，默认开启。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/sudojia_xinxi.js`
- 获取或设置：可选，填写青龙已有 sendNotify.js 所在目录；不配置时使用青龙标准目录。
- 填写格式：`本地通知模块目录路径。`

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

#### `ROW_URL`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：旧配置 ROW_URL 的可选兼容输入；优先使用 WEIBO_SUPERTOPIC_ACCOUNTS。
- 填写格式：`与规范变量相同，每行一个账号；原分号账号格式需要改为换行`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `IS_SORT`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：手动选择超话签到排序；原配置默认值未提供，本版本默认保持接口顺序。
- 填写格式：`NONE、INCREASE（等级升序）或 DECREASE（等级降序）`

#### `SIGN_ONCE_COUNT`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：手动设置每账号本次签到请求次数上限；已签到项不占用次数。达到上限仍有待签项时以非零退出，避免误报全量成功。
- 填写格式：`非负整数，默认 0 表示不限`

#### `WEIBO_SUPERTOPIC_DRY_RUN`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：设置为 1 进行完全离线预演，使用模拟列表，不验证真实凭据，不发送通知网络请求。
- 填写格式：`默认 0；0、false、no、off 为关闭`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：青龙通知全局开关；实网运行在所有结果后调用可用的 notify.py/send，通知失败保留业务退出码。
- 填写格式：`默认 1；0、false、no、off 为关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/supertopicsign.py`
- 获取或设置：可选填写青龙 notify.py 所在目录；也自动检查 Python 导入路径及 /ql/data/scripts、/ql/scripts。
- 填写格式：`本地目录路径`

#### `SYNSPOINT_DRY_RUN`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：设置为 1 开启断网预演，业务请求和通知发送均不执行。
- 填写格式：`默认 0；1/0、true/false、yes/no、on/off`

#### `SYNSPOINT_APPOINTMENT`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：仅确有预约需求且活动有效时设置为 1，显式开启上播预约及取消流程。默认关闭原随机预约副作用。
- 填写格式：`默认 0；1/0、true/false、yes/no、on/off`

#### `SYNSPOINT_ACTIVITY_ID`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：从小程序本人请求 /api/live/wx/strategy/appointment 的 activityId 字段获取，不猜测当前活动。
- 填写格式：`正整数；沿用原始活动默认值 818，旧活动可能已失效。`

#### `SYNSPOINT_GOODS_ID`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：从同一活动预约请求的 goodsId 字段获取；不填时沿用原始 56 项商品列表随机选取。
- 填写格式：`正整数；可选，不影响默认关闭预约。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：青龙全局通知开关，按个人需要设置。
- 填写格式：`默认 1；0、false、no、off 关闭；断网预演只模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/synspoint.py`
- 获取或设置：可选，填写青龙 notify.py 或 sendNotify.js 所在目录；不填时自动发现 notify 模块及标准青龙脚本目录。
- 填写格式：`本地目录路径，不作为业务运行依赖。`

#### `TENCENT_VIDEO_COOKIE`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：与规范变量获取方式相同；仅在 TENCENT_VIDEO_COOKIES 为空时使用，兼容旧单账号配置。
- 填写格式：`完整 Cookie；也按每行一个账号解析。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TENCENT_VIDEO_DRY_RUN`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：在青龙环境变量中设置，用于断网验证配置。
- 填写格式：`1/true/yes/on 开启预演，默认实际执行。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：按需在青龙环境变量中设置，控制全部通知渠道。
- 填写格式：`默认 1；0/false/no/off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：可选：填写青龙已有 notify.py 或 sendNotify.js 所在目录；默认发现标准路径。
- 填写格式：`已有通知模块的目录路径；业务运行不依赖此目录。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：从 PushPlus 官网个人中心取得推送令牌；青龙通知不可用时尝试。
- 填写格式：`单个推送令牌，与账号 Cookie 分开配置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SENDKEY`

- 所属脚本：`scripts/tencent_video_checkin.py`
- 获取或设置：从 Server酱官网取得 SendKey；青龙及 PushPlus 不可用时尝试。
- 填写格式：`单个 SendKey，与账号 Cookie 分开配置。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIE_BA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：旧变量兼容入口，获取方式同 TIEBA_COOKIE；TIEBA_COOKIE 非空时优先使用它。
- 填写格式：`每个非空行一个完整 Cookie 或 BDUSS 单值；成长任务需包含 BDUSS 与 CUID。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_GROWTH_TASKS`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：按需手动设置；默认关闭。只有明确开启并具有同账号 BDUSS 与 CUID 时提交成长任务，启用后字段缺失计为账号失败，逐吧签到仍独立执行。
- 填写格式：`1、true、yes、on 开启，其他值关闭。`

#### `TIEBA_DRY_RUN`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：手动设为 1 开启完全断网配置预演。
- 填写格式：`1、true、yes、on 开启；默认关闭。`

#### `TIEBA_VERBOSE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：手动开启逐吧名称及结果日志，默认关闭。
- 填写格式：`1、true、yes、on 开启。`

#### `TIEBA_DELAY_MS`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：按需设置逐吧请求间隔，默认 1200 毫秒。
- 填写格式：`整数毫秒；限制在 500 至 10000；格式错误沿用默认值。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：青龙全局通知开关，默认开启。断网预演仅生成并展示脱敏通知汇总，不加载可能联网的通知组件。
- 填写格式：`0、false、no、off 关闭，其他值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：可选填写青龙 notify.py 所在目录；自动尝试导入 notify.send 及标准青龙目录。
- 填写格式：`本地目录路径；仅作为可选通知组件位置，业务功能不依赖此文件。`

#### `TJD_TOKEN`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：本人 App 请求头 Authorization；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_DEVICEID`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：与 Authorization 相同请求的 deviceid 头，此变量在脚本中实际读取；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_UID`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：同一请求的 uid 头，缺省为 0；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`

#### `TJD_NAME`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：自行设置账号标签，仅用于 --account 过滤；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`

#### `TJD_PHONE`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：本人完美世界账号手机号；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_PASSWORD`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：本人完美世界账号密码；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_OPENUDID`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：同一设备登录请求 openudid；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_VENDORID`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：同一设备登录请求 vendorid；旧变量兼容输入，优先使用 TJD_ACCOUNTS。
- 填写格式：`每行一个值，按 TJD_TOKEN 账号顺序对齐；不使用 & 分隔。缺少 deviceid 时该账号失败。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TJD_TASKS`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：在青龙环境变量中设置，点赞和分享必须明确选择。
- 填写格式：`逗号分隔 signin、gamesign、browse、like、share、status；默认 signin,gamesign,browse；--only 优先。`

#### `TJD_SHARE_PLATFORM`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：自行选择分享回调平台。
- 填写格式：`qq、wechat、timeline 或 wb；默认 qq，不发布文字。`

#### `TJD_DRY_RUN`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：设置为 1 进行完全断网预演。
- 填写格式：`1 启用；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：青龙全局通知开关。
- 填写格式：`默认 1；0、false、no、off 禁用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tjd_daily.py`
- 获取或设置：填写青龙 notify.py 所在目录，也自动查找标准青龙目录。
- 填写格式：`本地目录路径，通知失败保留业务退出码。`

#### `TRAE_ACCESS_TOKEN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_2`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_2`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_3`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_3`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_4`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_4`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_5`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_5`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_6`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_6`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_7`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_7`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_8`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_8`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_ACCESS_TOKEN_9`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号访问令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个访问令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_REFRESH_TOKEN_9`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方客户端取得同账号刷新令牌；未设置 TRAE_ACCOUNTS 时读取，与相同后缀的配套凭据对应。建议迁移到每行一个 JSON 的 TRAE_ACCOUNTS。
- 填写格式：`单个刷新令牌；账号后缀为无后缀或 _2 至 _9；不使用分隔符拼接多个账号。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_SESSION`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：在本人网页登录后的开发者工具中复制 X-Cloudide-Session 的 Value；优先使用 TRAE_ACCOUNTS 的 session 字段。
- 填写格式：`每行一个账号的单个 Cookie Value；与 TRAE_SESSIONID 行数相同且同账号对应，不填整个 Cookie 请求头。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_SESSIONID`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：在本人网页登录后的开发者工具中复制 sessionid 的 Value；优先使用 TRAE_ACCOUNTS 的 sessionid 字段。
- 填写格式：`每行一个账号的长效 Cookie Value；与 TRAE_SESSION 同行配对，不填请求头。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_DEVICE_ID`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容或显式 login 必需：从本人同账号客户端 storage.json 的 iCubeAuthInfo://icube-dc:<数字> 键取得。多账号优先在 TRAE_ACCOUNTS 中配置独立 deviceId。
- 填写格式：`真实 12 至 20 位数字；单账号无后缀，多账号兼容 _2 至 _9 与令牌对应，禁止生成或共享其他账号设备。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_UID`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：从本人官方登录响应取得公开用户编号；优先填账号 JSON 的 uid。
- 填写格式：`单个公开用户编号；兼容 _2 至 _9 的账号后缀。`

#### `TRAE_NAME`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：本人自定义非敏感账号名称，用于筛选；不填写手机号或凭据。
- 填写格式：`单个名称；兼容 _2 至 _9 的账号后缀。`

#### `TRAE_ICUBE_AUTH`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：本人客户端 storage.json 的 iCubeAuthInfo://icube.cloudide 值；仅显式提供时解密，不扫描客户端。
- 填写格式：`单账号明文 JSON 或原始加密值；加密值需要公共包 cryptography。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_STORAGE_PATH`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选旧参数兼容：本人主动上传的 storage.json 的明确路径；无需安装桌面客户端。
- 填写格式：`单个文件路径；仅读取，不改写源文件；预演禁止读取。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_AUTH_DIR`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：主动上传本人 auth-*.json 文件的目录；或显式 login 保存的位置。
- 填写格式：`目录路径；签到只有显式设置时读取；login 默认脚本目录 auths；预演禁止读取。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_DEVICE_KEY_PEM`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：本人设备配套 P-256 私钥；多账号建议放账号 JSON 的 deviceKeyPem。
- 填写格式：`PEM 字符串，支持字面量换行转义；与公钥及设备号配套。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_DEVICE_PUB_PEM`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：本人同设备 P-256 公钥；建议放账号 JSON 的 devicePubPem。
- 填写格式：`PEM 字符串；须与私钥配套，不能仅设置一个。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_MACHINE_ID`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：从本人同设备登录信息取得；多账号建议放账号 JSON 的 machineId。
- 填写格式：`单个设备绑定标识；显式 login 未设置时为本次授权生成，不输出。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_DEVICE_BRAND`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：从本人同设备官方登录请求取得设备品牌；设备指纹需与凭据一致。
- 填写格式：`单个字符串；未设置保留维护版本自动探测及空值行为。`

#### `TRAE_DEVICE_NAME`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：从本人同设备官方登录请求取得设备名称；设备指纹需与凭据一致。
- 填写格式：`单个字符串；未设置保留维护版本自动探测及空值行为。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_DEVICE_MODEL`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：从本人同设备官方登录请求取得设备型号；设备指纹需与凭据一致。
- 填写格式：`单个字符串；未设置保留维护版本自动探测及空值行为。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_CLIENT_ID`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：与本人凭据配套的官方 IDE 客户端编号；一般保持默认。
- 填写格式：`字符串；默认 ono9krqynydwx5，保留 IDE_PC、SOLO_PC 与旧客户端回退。`

#### `TRAE_TASK`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：按本次目的选择；命令行动作优先。
- 填写格式：`checkin 默认签到和余额；credits 仅查询余额；login 显式交互登录。`

#### `TRAE_LOGIN_TIMEOUT`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：按本机交互登录所需时间设置。
- 填写格式：`30 至 900 的整数秒，默认 300。`

#### `TRAE_DRY_RUN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：测试配置时设为 1；不会联网、读取凭据/缓存文件或写入业务文件。
- 填写格式：`默认 0；0、false、no、off 为正式模式，1 为完全断网预演。`

#### `TRAE_ONLY`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：指定本人要处理的账号，避免误操作其他账号。
- 填写格式：`账号原始序号、uid 或 name；无匹配时报错，默认全部。`

#### `TRAE_BATCH`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：在维护计划中设置每轮处理数。
- 填写格式：`默认 all；0 或 all 为全签，正整数为按北京时间小时轮签；早窗仍全签。`

#### `TRAE_PEAK_HOURS`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：指定北京时间早窗小时。
- 填写格式：`默认 0；逗号分隔小时或范围，如 0-2；仅用于小时配置，不用于账号分隔。`

#### `TRAE_COOLDOWN_MIN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：设置普通时段账号独立限流冷却。
- 填写格式：`1 至 1440 的整数分钟，默认 55。`

#### `TRAE_PEAK_COOLDOWN_MIN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：设置早窗账号独立限流冷却。
- 填写格式：`1 至 1440 的整数分钟，默认 12。`

#### `CLAIM_TRIES`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：显式调整领取次数；一般保留默认一次，冷却后由定时重试。
- 填写格式：`1 至 5 的整数，默认 1；不轮换设备。`

#### `TRAE_CIRCUIT`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：启用旧版全局熔断。
- 填写格式：`默认 0；1 为某账号限流后跳过其余未处理账号，未完成仍非零退出。`

#### `TRAE_JITTER`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：控制维护版本启动错峰。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `TRAE_JITTER_MAX`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：兼容主来源启动错峰上限，不改变维护默认。
- 填写格式：`0 至 86400 的整数秒，默认 20；设 600 可使用上游原错峰上限；预演不等待。`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：兼容 Trae Work 每账号随机等待；一般保持未设置。
- 填写格式：`维护默认 false；0、false、no、off 关闭，其他值启用；预演不等待。`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：启用 RANDOM_SIGNIN 后设置每账号等待上限。
- 填写格式：`0 至 86400 的整数秒，默认 3600；未启用时不增加等待。`

#### `TRAE_TOKEN_CACHE`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：指定本脚本安全缓存位置。
- 填写格式：`文件路径；默认脚本目录 .trae_token_cache.json；以 0600 权限原子保存轮换凭据和官方公开 UID，预演不读写。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TRAE_STATE_FILE`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：指定签到去重和账号冷却状态位置。
- 填写格式：`文件路径；默认脚本目录 .trae_checkin_state.json；北京时间每日状态，0600 原子写入，预演不读写。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：青龙全局通知开关；默认所有结果均尝试发送脱敏汇总。
- 填写格式：`默认 1；0、false、no、off 关闭，通知失败不改变业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：指向青龙自带 notify.py 或 sendNotify.js 所在目录。
- 填写格式：`目录路径；也自动查找 /ql/data/scripts、/ql/scripts 或导入 notify；预演仅提交本地摘要并阻止网络投递。`

#### `QYWX_TOKEN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：本人企业微信群机器人的密钥；优先于 WECHAT_WEBHOOK。
- 填写格式：`机器人 key 或官方 webhook；只向固定官方主机发送脱敏摘要，预演不发送。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECHAT_WEBHOOK`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：本人企业微信群机器人的官方 webhook，兼容旧参数。
- 填写格式：`含 key 的官方 webhook 或 key；QYWX_TOKEN 优先，预演不发送。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `PLUSPLUS_TOKEN`

- 所属脚本：`scripts/trae_checkin.py`
- 获取或设置：可选：本人 PushPlus 通知令牌，兼容原变量拼写。
- 填写格式：`单个令牌；仅发送脱敏汇总，预演不发送。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

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
- 获取或设置：需要断网验证时在青龙环境变量设置为1；正式执行时设为0或删除。
- 填写格式：`1、true、yes、on启用；默认0`

#### `TY_DRAW_SIGNIN`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：希望签到后抽取当天已有的签到奖励机会时手动启用。
- 填写格式：`1、true、yes、on启用；0、false、no、off关闭；默认0`

#### `TY_DRAW_PHOTOS`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：希望抽取已有相册任务奖励机会时手动启用；需自行在官方客户端取得资格，本脚本不启用相册备份或上传照片。
- 填写格式：`1、true、yes、on启用；0、false、no、off关闭；默认0`

#### `RANDOM_SIGNIN`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：按需要设置签到前随机等待；沿用已维护版本默认值，验证时可设为false。
- 填写格式：`仅true启用；默认true`

#### `MAX_RANDOM_DELAY`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：在青龙环境变量填写签到前随机延迟的最大秒数。
- 填写格式：`0～86400的整数；默认3600；断网预演不等待`

#### `TY_ACCOUNT_TIMEOUT`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：在青龙环境变量填写每个账号HTTP流程的总秒数；包括登录、签到及启用的奖励阶段，不包括随机等待。
- 填写格式：`10～600的整数；默认60；需要Python 3.9及以上的青龙Linux或其他支持信号计时器的系统`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：使用青龙现有通知配置；如需关闭任务通知设置为0。
- 填写格式：`默认1；0、false、no、off关闭；断网预演只生成通知摘要、不传输`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/ty_netdisk_checkin.py`
- 获取或设置：可选填写青龙通知模块所在目录；不需要额外仓库或业务依赖。未设置时查找可导入的notify.py及青龙标准脚本目录，再尝试sendNotify.js。
- 填写格式：`可选目录路径；通知模块不可用或失败不改变业务退出码`

#### `TYQH_DRAW_ENABLE`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：默认 0，仅查询资产与奖品。确认官方活动规则和兑换成本后自行设为 1 开启抽奖。
- 填写格式：`0 或 1；默认 0`

#### `TYQH_DRAW_LIMIT`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：自行设置本轮抽奖次数上限；仅在抽奖开关开启时执行。
- 填写格式：`1 至 10 的整数；默认 10`

#### `TYQH_DRY_RUN`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：验证配置时设为 1，所有接口和通知完全断网模拟。
- 填写格式：`0 或 1；默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：默认启用青龙通知；可按需关闭。
- 填写格式：`默认 1；0、false、no、off 关闭，不区分大小写`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：可选，填写青龙 notify.py 所在目录；未设置时尝试导入 notify 及标准青龙目录。
- 填写格式：`本地目录路径`

#### `ocr_url`

- 所属脚本：`scripts/tyqhdraw.py`
- 获取或设置：旧版参数，无需获取或设置；维护版通过本地图像匹配识别，不连接外部 OCR 服务。
- 填写格式：`已废弃，设置后也不使用`

#### `VALORANT_DRY_RUN`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：在青龙环境变量中设置为 1 启用完全断网预演；默认 0。
- 填写格式：`1 启用；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：全局通知开关，默认 1；同时控制文字通知和 Telegram 图片。
- 填写格式：`0、false、no、off 关闭；其他非空值开启。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：可选，填写已有青龙 notify.py 所在目录；脚本也查找同目录及 /ql/data/scripts、/ql/scripts，最后兼容 import notify.send。不需要私有工作流仓库。
- 填写格式：`本地目录路径。`

#### `TG_BOT_TOKEN`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：可选，从 Telegram 的 BotFather 创建机器人取得令牌；与 TG_USER_ID 配套启用商品长图。
- 填写格式：`机器人令牌；仅向 Telegram 官方 HTTPS 接口发送。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TG_USER_ID`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：可选，取得自己已授权接收该机器人消息的用户或群组聊天编号；与 TG_BOT_TOKEN 配套填写。
- 填写格式：`十进制聊天编号，群组编号可为负数。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VALORANT_FONT_PATH`

- 所属脚本：`scripts/valorantstore.py`
- 获取或设置：可选，指定当前运行环境已经安装且获准使用的中文字体以改善长图中文显示；不填写使用 Pillow 内置字体。脚本不下载或安装字体。
- 填写格式：`可读本地字体文件路径；不是必需文件，不依赖固定私有路径。`

#### `VORTEXA_LOGIN`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：官网注册时使用的账号和密码；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`旧格式每行 账号@密码；用户名在第一个 @ 分割，邮箱在完整邮箱后的 @ 分割，密码剩余内容完整保留。推荐规范 JSON。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_ACCOUNT_PASSWORD`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：同 VORTEXA_LOGIN 的兼容别名；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`同 VORTEXA_LOGIN；两者同时设置时优先 VORTEXA_LOGIN。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_ACCOUNT`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：本人官网登录账号；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每个非空行一个账号，配套 VORTEXA_PASSWORD，非空旧凭据变量行数必须相同。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_EMAIL`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：本人官网注册邮箱，VORTEXA_ACCOUNT 的兼容输入；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每行一个邮箱，配套 VORTEXA_PASSWORD；优先级 ACCOUNT、EMAIL、USERNAME。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_USERNAME`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：本人官网注册用户名，VORTEXA_ACCOUNT 的兼容输入；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每行一个用户名，配套 VORTEXA_PASSWORD。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_PASSWORD`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：本人官网账号密码；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每个非空行一个密码，不能含换行；需要包含换行的凭据不支持。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_TOKEN`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：开发者工具中官网 API 请求 Authorization 的 Bearer 值，或登录响应 accessToken；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每行一个访问 Token，不含 Bearer 前缀。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_ACCESS_TOKEN`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：同 VORTEXA_TOKEN 的兼容别名；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`同 VORTEXA_TOKEN；优先使用 VORTEXA_TOKEN。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_COOKIE`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：开发者工具中官网 API 请求的 Cookie 值，包含 openbot_refresh 时可刷新访问凭据；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每行一个账号完整 Cookie，不含请求头名称。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_REFRESH`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：浏览器官网会话 Cookie 中 openbot_refresh 的值；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`每行一个刷新凭据；仅未提供完整 Cookie 时组装为 openbot_refresh Cookie。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_FINGERPRINT`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：同一登录会话的 x-fingerprint 请求头；兼容输入，优先使用 VORTEXA_ACCOUNTS。
- 填写格式：`单行文本；默认每个账号独立随机生成。规范账号对象内字段优先。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `VORTEXA_USER_AGENT`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：浏览器 API 请求 User-Agent 请求头；不需要填写时使用内置 Windows Chrome 请求头
- 填写格式：`单行文本；规范账号对象内 userAgent 优先。`

#### `VORTEXA_LOGIN_FIELD`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：从官网 /auth/login 请求体确认账号字段名
- 填写格式：`可选字母开头的字母、数字、下划线字段，不能是 password；默认邮箱使用 email，其余使用 username。`

#### `VORTEXA_API_BASE`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：仅依据官网开发者工具确认 API 地址；无依据不要更改
- 填写格式：`默认 https://api.vortexa.cloud/api；只允许 HTTPS，无 URL 凭据、查询串或片段。`

#### `VORTEXA_ORIGIN`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：官网请求 Origin 头
- 填写格式：`默认 https://www.vortexa.cloud；只允许 HTTPS。`

#### `VORTEXA_REFERER`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：官网免费主机页面地址
- 填写格式：`默认 https://www.vortexa.cloud/free-hosting；只允许 HTTPS。`

#### `VORTEXA_PRODUCT_ID`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：运行 VORTEXA_LIST_PRODUCTS=1 从公开免费产品列表获取
- 填写格式：`产品 ID；指定值不存在就失败，不自动更换产品；即使同时提供套餐 ID 也须核验免费。`

#### `VORTEXA_PLAN_ID`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：运行产品列表模式从免费套餐列表获取
- 填写格式：`免费套餐 ID；必须属于所选产品，且 type 为 free 或明确价格为零。`

#### `VORTEXA_PRODUCT_SLUG`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：运行产品列表模式获取产品 slug
- 填写格式：`不区分大小写精确匹配；优先级低于产品 ID。`

#### `VORTEXA_PRODUCT_NAME`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：运行产品列表模式获取产品名称
- 填写格式：`不区分大小写子串匹配，如 node；优先级低于 ID、slug；无选择参数时保留首个免费产品默认选择。`

#### `VORTEXA_LIST_PRODUCTS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：用户按需启用
- 填写格式：`1/true/yes/on 开启；默认关闭；优先于领取和循环模式，账号凭据仍必须符合契约但不发送到产品接口。`

#### `VORTEXA_CLAIM`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：用户明确希望领取免费主机时启用
- 填写格式：`1/true/yes/on 开启；默认关闭，只读取主机、库存、免费套餐；不直接领取付费套餐。`

#### `VORTEXA_LOOP`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：用户按需启用库存轮询
- 填写格式：`1/true/yes/on 开启；默认关闭；在领取模式下最多扫描 VORTEXA_MAX_SCANS 次，已有主机或领取核验完成即停止。`

#### `VORTEXA_MAX_SCANS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按可接受的轮询时间配置
- 填写格式：`1 至 30 的整数；循环默认 3 次，未开启循环只扫描一次；建议执行时间小于十分钟定时间隔。`

#### `VORTEXA_TIMEOUT_MS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按网络质量配置
- 填写格式：`1000 至 120000 的整数毫秒；默认 30000，覆盖完整请求时长。`

#### `VORTEXA_CONFIRM_DELAY_SECONDS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按服务开通延迟配置
- 填写格式：`0 至 120 的整数秒；默认 5；领取后等待再确认官方状态，未确认则失败且不重复提交。`

#### `VORTEXA_INTERVAL_SECONDS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按库存扫描需要配置
- 填写格式：`1 至 300 的整数秒；旧最小间隔别名，默认 30。`

#### `VORTEXA_INTERVAL_MIN_SECONDS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按库存扫描需要配置
- 填写格式：`1 至 300 的整数秒；默认采用 INTERVAL_SECONDS 或 30。`

#### `VORTEXA_INTERVAL_MAX_SECONDS`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：按库存扫描需要配置
- 填写格式：`不小于最小间隔且不大于 300 的整数秒；默认最小间隔与 60 中较大者。`

#### `VORTEXA_DRY_RUN`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：本地或青龙测试时启用
- 填写格式：`1/true/yes/on 开启；不访问任何业务网络，不执行领取或登录；通知也受断网保护。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：青龙全局通知开关
- 填写格式：`默认 1；0/false/no/off 关闭；其余值尝试通知。通知缺失或失败不影响业务退出码。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/vortexa_free_claim.js`
- 获取或设置：已安装青龙 sendNotify.js 的所在目录
- 填写格式：`可选目录；其次探测 /ql/data/scripts 和 /ql/scripts；不下载辅助文件，不作为业务依赖。`

#### `WANGCHAO_DRY_RUN`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：需要断网检查参数、账号隔离、阶段计划和汇总时设置为 1。
- 填写格式：`默认 0；1/0、true/false、yes/no、on/off。预演不代表真实业务成功。`

#### `WANGCHAO_LOTTERY`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：确认允许消耗抽奖次数后手动设置为 1；先在官方页面完成必要绑定。
- 填写格式：`默认 0；设为 1 时仅在阅读进度和官方资格都通过后抽奖一次，不自动重试。`

#### `WANGCHAO_BONUS`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：需要浏览推荐频道中的“阅读有礼”“诗韵望潮”活动文章入口时设置为 1。
- 填写格式：`默认 0；设为 1 时按接口提供的入口浏览，不重放随机文章阅读或承诺增加次数，不运行诗词答题及红包。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：使用青龙通知模块现有渠道配置；设为 0 可关闭。
- 填写格式：`默认 1；0、false、no、off 关闭。总结含账号总数、成功数、失败数及预演状态。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/wangchao.py`
- 获取或设置：仅当 notify.py 不在 Python 导入路径或青龙标准脚本目录时，填写其所在目录。
- 填写格式：`可选本地目录路径；用于通知，不参与业务请求。通知不可用、失败或超时均保留业务退出码。`

#### `WENTIWEILAIHUI_DRY_RUN`

- 所属脚本：`scripts/wentiweilaihui.py`
- 获取或设置：在青龙环境变量手动设置，测试时使用 1。
- 填写格式：`1 开启完全离线预演；0、false、no、off 关闭，默认 0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/wentiweilaihui.py`
- 获取或设置：青龙全局通知开关，默认启用。配置青龙 notify.py 或 sendNotify.js 的推送渠道。
- 填写格式：`0、false、no、off 禁用，其余值启用；预演仅模拟通知，保证完全断网。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/wentiweilaihui.py`
- 获取或设置：仅在通知模块位于自定义目录时填写，默认发现可导入 notify 或青龙标准目录。
- 填写格式：`包含 notify.py 或 sendNotify.js 的本地目录，不用于业务接口或凭据配置；JavaScript 通知仅在已有 Node.js 时可用。`

#### `WORKBUDDY_DRY_RUN`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：由用户设置，开启完全断网预演。
- 填写格式：`1、true、yes、on 开启；默认 0。`

#### `WORKBUDDY_JITTER_MAX`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：沿用上游启动随机延迟参数，按需要设置。
- 填写格式：`0～3600 的整数秒；默认 600，0 关闭。正式运行账号间保留 5～10 秒等待。`

#### `WORKBUDDY_TIMEOUT`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：按网络环境设置单次 HTTP 超时。
- 填写格式：`1～120 的整数秒；默认 30。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：青龙全局通知开关，由用户设置。
- 填写格式：`默认 1；0、false、no、off 关闭。断网预演仅模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/workbuddy.py`
- 获取或设置：可指定本人青龙 notify.py 所在目录；也检查常用青龙脚本目录和可导入的 notify 模块。
- 填写格式：`可选本机目录路径，仅用于通知，不用于业务 HTTP。`

#### `WORKBUDDY_TOKEN`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：旧国际版单账号兼容别名；从本人官方登录授权响应获取明文 accessToken（AT）与 refreshToken（RT）；不得使用加密信封、他人凭据或把真实值提交仓库。优先使用规范变量 WORKBUDDY_INTL_TOKENS。
- 填写格式：`国际版单个 AT；规范变量非空时忽略。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_TASKS`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：按需手动选择国内版任务，默认签到、已完成任务领奖、旅行、Buddy信息和徽章查询；也可用 --tasks。
- 填写格式：`任务名逗号或空格分隔：checkin、claim、travel、buddy_info、badges、lottery、blindbox、redeem、gift、makeup、canvas、team_3、apps、theme、library、expert_5、template_5、chat_5、black_cat、Expert_lighthouse、Sequential_Tasks_1 至 Sequential_Tasks_7，兼容对应服务端成长任务代码。`

#### `WORKBUDDY_ONLY_TASKS`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：旧国内版任务筛选别名；建议使用 WORKBUDDY_TASKS。
- 填写格式：`与 WORKBUDDY_TASKS 相同；规范变量未定义时生效。`

#### `WORKBUDDY_SKIP_TASKS`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：按需手动排除国内版任务，也可用 --skip-tasks；不影响纯查询或仅续期模式。
- 填写格式：`同任务白名单格式，逗号或空格分隔。`

#### `WORKBUDDY_ALLOW_REPORT`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：本人明确允许模拟活跃事件后设为1，仍需显式选择成长任务；会产生对话、积分消耗或模拟记录，不代表真实桌面操作。
- 填写格式：`默认0；仅1开启成长任务模拟上报。`

#### `WORKBUDDY_MP_GAP`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：小程序成长任务使用上游45秒节奏；也可用 --mp-gap，维持真实操作间隔。
- 填写格式：`默认45，单位秒，有限非负数。`

#### `WORKBUDDY_TOKEN_STORE`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：本人指定已有私有目录中的可写缓存文件，权限0600；需 RT 续期时必填，不能放入公开仓库。
- 填写格式：`私有普通文件路径； --refresh、只有RT或已配置缓存的按需续期会原子写入；断网预演不读写。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_INTL_TOKEN_STORE`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：国际版显式 --refresh 时提供本人已有私有目录中的可写缓存文件，权限0600；不得公开。
- 填写格式：`国际版独立私有普通文件路径；续期需同一行RT；断网预演不读写。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WORKBUDDY_INTL_KEEPALIVE`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：本人明确接受创建模型对话和可能的积分消耗后开启；--keepalive也可开启，--no-keepalive优先关闭。
- 填写格式：`默认0；1、true、yes、on开启。独立日报或trial模式不得开启。`

#### `WORKBUDDY_INTL_MODELS`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：默认保留参考源四模型按序回退，可根据本人官方可用模型信息手动指定。
- 填写格式：`逗号分隔模型名；默认 deepseek-v4.1-flash、hy3、hy4-preview、hy4-preview-f。`

#### `WORKBUDDY_DRY_RUN`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：本地或青龙验证时设为1；仅验证配置与执行阶段，不请求业务、文本提供方、通知网络或轮换文件。
- 填写格式：`默认0；1、true、yes、on启用完全断网预演。`

#### `WORKBUDDY_INTL_DRY_RUN`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：仅国际版兼容的断网预演开关，也可统一使用 WORKBUDDY_DRY_RUN。
- 填写格式：`默认0；1、true、yes、on开启国际版断网预演。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：使用青龙已有 notify.py 发送脱敏总结；默认开启；通知不可用不改变业务退出码。
- 填写格式：`默认1；0、false、no、off关闭；断网预演仅模拟通知。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/workbuddy_daily.py`
- 获取或设置：可选指定青龙通知模块所在目录；未指定时尝试导入 notify 及青龙标准脚本目录。
- 填写格式：`含 notify.py 的本地目录；不作为业务运行依赖。`

#### `WPS_DRY_RUN`

- 所属脚本：`scripts/wps_clock_in.py`
- 获取或设置：在青龙环境变量中设置为1启用完全断网预演。
- 填写格式：`1、true、yes、on启用，默认0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/wps_clock_in.py`
- 获取或设置：青龙全局通知开关，默认启用；断网预演仅模拟通知。
- 填写格式：`0、false、no、off关闭；默认1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/wps_clock_in.py`
- 获取或设置：若青龙notify.py不在标准目录，可设置其所在目录；不需要私有项目仓库。
- 填写格式：`本地青龙通知模块所在目录，可不填写。`

#### `YHT_DRY_RUN`

- 所属脚本：`scripts/yht.py`
- 获取或设置：在青龙环境变量中设置；预演无需有效凭据。
- 填写格式：`1 完全断网预演，0 实跑；默认 0。`

#### `YHT_HELP`

- 所属脚本：`scripts/yht.py`
- 获取或设置：确认要在本次配置的账号之间互助后设置；不读取远端作者名单。
- 填写格式：`1 开启，0 关闭；默认 0；至少两个可取得用户标识的账号；排除自己。`

#### `YHT_SIGN`

- 所属脚本：`scripts/yht.py`
- 获取或设置：需要每日签到时设置；原主流程未调用签到，因此保持默认关闭。
- 填写格式：`1 开启，0 关闭；默认 0。`

#### `YHT_PLANT_ACTIVITY_ID`

- 所属脚本：`scripts/yht.py`
- 获取或设置：默认来自上游种植活动；活动变更时在小程序种植请求的 activityId 字段核实。禁止猜测新活动。
- 填写格式：`数字字符串；默认 1025694534292430849。`

#### `YHT_SIGN_ACTIVITY_ID`

- 所属脚本：`scripts/yht.py`
- 获取或设置：默认使用上游签到请求实际提交的 activityId；开启签到前在小程序对应请求中核实。
- 填写格式：`数字字符串；默认 992065397145317377；不使用上游未被调用的 dailySignId 属性。`

#### `YHT_TIMEOUT`

- 所属脚本：`scripts/yht.py`
- 获取或设置：在青龙环境变量中设置请求超时。
- 填写格式：`1～60 秒，默认 15。`

#### `YHT_FERTILIZE_LIMIT`

- 所属脚本：`scripts/yht.py`
- 获取或设置：可在青龙环境变量中调低单次施肥请求数量；施肥会消耗活动肥料。
- 填写格式：`1～100 的整数，默认 100；任何未确认成功的响应立即停止施肥。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/yht.py`
- 获取或设置：青龙全局通知开关；由 notify.py 读取平台通知配置。
- 填写格式：`默认 1；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/yht.py`
- 获取或设置：可选填写已有青龙 notify.py 所在目录；也尝试脚本目录及青龙标准目录；不可用只记录通知失败。
- 填写格式：`本地目录路径；不是业务必需依赖；预演通知适配器运行于禁网子进程。`

#### `YOUDAO_DRY_RUN`

- 所属脚本：`scripts/youdao.py`
- 获取或设置：自行设置为 1 进行完全断网预演，通知仅模拟，不验证真实登录；默认 0。
- 填写格式：`1 启用；0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/youdao.py`
- 获取或设置：青龙全局通知开关，默认 1；实际运行通过已有 notify.py 或 sendNotify.js 发送脱敏总结。
- 填写格式：`0、false、no、off 关闭。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/youdao.py`
- 获取或设置：可选，填写已有青龙通知模块所在目录。未设置时自动发现青龙标准目录。
- 填写格式：`本地目录路径。`

#### `YYS_HUIJUAN_DRY_RUN`

- 所属脚本：`scripts/yyshuijuantime.py`
- 获取或设置：测试时在青龙环境变量中设置为 1；正式运行删除该变量或设置为 0。
- 填写格式：`1、true、yes、on 启用断网预演；默认 0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/yyshuijuantime.py`
- 获取或设置：青龙全局通知开关；默认开启，使用青龙已有 notify.py 通知配置。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/yyshuijuantime.py`
- 获取或设置：可填写青龙 notify.py 所在目录；否则尝试可导入的 notify 模块及 /ql/data/scripts、/ql/scripts。通知失败不改变业务退出码。
- 填写格式：`可选绝对目录路径`

#### `ZCODE_INTL_TOKENS`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：选择 intl 时必填，all 时配置需要执行的区域。在官方 ZCode 国际版（z.ai）完成登录或客户端网页授权，在网络面板查看 billing/preview 或 billing/claim，获取套餐 JWT、设备及验证码。JWT 与国内版不互通，勿使用推理 access_token。验证码失效时重新获取。
- 填写格式：`每行一个账号，格式与 ZCODE_CN_TOKENS 相同。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZCODE_REGION`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：按账号所属区域设置，也可用 --region 覆盖。
- 填写格式：`cn（默认）、intl 或 all；all 按国内、国际顺序处理已配置账号。`

#### `ZCODE_PLAN_ID`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从官方套餐预览请求的返回数据获取 plan_id。
- 填写格式：`套餐标识，留空按最高优先级选择，同优先级取首项。`

#### `ZCODE_APP_VERSION`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从官方客户端版本或套餐请求参数获取。
- 填写格式：`版本字符串，默认 3.14.0。`

#### `ZCODE_CAPTCHA_PARAM`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从当前账号 claim 请求的 X-Aliyun-Captcha-Verify-Param 获取；建议放入对应账号行，3007 时重新获取。
- 填写格式：`仅补齐账号行未提供的验证码，可能短时一次性。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZCODE_ACTIVATION`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：确认需要补报客户端启动和日活事件时显式设置。
- 填写格式：`0（默认）或 1；预览和断网预演始终不发送。`

#### `ZCODE_CN_DRY_RUN`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：用于断网验证，不验证真实业务。
- 填写格式：`1/true/yes/on 开启全进程预演；默认关闭。`

#### `ZCODE_INTL_DRY_RUN`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：国际版兼容预演开关，作用于全部区域。
- 填写格式：`1/true/yes/on 开启全进程预演；默认关闭。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：青龙统一通知开关。
- 填写格式：`默认 1；0/false/no/off 禁用。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：填写青龙 notify.py 所在目录，默认自动发现脚本目录和标准青龙目录。
- 填写格式：`本机通知模块目录。`

#### `PUSHPLUS_TOKEN`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从 PushPlus 用户中心获取；青龙通知不可用时使用。
- 填写格式：`推送令牌。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BARK_URL`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从 Bark 应用获取；青龙通知不可用时使用。
- 填写格式：`完整 HTTPS 推送地址。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `WECOM_WEBHOOK`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从企业微信机器人设置获取。
- 填写格式：`完整 HTTPS Webhook 或机器人密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_WEBHOOK`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从钉钉机器人设置获取。
- 填写格式：`完整 HTTPS Webhook。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `DINGTALK_SECRET`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从钉钉机器人加签设置获取。
- 填写格式：`与 Webhook 配套的签名密钥。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `QL_URL`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从原有青龙通知接口部署配置获取，优先使用 notify.py。
- 填写格式：`HTTPS 青龙地址，不带末尾斜线。`

#### `QL_TOKEN`

- 所属脚本：`scripts/zcode_cn_daily.py`
- 获取或设置：从原有青龙通知接口配置获取。
- 填写格式：`与 QL_URL 配套的通知令牌。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZIPPO_TASKS`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：按需选择任务，默认仅积分查询与签到。
- 填写格式：`逗号分隔 points,sign,goods,favorite,unfavorite,share,comment,invite；默认 points,sign；unfavorite 必须同时选择 favorite。`

#### `ZIPPO_COMMENT_STAR`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：选择 comment 时必填，填写自己认可的评价星级。
- 填写格式：`1至5的整数。`

#### `ZIPPO_COMMENT_TAG`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：选择 comment 时必填，从小程序商品评价页面获取自己认可的官方候选标签。
- 填写格式：`一个完整标签，必须与官方候选完全一致；仅提交标签，不发布自由文本。`

#### `ZIPPO_INTRODUCER`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：选择 invite 时必填，向自己认可的推荐人获取推荐码，绑定可能不可撤销。
- 填写格式：`单个推荐码，不从远程获取；回显不足时报告失败并提示人工核对。`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `ZIPPO_DRY_RUN`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：设置为1执行完全断网预演。
- 填写格式：`1、true、yes、on 启用，默认0。`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：青龙全局通知开关，默认开启；预演只生成摘要以保证断网。
- 填写格式：`0、false、no、off 关闭，默认1。`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/zippo.py`
- 获取或设置：可选，填写青龙自带 notify.py 所在目录；未配置时尝试导入 notify 和青龙标准目录。
- 填写格式：`本地目录路径，仅用于通知适配器；业务运行不依赖此目录。`

#### `ZODGAME_TASKS`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：可选任务开关，在青龙环境变量中配置；默认执行签到与广告。
- 填写格式：`all（默认）、sign（仅签到）、bux（仅广告及余额）`

#### `ZODGAME_DRY_RUN`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：验证脚本参数时设置为 1。预演不调用业务网络和通知传输，只生成通知摘要；预演成功不代表真实业务成功。
- 填写格式：`1、true、yes、on 启用；默认 0`

#### `ZODGAME_DEBUG`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：保留旧输入兼容，维护版固定使用脱敏详细日志，不输出响应、地址、Cookie 或表单令牌。
- 填写格式：`兼容旧版 0 或 1，不再开启原始响应输出`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：青龙通知配置可正常发送后默认开启；如需关闭通知，设置为 0。通知缺失或失败不改变业务退出码。
- 填写格式：`默认 1；0、false、no、off 关闭`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/zodgame_test.py`
- 获取或设置：可选，指定现有青龙 notify.py 所在目录；默认尝试导入 notify，再查找 /ql/data/scripts 与 /ql/scripts。无需该模块即可执行业务。
- 填写格式：`本机青龙通知模块所在目录`


## 验证与兼容性

- `scripts/139_yunduo.py`：SHA-256 `c37eff8c6b1d510213e6ec929a3f4505e7ecf43f6934c655d924fd0165024942`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/117317c83fa5c3cc`。
- `scripts/2cycdx.py`：SHA-256 `50e848475c664acc9e2f665f75dd6c0f4b72d770e94fea08f421185fdbd77d1b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4a0d6e0728deb3f6`。
- `scripts/51cto_sign.js`：SHA-256 `0f62a8d10db8c2b4dd354e467d57274ec1ed97c9734cd4ac1965a96be9e43410`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d81ca9fcd4ad24e1`。
- `scripts/999.py`：SHA-256 `c42405330b4bfbd4f50bdc0b0e37203134a0ea24701f9d51e3e5a5a680419b84`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8ea0312febc74515`。
- `scripts/acfun.py`：SHA-256 `006ac42bec4fba6c9e41599da022e9b425b4ca5b6617bcd66c0403ab8917ed65`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0f0989a0ef3d7803`。
- `scripts/agentrouter.py`：SHA-256 `a22e06bb7c32b2ce57c1dbbea73b86dac505381bde53a818ec84254669f4c888`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/81684dd327c48211`。
- `scripts/airport.py`：SHA-256 `751d2835e39d2431905eacf72fc64a9cddfb4fac8032eaa83bc7af4632e7983d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8cd72e9849a3c893`。
- `scripts/akile_checkin.py`：SHA-256 `414598a6cc00cd6d0f804fb48bb2bed84dc8b9a64ca5fad8687925799c3e85be`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/48ce92fe72bec5fa`。
- `scripts/aliyundrive_checkin.js`：SHA-256 `e247d342c3624bc2e7cc9da6f1808d8dfeffe19f1df4a64d3a410b2b87a4ac0b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bd7e90cbb255e115`。
- `scripts/aliyunpan_checkin.py`：SHA-256 `ed1ba9f840e3411c993266ae1b29c1db3cd968bf49f318d682fea69aab37815c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9c6fa7a75879fa8b`。
- `scripts/aolaxing.py`：SHA-256 `5e2e40940a4bd132b7f240273fe1e6850ace43aa93856a8ee9871aa263ee7b46`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3ca8984737c9322f`。
- `scripts/api_hax.py`：SHA-256 `b82b5df5898bca09afb910abd7db43507e0fa2b93866ffd7fec97e722e3b8d49`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/fbf36f8697d4cc45`。
- `scripts/arknightsbanner.py`：SHA-256 `e8f9017bbd7ddf89573d8a0e04bc5bdef09d8f3aa0da333b42a57e5df74e9161`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/918364c17c412528`。
- `scripts/atxyq.py`：SHA-256 `6d8723d7248ad77b80ee7a77734038bb6dae5c87cdebc86da19af1319553fcf1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `evidence/basic/6b6ae91490051bce/6d8723d7248ad77b80ee7a77734038bb6dae5c87cdebc86da19af1319553fcf1`。
- `scripts/auto_buy.py`：SHA-256 `551b1099baab98acf5d68dc9ff68add1914aad1763a9fec69ee6ffe93852b859`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0196c3c6c89dc959`。
- `scripts/autoclaw_cn_daily.py`：SHA-256 `f8bdc918bce6376ca7e1a8cb8d182c987fd9ff3286a808187d66a3768305a426`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3813c988ddc0c592`。
- `scripts/autosignin.js`：SHA-256 `c9f9cb1e7cf025514b245d555ac63849d2617eb3d29b473f92cf61f6b2a4a72b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ee45e24a6845dbc0`。
- `scripts/autosignin.py`：SHA-256 `cd2b330788aa14bc2e020a5451329f291e5d1dd97f66ad0a6ed2c921b6dee3d8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7919605278826396`。
- `scripts/baidu.py`：SHA-256 `f3bfc64c4f219e4c451796542f4d2af0605812c82ab871f29039441d108afd1a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ed0673d8c02fc410`。
- `scripts/baiduwangpan_checkin.py`：SHA-256 `e9c658f4544427bd94ab4da74a724038d1f849c8b9665464ded6e8a1c4dd2c18`；live 业务成功证据位于 `projects/checkin/validation/d9230b69d9462c7c`。
- `scripts/baiduwp.py`：SHA-256 `419008b91e8a348b310d5de9d819e6670ec665dd212922406e85348e52f6b0d6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/74d362990ff7d2f9`。
- `scripts/bilibili.py`：SHA-256 `b9d238f43b63599e7dfac7bac80c8f2de6b13eaa657e8f589a7a9039ab4f1f8c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ca4e1c75a27952c1`。
- `scripts/bsly_draw.py`：SHA-256 `ae1d0fe072b35fe9c22ad02ebc04ca2b0571c7cf0e60c3ad68e2c8cca58925a3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/28b170786df4dff2`。
- `scripts/bugutv.py`：SHA-256 `655c9b0fad89e4df49112865cea7fe78d7fe8f4f5a4a12649ea5a8a532cb1a97`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7ca80eead6ecc78a`。
- `scripts/bwcj.py`：SHA-256 `ae20e692177d7102468ed3ddc462576f39fd2c81ea51a9dad626e138700ac4af`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0367e0709855a394`。
- `scripts/caigamer.js`：SHA-256 `fd3bdc3108575c6901f1f9d8626e1a039f85da54bb2d200d3dd28124f794bd01`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8bd252d858b7095c`。
- `scripts/cdrail.py`：SHA-256 `5caed175e6b1ff5b1033fbbd59105a71dfb952c8dd79bc9b92f3d354a69e5225`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7389d13167df31b6`。
- `scripts/cfmoto_checkin.py`：SHA-256 `15ecc5e482af800b18360374359667392176fe88ab77c7950509da115f09f07a`；live 业务成功证据位于 `projects/checkin/validation/0ba7bb41fd4c339c`。
- `scripts/chevrolet.js`：SHA-256 `fc9137b46f1cb49c1d8f9523c145651d9453fbf8beac391fcc85039a950d7cd2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5e7302e54a0be513`。
- `scripts/ck_2nzz.py`：SHA-256 `7f3516766b49802f68470d5adb40d69a59014b79178df5de52a083e60f8af02b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a50eecf80a170dc5`。
- `scripts/ck_acfun.py`：SHA-256 `1e650693abb1fbf6f49934ed22d3ac1ff876d5c4ab719c232c57a5f15212af15`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/21b5208e088c5d34`。
- `scripts/codearts_daily.py`：SHA-256 `c6bdd619ce35cd32e1fca575006e8420c6ac3b55d55cc1ffb48ba9122862d856`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b896028c3fdcd52d`。
- `scripts/comicai_ai_cookie.py`：SHA-256 `173db2c22758f322022dedfb23fdd735a85d1cff0d39ad308ed5a8c3d0d45c8c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b33f4d715d28a216`。
- `scripts/crealitycloud_checkin.py`：SHA-256 `65ca612e847d35d7aabc19505ed10d819c478e1bdda4b88321a9dc4c24e11743`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f9739e4f6c54dce7`。
- `scripts/dachao.py`：SHA-256 `5745d76090d1c471883f40df8aead8ad74fd0f1b7fe8db24c7b995bac3dc25a9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7b77205efaf0158a`。
- `scripts/daily_benefits.py`：SHA-256 `9a155b77acadb949a6fedf73bdd5e63ec7684a45fabd5143b66ac1873f27676b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/35a9f7fe38bde305`。
- `scripts/dailynewscn.js`：SHA-256 `f2c3d44944b98f1c36d9d248b6b80554a34a74656b6df7d267acf7a1583b1268`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f3d5ae90c3c979bf`。
- `scripts/ddnsto.py`：SHA-256 `a36378f008a43fa3824429fe8650bb693f256aba081914b5254cc51fcfe58087`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e7b851436459bf8f`。
- `scripts/deepflood_checkin.py`：SHA-256 `1743ea3da4f0ef463f70619fb5a49d375dc48e5817d867ea080875a12b3f68c4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/01d51606a735260a`。
- `scripts/durex.py`：SHA-256 `dcfd65a77d774a5ea04efb135a56f675f531c6fd11d770279ec6120cbd8e025c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5bc8db2e6a36d14b`。
- `scripts/enshan_checkin.py`：SHA-256 `bbf4daf1880caeb8d30c22e335df244f0aec8756937d3e810ef62da534899504`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bec8a601d5a51b0a`。
- `scripts/epicfreegames.py`：SHA-256 `c8d5c51c3bc4dfbfb194ddb29720a35d605c3285eca606ec4af7ffdff72d0d4a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/62f8f8c670e36faa`。
- `scripts/erke.py`：SHA-256 `887228083c773feabe55dd6c936eec5ff029daf6c252a28f05732b9d32e83e59`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2eeae7b152108dae`。
- `scripts/f1owkang_qingskyland_skyland.py`：SHA-256 `2fa1e00174515df634f27a6225379ab867b62fcd9f4049f46a7431bc0efb7ed3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e02ed814df52c998`。
- `scripts/fnnasclub.py`：SHA-256 `80358575b8206ca830681be924da4c67dc20b6d4aa1e323a9f810fadff669cfc`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b5b4289ee7ca4222`。
- `scripts/forum_download.py`：SHA-256 `f7c36f3c4bb0ef72d1c9bdaec2387d373c870a5be4607ac71ed9f274c0339751`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e60b615a6554e2b6`。
- `scripts/fwxs_checkin.js`：SHA-256 `e9f6410e225fbef75b20d661e4122ea2bece6b41b7908f17f4f42244f151780c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/be3b140cb6fdd0e3`。
- `scripts/fxh.js`：SHA-256 `228504f8a8e327c856a9187a242e930442b57356490653b6e6c7e692509f4081`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/825e404e9590b589`。
- `scripts/get_yys_cgvideo.py`：SHA-256 `5acaf38a721b681a7ea5a7ac0240d4116214d54ea3dde624435202a040af09cd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8edbbefea99ad1fb`。
- `scripts/get_yys_imagelinks.py`：SHA-256 `ee7273bd292415bb0bad2603012b77b85fb0287709a5ca24d7f4e426408e3cf3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/21c2272d2f618e0f`。
- `scripts/hellogithub.py`：SHA-256 `9ba47639b981f682c235acbddab2d09e14f1e0bc0737fc1d07171debe254a8ce`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e249d85fcb6de594`。
- `scripts/hifiti_checkin.py`：SHA-256 `ae18f25d6d7ad768ae64880761732b510e7bc3e75179bb9d66790f8203e4faf9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7e9bef2404a0d5b3`。
- `scripts/hlyl.py`：SHA-256 `ad472c7faec4d4ebd6c081c9abc6e3f6274a701c7a2f7284c0f6e7292878097d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/397f602c2c364fad`。
- `scripts/hsay.py`：SHA-256 `334abc1e83a833188dedc6debb51a5f46c2bf1c7ffff2b2a0c57aeffb60954f7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/1a646b7bbddbaa7d`。
- `scripts/huaruntong_wx.py`：SHA-256 `6fb8e542eeeed076b41be51b9c90430571698ff02226f25d85b83b54562a7c8e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/13902b7b1dd570d1`。
- `scripts/hykb_gamesign.js`：SHA-256 `11f5887f78f37ed569c9d8c0e75944c30a98d62dca54cb30bddab8644d2e75ae`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b7f05744373113a8`。
- `scripts/ikuuu_checkin.py`：SHA-256 `44c91448c6d2d8ef71df14ee1a232e58f45bd7b232ff8870983ff6379e378694`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7ea70c9e9d579efb`。
- `scripts/imaotai.py`：SHA-256 `9c2f6927060e1dfa9b08784217483bfe8e4979e81763380ed03ad98f3fa8bd66`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ef664085f75113bd`。
- `scripts/index.js`：SHA-256 `b0f670de5353137cb479251c75283cf6960207864f98a92c687c46147f7db3d7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b4b3175bb52c98a5`。
- `scripts/iqiyi_checkin.py`：SHA-256 `2829c7add08087e4c054a99ebc6b3f88c9e665a7a9310b713d19b2467acebed2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7701c083c0ca06d5`。
- `scripts/jc_checkin.py`：SHA-256 `a9e3d7940077da25253b9b49f7a39552ffe129ebf250bf5036d3a1dad18cc787`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/fd9b2a23e39332a5`。
- `scripts/jcqd.py`：SHA-256 `ddbc8159cadbfeb3332e7ecfed3200f268bc1950c4fd4a6f6597b461ac7ad731`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/757bc6292780fb17`。
- `scripts/jingyiluntan_sign.py`：SHA-256 `0a3987df426c3b1aecf1022de9d2c61da039f8ce3c6dc0bebff7f6c50117ca3e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c2696f744222baac`。
- `scripts/jissbon.py`：SHA-256 `6fac3023c4ba77d121f3e7679bd5a0cc28b3739bb988776f28a22fb80e9d20bf`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/dff518c351ef674e`。
- `scripts/jyj.py`：SHA-256 `28d1ce160e4bd75321dc615c98494c1703728f17bfb1bc4b692b5bc6f1278042`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d484be6cd2a617db`。
- `scripts/kgqq.py`：SHA-256 `fd14c4b064a5168918f0d3eb0ea766762361151ca7c441e4188cd7b98c31d9a9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d49d052949d2bef1`。
- `scripts/kjwj.py`：SHA-256 `6867c355c23ccfdd7deafbcbeef48865c1001d7e274c9b9e265dced5047eaaab`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f4e13633e05b6a28`。
- `scripts/kuaishou_reward_status.py`：SHA-256 `b727e90b3326ec58b00281be13ad27879cb75be0af9a9c5c0a93fe3fbd8aa305`；live 业务成功证据位于 `projects/checkin/validation/ks_cleanroom_v1`。
- `scripts/kuku_daily.py`：SHA-256 `d16dbbed6f9a6a5ebe6daa4597c46b4e692c7f363beb4a6296bb1e1fceb35fc9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/224698e8fa0ac8f6`。
- `scripts/kurobbs_sign.py`：SHA-256 `420de38577b9132e63b09652938838b0a60f03519d374ea9114bc9a01d80bb05`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7f6af4cafcff2aaf`。
- `scripts/l.py`：SHA-256 `aba0cf5855af880ab672f6f322417b935718dc8e2e81351ebd65791a1b9809dd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/f1ad78537129604d`。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：SHA-256 `1e758c69465f04e6b2561615b1b0a222871c106bbacbb0f0afab42fbb0fa238c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/12e44eccee922041`。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：SHA-256 `b165e0325fb0761f66081e45083b65726d03157099f19fddec58665381ad2c34`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/cb2f4adeccaa95b9`。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：SHA-256 `d403a1c68ee24f721a320318363bb0a763d815b217fa73801512ecbac8c303ff`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7990614346ba82e0`。
- `scripts/lizhixu_ql_script_hub_youdao.py`：SHA-256 `6aca37b98181444404cc54f0917b8aab7d6a0995e485aff80918ec32a205e3a6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/bd893babb907859b`。
- `scripts/lobsterai_checkin.py`：SHA-256 `30863a779860e257ebe6c38bb2b222f97448e0748a912b1c8cea38dc33f4dc18`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3328423575cf7143`。
- `scripts/loomy_daily.py`：SHA-256 `31903376bb554862f5d23f99b67975b4d159ee6de93bb8b280b3fc329d451ce9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/5e0e668122f2807b`。
- `scripts/lynkco_qinglong_single.py`：SHA-256 `5c07b38c3cc8f306cafb7a9efda1215db8b036c5d4d24c2faeb9985c89490233`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c087eb48daa78349`。
- `scripts/main.py`：SHA-256 `ea3bb416264f093933b3bf07dbc40a5dc02eeb4e8fc02d1626f2db0e4ac1ae17`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c0137ce8eaf72832`。
- `scripts/mifan_optimized.py`：SHA-256 `7fbd32635c2c61d2e89c6ef056726314c439ad70655c0295af47364e565f8ffb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/68feda0fb9579305`。
- `scripts/mimotion.py`：SHA-256 `4e8149eb7fd9f48b6a92c4b22190c633a40d7def1754bb196a3c26bcbf30d7cc`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4b7d4969e07369fa`。
- `scripts/netease_task.py`：SHA-256 `a94fc863e187c81a29f6c44ab88c30162bc3d1570ebbe602a70ed4824a198fbe`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a8a311f3f5aaa2e6`。
- `scripts/nga_checkin.py`：SHA-256 `147ff1cce75da800dc48ed5dade6222282afff8f7bd6f1bbbdebda74ede5242e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4e0cf5e129fb12a4`。
- `scripts/nodeseek.py`：SHA-256 `9e38011e2840ce76dc24111e8c6d6522aeb75b71d8212be4551def23840e5549`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c28f0207e2b02a7b`。
- `scripts/nodeseek_checkin.py`：SHA-256 `bc4d97b59c92bda264dd477193a902490e25641b333bfe8feab8406d233ef505`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4196e654f2a752f8`。
- `scripts/nte.py`：SHA-256 `44b3e9817214e01d674b189c4b2b38af6bb6fcb0012f2887f471080a78e635b1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/6919295133257387`。
- `scripts/officeace_daily.py`：SHA-256 `24733f11f9b386cbd668978df42e4c7a7140f8ef4480651d0aa73abe3d2ebb22`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/61204ec3f68839fd`。
- `scripts/ole.py`：SHA-256 `5dba4860d34bf701f15f92c59b1cfa4f6cea511c7b24355c2ea839334eea3796`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/89d9992e56504271`。
- `scripts/passnat_checkin.py`：SHA-256 `378ef21771663547b6f58d6d66d4639e79047fee044815af7c84d137b4bf2aaf`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7e0ea7b66d8114d3`。
- `scripts/psnine.py`：SHA-256 `c5eee3d70ff8779f96a50277dac5ceb6076b88c62dea16a15ac2c625078950c4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/190d89a73fbfe28e`。
- `scripts/pt_sign_v5.js`：SHA-256 `00c5772a3b7bacd61255515237ab1bd9f1d9d075d9bbf32d8ce4ec8c123552d2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/ff443f9fbbdbade5`。
- `scripts/qoder_airscript.js`：SHA-256 `e1e74cc7bb351cb9b95995c142025eebec911240c0b7e54d0a9fb62b60e54480`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e034e75509550071`。
- `scripts/quark_signin.py`：SHA-256 `2487b5cd4a53457b8d0ce2000f154668060333a0483b846a52a9d329da18a5bb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/18c47e12eda9864c`。
- `scripts/raccoon_daily.py`：SHA-256 `3ebdbfeaf41c75c467fdeb6f2e11889b5a985cacfc3b7203679348087ed36b63`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d4bfc257a45d9e8d`。
- `scripts/rainyun.py`：SHA-256 `15f8b296b4bca186c9376744151cbb06dafa0d3b1a0c79f0ddff119163dc2b4a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/89f2e9b460331a75`。
- `scripts/rousi_checkin.js`：SHA-256 `b20207312e40ff721f057cfe38dbdf6570486e9f4ce1b4d7882f60f85dafb138`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/3c5c6df4d8a81a7f`。
- `scripts/sf.py`：SHA-256 `5c594804fd2d2a74fe2ad188aa73f95755d5bd28e562d3feceb78cc0fa87fcaf`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/c231dec461782853`。
- `scripts/sfsu_checkin.py`：SHA-256 `d48a9999e72bbea15c0de43dc537ab4f37f63c5a6fb38708098482f92761affb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/19b2285cc7b8a82e`。
- `scripts/sgs.py`：SHA-256 `af3d44c77a409fccb89cdf36a8282bb311c17463a559c544c114d78b253efce7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/45e40e4a3ee37968`。
- `scripts/shuyi.py`：SHA-256 `947ec405caf0bacdc1f2b823552425d882c3510d733c99c8a1801bf7a739870c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/551a306ac75780f1`。
- `scripts/sign_in.py`：SHA-256 `d2d3f6610f0aaf4c6866b93fc47751f18a8004bf53c9eae43b560cde380d6cef`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/01041a1995eb1f55`。
- `scripts/skland_daily.py`：SHA-256 `23bae97efad62a8e36e4ed2b0d82fe9a2d97450fdba6f089cd23c2d9561580b3`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/96b3c22e1eff9659`。
- `scripts/skland_demo.py`：SHA-256 `6630751a2fdb3b62947ba9dd9b33187db05cbf4dcdd859fe9f60da9e9dda5c2b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d82ea23b9575791b`。
- `scripts/skyland.py`：SHA-256 `4e83f3d0eda94365bdd5fc3648594f678a381cb513c7d065667be9dfbe8874e1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/0bde30a1db078051`。
- `scripts/smzdm_checkin.js`：SHA-256 `b01d902608844777102486bab86a7fa18f18c4dfb3166375b7bfacad07e0808b`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/621df252c315f2d1`。
- `scripts/ssl.py`：SHA-256 `6fc3c3040959c04d815c2ba897050e99994e591f34fbdd4ab6ca2b894ed54766`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/cf6fb60f0d69e9ed`。
- `scripts/sudojia_33agilestudio.js`：SHA-256 `7677c43b5720b0556f6d0b2949405b7c91d218dbc5d020ad6be0dd46ce2308d8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/28da2f8c0aec7716`。
- `scripts/sudojia_allgirls.js`：SHA-256 `c553619d6534fdf01df62c381df54bfb5557104402a27aa037bf381b075d8934`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e8776198aafad33e`。
- `scripts/sudojia_amx.js`：SHA-256 `74c9e4adc427ad5b11fa3790b55857eb5a928af78cabc6c0d7c7d04ee8694c65`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/2afe8ef7e443b92b`。
- `scripts/sudojia_authcheck.js`：SHA-256 `cb0ac42844920cb1be7a54b04e2781ad0f330cda89176379e2f8353a87119a0c`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/505cfecf6964c372`。
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
- `scripts/sudojia_jlc_yj.js`：SHA-256 `1f7a49e30dd7a0e4da2a1298bd24b1ca0578cf86e10fec9406d001aa872cb493`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/38602005c4e13646`。
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
- `scripts/sudojia_v2ex.js`：SHA-256 `a1f67a331ea725190a2791e37240a488b7be8db2f0f64bb1b436162fa8c45080`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/705cf315f5da6907`。
- `scripts/sudojia_wnna.js`：SHA-256 `776fd6f05d881afb02e5c070096ab8909a638f944e548065d702ae7e1bb2dd72`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/364d0c6592e14300`。
- `scripts/sudojia_xhn.js`：SHA-256 `b0131f2d77c0d1f5ae6271d2a7604798ee3313db307e23390343d2d5e316abbd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/b86681a8e89e05c0`。
- `scripts/sudojia_xiangwan.js`：SHA-256 `692566ebd5403b42b7671029cf12e1d993ebc6199d8ae704fd3bc489b9069ed7`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d59346ef3ccb8591`。
- `scripts/sudojia_xiaomi_community.js`：SHA-256 `2426f49711019ec8e7fe8dc664362df99aa478c1828bd5d5f48c331dbb2a88dd`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8b06f8c5b53252cf`。
- `scripts/sudojia_xinxi.js`：SHA-256 `fcdb27ec00935e010ddc68dcaae974b36d3d5effd2de4cf408cd1971f28d6a3d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/83f21cfa63eab18f`。
- `scripts/sudojia_xpfarm.js`：SHA-256 `ffa9878cc55005e28061ca97009b8ffa7c48ce01144b325d0354d499c28a897d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/9705540ac69a7c3e`。
- `scripts/sudojia_znds.js`：SHA-256 `e642ddf42719ca2ac4e37a94856f3c35e08307bc0b47d993bd5a1a83eb13eba1`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e69a67d8a3d7b7a9`。
- `scripts/sudojia_zxice.js`：SHA-256 `eb50f784e85263452ae010edf81d6b0e1d6c864532f2c6f1a170aa168ddc8c5d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/eb4b0810d476bc5e`。
- `scripts/supertopicsign.py`：SHA-256 `7ec766c350e8734acddc724e720a0073d8838430e1885a9e699e13d907fbacb4`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a5e811acce266569`。
- `scripts/synspoint.py`：SHA-256 `f343af6c80ac9ca40e51f0fb72a81d41acb2af51233623d6fa2f1fca4e636f7f`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8060442233509c9a`。
- `scripts/tencent_video_checkin.py`：SHA-256 `22ae305cd2e4196c0574785ab58f4dc0fb54266676ba599ea71971c4dc973ec6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/79a75a8c4715aa96`。
- `scripts/tieba_checkin.py`：SHA-256 `2db577380e0d0f1f5cf940b40cceca8bfcd21e2d140e284552f9cc943f4a7d4e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e608052390d250da`。
- `scripts/tjd_daily.py`：SHA-256 `95bb1d686b6e91e37c588601be134a99e9715c943ea99b63f6fda75fd0d51943`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e096ba77bcda7172`。
- `scripts/trae_checkin.py`：SHA-256 `45962500ef7a2bad52fda864d421f76bf3639e6ee0fb6dee695b394eb34199b8`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/71de90498a3a6ded`。
- `scripts/tsthb_checkin.py`：SHA-256 `f1f423f22e8134fb3080600f07293746eeb4d05783ec1778f489174dc1166d4c`；live 业务成功证据位于 `projects/checkin/validation/82616d06df4e5f53`。
- `scripts/ty_netdisk_checkin.py`：SHA-256 `096668383bde7522670dd87830f0e8b48ed4ce3e142e723c6fe6ebce238f99f2`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/70f2505a78eb7276`。
- `scripts/tyqhdraw.py`：SHA-256 `c2c1115b60fd085034eb55d28ffb8fd3cb6476263eeff23f53f5bea8ad892b7e`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/8ccef1e6eb2d7404`。
- `scripts/valorantstore.py`：SHA-256 `e7b189720b1086ca20bad310b392de69d4f75c7fa0660ed843120affa4bcc0fb`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/1153449ac9321744`。
- `scripts/vortexa_free_claim.js`：SHA-256 `4a9d6c8d8e147991d196f0ddebf7c74f200c9e12ab1fca721555034e46e2da04`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/7f027fefd96fedf2`。
- `scripts/wangchao.py`：SHA-256 `487368c93ce9621b956e4df0aba44badaf3094070a94d3a6a61c384742915067`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/d0c1751256314943`。
- `scripts/wentiweilaihui.py`：SHA-256 `f91a3a6a1873b350c695cc5466ff224a18d90d01e59e013c5a319dfc55facc24`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/afa2f50b7baa69db`。
- `scripts/workbuddy.py`：SHA-256 `c20f62f74b4c3a50a42852229dff9b40dc79baa5f6854e8d40e01a4f361c5a7a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/af0ae4c86279f8da`。
- `scripts/workbuddy_daily.py`：SHA-256 `af37790e41e116c92ebe1ecb8a001b4fc030d65a9785e161dc1bc926e23be14a`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/132c582ed57df40f`。
- `scripts/wps_clock_in.py`：SHA-256 `bc653d3a575e4993de249bd00b7f3107a8ca17f8da320903f086372b1df9a827`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/aa7303325b9bca16`。
- `scripts/yht.py`：SHA-256 `041f5e6059185deb57a956d7c3d4f62db0b4f9e6438d6884ea9b561a04a7ad9d`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/e4af0e04fafedbd8`。
- `scripts/youdao.py`：SHA-256 `0c740bfa5e0616e362c80e44bb42aedacc6cf7785d7a0665f4f9be29f4ddb799`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/4cc5f70c13c67bbd`。
- `scripts/yyshuijuantime.py`：SHA-256 `ed7e4a6e165c239056135e84d3f2a0825a5fcfded2a1f0961d11b37172069cf6`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/efe42c0f180ce822`。
- `scripts/zcode_cn_daily.py`：SHA-256 `7085cd0c4eeef4e5c9bc6f38f03e752e4e253b341c6fdb25334537e6ceceb8e5`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/a0a7b04503bfb900`。
- `scripts/zippo.py`：SHA-256 `db87391467bd1a78afea9e1725cf8a5a06a4f78373821128a20dcb98ed03b338`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/60f9d3538e9f8470`。
- `scripts/zodgame_test.py`：SHA-256 `1e51c1301d3f6930103407ee55631084359d11244ffb4b40e9bc149eb0fb3ef9`；基础核验通过，尚未验证真实账号业务；基础证据位于 `projects/checkin/validation/eb4bfbfde0f17e39`。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。

## 副作用与风险

- `scripts/139_yunduo.py`：执行每日签到并领取AI豆；点击互动、问卷及其他已选择任务，可能改变任务进度或领取AI豆；启用YDYP_UPLOAD后在云盘根目录上传10字节任务文件；启用YDYP_DELETE_AFTER后将本轮上传文件移入回收站；正式执行通知时向已配置的通知渠道发送脱敏统计。
- `scripts/2cycdx.py`：正式运行提交论坛签到及签到文案，领取对应贡献奖励。；正式运行且开启通知时发送脱敏任务通知。。
- `scripts/51cto_sign.js`：登录建立服务端会话；每日签到及平台对应的签到奖励；真实运行时通过青龙通知渠道发送脱敏摘要。
- `scripts/999.py`：正式执行提交答题选项，可能按活动规则产生积分奖励；正式执行在通知开启且模块可用时外发脱敏任务摘要。
- `scripts/acfun.py`：默认执行每日签到，更新签到状态；选择 like 时新增点赞；选择 like-cycle 时新增点赞后取消；选择 danmu 时向所选视频公开发布一条弹幕；选择 banana 时向所选视频投出一根香蕉，消耗余额；选择 share 时上报分享任务完成状态；开启通知时尝试发送脱敏任务总结，预演阻止网络传输。
- `scripts/agentrouter.py`：重新登录 AgentRouter，创建登录会话并可能发放当日签到额度。；仅显式启用 AGENTROUTER_ALLOW_AUTHORIZE 后可提交 GitHub 首次应用授权。；正式运行按 QINGLONG_NOTIFY 设置发送青龙通知。。
- `scripts/airport.py`：正式模式通过登录建立网站会话。；正式模式执行每日签到，可能增加网站赠送流量或签到记录。；正式模式调用青龙通知渠道发送脱敏任务总结，可通过 QINGLONG_NOTIFY 关闭。。
- `scripts/akile_checkin.py`：未完成今日签到时提交一次 AK 币签到。；实际执行保存本地连续签到及累计收益统计；只读和预演不写入。；显式开启保活时刷新登录 Token 并回写唯一匹配的青龙 AKILE_TOKEN 变量。；实际执行按通知开关调用青龙通知模块发送总结。。
- `scripts/aliyundrive_checkin.js`：刷新账号访问令牌；执行每日签到；领取当日签到奖励；向青龙通知渠道和可选 PushPlus 渠道发送脱敏任务总结（预演不发送）。
- `scripts/aliyunpan_checkin.py`：执行账号每日签到；默认领取当日奖励，显式全量模式下补领其他已签到未领奖励；ENABLE_DEVICE_SESSION=1 时注册设备会话；ALIYUN_PERSIST_ROTATED_TOKENS=1 且令牌轮换时写入安全凭据文件；正式执行且通知启用时发送脱敏任务通知。
- `scripts/aolaxing.py`：配置 AOLAXING_TASK_IDS 时触发对应每日任务完成及服务端关联积分或签到状态变更，具体效果以用户审阅的任务为准。；在线运行且通知开启时发送青龙任务汇总通知。。
- `scripts/api_hax.py`：正式模式且启用通知时，通过青龙通知渠道发送查询结果和统计。。
- `scripts/arknightsbanner.py`：正式运行在用户明确指定的位置创建或原子更新公告去重状态文件。；启用通知时向青龙配置的通知渠道发送卡池公告与运行总结；配置图片接收目标且公告有封面时向 Telegram 发送图片。。
- `scripts/atxyq.py`：默认每日签到，记录签到并可能增加积分。；默认领取普通任务奖励，可能增加积分。；开启 ATXYQ_LIKE 后对最多两篇文章点赞并取消点赞。；开启 ATXYQ_POST 后发布公开校园动态；配套图片参数存在时登记本人已有图片。；atxyqDel 非零时删除本人最近十篇列表内帖子。；开启 ATXYQ_HELP_LIKE 后为明确指定的帖子点赞。；开启 ATXYQ_INVITE 后创建所选邀请关系。；正式运行且通知开启时向已配置青龙通知渠道发送脱敏总结。。
- `scripts/auto_buy.py`：显式开启商城后提交抢购请求，可能兑换商品、扣除积分或产生付费订单；明确拒绝时可能重复提交；显式开启积分后增加阅读计数并提交阅读、视频或分享积分请求，可能增加积分及改变任务进度；显式开启收藏动作后添加收藏，另行开启取消收藏开关后可能移除已有收藏；显式开启评论动作后公开发布带来源署名或本地回退的评论文字；真实运行发送青龙任务汇总通知。
- `scripts/autoclaw_cn_daily.py`：真实运行提交所选地区 daily_signin 签到任务，可能获得积分；登录态过期或 --refresh-only 时续期登录态，可能使旧登录态失效；仅显式配置对应地区 STORE_FILE 时写入受保护的本地凭据缓存；通知开启时通过已配置渠道发送脱敏摘要；预演仅模拟通知。
- `scripts/autosignin.js`：正式运行刷新阿里云盘会话令牌，新凭据仅在内存使用。；正式运行执行每日签到。；正式运行领取当天已完成的签到及任务奖励。；正式运行在通知开启且模块可用时发送脱敏总结。。
- `scripts/autosignin.py`：正式访问新闻页可能领取每日签到奖励及触发服务端随机遭遇事件；正式运行在通知启用且模块可用时发送脱敏通知。
- `scripts/baidu.py`：实际运行向百度提交本站 URL 并消耗提交配额；显式 times 大于 1 时重复提交同一清单；实际运行在通知开启且通知模块可用时发送脱敏任务通知。
- `scripts/baiduwangpan_checkin.py`：为每个已配置的百度网盘账号执行每日会员签到；为每个已配置的百度网盘账号提交每日会员问题答案；在通知开启且青龙通知模块可用时发送一条脱敏任务汇总通知。
- `scripts/baiduwp.py`：执行会员签到，增加会员成长值；提交每日题目答案，可能增加会员成长值；启用通知时发送脱敏任务总结。
- `scripts/bilibili.py`：漫画签到改变签到记录；观看进度上报改变观看历史与任务记录；显式启用分享后改变视频分享任务记录；显式启用投币后消耗硬币并改变视频投币记录；显式启用附带点赞后改变视频点赞状态；显式启用兑换后消耗银瓜子并增加硬币。
- `scripts/bsly_draw.py`：显式开启实跑后消耗抽奖机会并可能获得奖品。；实跑启用通知且桥接可用时向青龙配置的通知渠道发送脱敏总结。。
- `scripts/bugutv.py`：登录并建立账户会话，沿用上游rememberme登录参数；每日签到并领取服务端实际发放的积分奖励；默认退出本次账户会话，可通过BUGUTV_LOGOUT关闭；通知开启时发送青龙任务总结；配置SendKey时额外发送Server酱总结。
- `scripts/bwcj.py`：新版签到产生签到记录及服务端发放的积分或奖励。；显式开启旧版签到后产生旧版签到记录及服务端奖励。；正式运行时通过青龙配置的通知渠道发送脱敏任务总结。。
- `scripts/caigamer.js`：正式运行提交签到并领取站点签到奖励；正式运行在通知启用且通知模块可用时发送脱敏任务统计。
- `scripts/cdrail.py`：调用签到接口，完成每日签到并可能增加积分；正式模式通过青龙通知模块发送脱敏结果摘要。
- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容；最多产生三次公开评论、三次点赞和三次分享任务记录；发帖和评论前访问第三方一言接口获取公开随机文本，不发送春风动力账号凭据。
- `scripts/chevrolet.js`：实际运行向雪佛兰签到接口提交签到，可能改变签到状态并获得服务端签到奖励。；通知启用且本地青龙通知器可用时，实际运行发送脱敏任务总结。。
- `scripts/ck_2nzz.py`：正式运行向咔叽网单提交每日签到，可能获得站点签到奖励。；正式运行且通知开启时通过青龙配置的通知渠道发送脱敏任务摘要。。
- `scripts/ck_acfun.py`：默认执行每日签到，可能获得签到奖励。；启用 like 时先点赞再取消；取消失败时可能保留点赞状态。；启用 danmu 时公开发布弹幕。；启用 banana 时消耗一根香蕉并投给视频。。
- `scripts/codearts_daily.py`：领取福利积分与新人奖励；确认福利到账；使用可选续期材料刷新登录凭据；写入私有凭据缓存和领取幂等台账；发送脱敏通知（预演只模拟）。
- `scripts/comicai_ai_cookie.py`：向 ComicAI 提交每日签到并可能获得积分；启用通知时发送脱敏任务总结。
- `scripts/crealitycloud_checkin.py`：登录与 OAuth 授权生成服务端会话；每日签到改变签到记录并领取奖励；正式运行发送已配置的青龙通知；断网预演仅尝试通知调用，不允许联网。
- `scripts/dachao.py`：签到改变签到记录及活动积分；完成阅读任务并上报阅读时长；开启抽奖后消耗活动抽奖次数并获得奖励；开启兑换后领取现金红包。
- `scripts/daily_benefits.py`：默认执行免费会员签到，符合条件时领取七日奖励；显式开启会员试用时提交申请并消耗申请机会；显式开启天天抽奖或任务中心抽奖时消耗抽奖机会并领取接口发放的奖品；显式开启签到系列重开时改变签到系列；显式开启任务中心时执行签到并领取签到奖励；正式运行通知启用且模块可用时发送任务汇总通知。
- `scripts/dailynewscn.js`：正式运行且通知启用时，向青龙已配置渠道发送所选公开内容及脱敏总结。。
- `scripts/ddnsto.py`：真实执行时创建七天免费套餐订单；真实执行时将订单套餐绑定到指定路由器并延长套餐到期时间；启用通知且青龙模块可用时发送脱敏任务通知。
- `scripts/deepflood_checkin.py`：正式运行向 DeepFlood 提交每日签到，可能获得鸡腿并改变账号签到及积分状态；正式运行通知启用且模块可用时，通过青龙已配置渠道发送脱敏任务汇总。
- `scripts/durex.py`：每日签到改变签到状态并可能获得积分；开启分享后上报活动分享记录并可能获得奖励；开启抽奖后参与活动并可能消耗抽奖机会或积分。
- `scripts/enshan_checkin.py`：正式运行提交每日签到，可能增加恩山币和积分。；正式访问论坛可能产生论坛自身的登录奖励或访问记录。；正式运行且通知开启时，通过青龙通知模块发送脱敏任务汇总。。
- `scripts/epicfreegames.py`：向配置的 Telegram 会话发送免费游戏图片或文字提醒。；真实运行时按 QINGLONG_NOTIFY 设置通过青龙 notify.py 发送脱敏任务汇总。。
- `scripts/erke.py`：正式运行提交会员签到，可能增加积分和签到记录。
- `scripts/f1owkang_qingskyland_skyland.py`：实际运行时向设备认证服务注册本次设备认证信息；实际运行时换取鹰角授权及森空岛登录凭据；为明日方舟与终末地绑定角色执行每日签到并领取奖励；实际运行且通知开启时发送脱敏任务通知。
- `scripts/fnnasclub.py`：执行论坛签到，更新签到记录及论坛对应奖励；正式运行向已配置的青龙通知渠道发送脱敏总结。
- `scripts/forum_download.py`：启用 sign 或 sign_plus 时提交每日签到并可能获得签到奖励。；首页访问及页面读取可能增加论坛访问统计或触发站点每日访问奖励。；显式启用 download 后附件请求可能消耗论坛积分、增加下载次数或触发下载奖励。；显式开启 work 后提交广告点击和领取奖励，可能改变积分、任务状态及广告点击统计。。
- `scripts/fwxs_checkin.js`：通过 GET /qiandao 完成废文网签到，增加签到天数及服务端签到奖励（以站点规则为准）；正式执行结束后通过青龙通知渠道发送脱敏任务统计（可关闭）。
- `scripts/fxh.js`：实际执行每日签到，改变签到状态并由服务端发放积分；启用通知时调用青龙通知模块发送任务总结。
- `scripts/get_yys_cgvideo.py`：显式下载且非预演时创建保存目录、媒体文件和校验清单；实际运行且通知开启时调用青龙通知发送摘要。
- `scripts/get_yys_imagelinks.py`：仅在 YYS_DOWNLOAD 显式开启时创建素材目录并保存原画或视频文件；视频同时维护标题历史记录。；正式运行且通知开启时调用青龙通知模块发送脱敏任务结果。。
- `scripts/hellogithub.py`：正式运行时提交月刊内容及任务总结到青龙通知渠道；所有月刊消息提交成功后原子更新本地已发送期号状态文件。
- `scripts/hifiti_checkin.py`：向 HiFiTi 提交每日签到；向 HiFiHi 提交每日签到；真实模式按全局通知开关向青龙配置的渠道发送脱敏任务通知。
- `scripts/hlyl.py`：未签到时提交每日签到，可能获得积分和成长积分；显式开启时执行活动抽奖，可能消耗活动次数或积分并获得奖品；通知开启且正式运行时通过青龙组件发送任务总结。
- `scripts/hsay.py`：向沪上阿姨签到接口提交每日签到，领取活动奖励；实际模式下通过青龙通知模块发送脱敏任务总结。
- `scripts/huaruntong_wx.py`：正式运行提交签到与答题结果，可能获得签到积分；正式运行通过青龙通知组件发送脱敏任务汇总。
- `scripts/hykb_gamesign.js`：默认向所发现的未结束游戏活动提交每日签到，可能领取相应活动奖励。；仅在 HYKB_ALLOW_EXPERIENCE=1 且活动要求试玩时，记录官方试玩前置动作。；仅在 HYKB_ALLOW_SHARE=1 且活动要求分享时，记录官方分享前置动作。；真实模式且 QINGLONG_NOTIFY 开启、通知模块可用时，发送脱敏任务通知。。
- `scripts/ikuuu_checkin.py`：实际运行时邮箱密码登录并建立账号会话；实际运行时提交每日签到，可能增加账号流量；实际运行时通过青龙已有渠道及可选 PushPlus 发送脱敏任务摘要。
- `scripts/imaotai.py`：显式开启后提交商品申购申请；启用耐力任务后领取耐力奖励；正式运行且开启通知时发送脱敏总结。
- `scripts/index.js`：正式运行时创建明确指定的图片目录并保存收藏原图；替换未通过校验的普通图片文件；下载过程中创建临时文件并在结束时清理；通知开启且组件可用时发送脱敏任务结果通知，断网预演不外部投递。
- `scripts/iqiyi_checkin.py`：自然月签到改变签到记录并可能发放积分；网页积分签到改变积分及签到记录；启用会员抽奖时消耗机会并可能获得奖品；启用摇一摇时消耗活动机会并可能获得奖品；启用任务次数领取时记录浏览、预约电影任务并增加白金次数；启用白金抽奖时消耗活动机会并可能获得奖品；启用V7领取时可能改变会员权益或类型；正式模式开启通知时向配置渠道发送脱敏总结；启用 VIP 自动签到时改变签到记录并可能增加成长值；启用每日成长任务时记录任务参与、浏览或预约、完成通知，并可能领取成长奖励。
- `scripts/jc_checkin.py`：正式运行登录并建立账号会话；正式运行每日签到，可能增加机场签到流量或奖励；启用通知时发送脱敏统计；显式开启兼容推送时向 PushPlus 发送脱敏统计。
- `scripts/jcqd.py`：向所选站点提交登录并建立会话；向所选站点提交每日签到，可能获得流量或站点签到奖励；正式运行通过青龙通知模块发送脱敏任务摘要。
- `scripts/jingyiluntan_sign.py`：正式运行提交每日签到；仅在 JYLT_RATE=1 时提交热门帖 +1 评分和附言，消耗论坛允许的评分额度；正式运行按全局开关发送青龙通知。
- `scripts/jissbon.py`：实际执行时提交每日签到；实际执行时登记分享奖励；显式开启抽奖时消耗抽奖机会，可能消耗积分并获得奖品；启用通知时通过青龙通知模块发送脱敏总结。
- `scripts/jyj.py`：签到并领取积分或水滴奖励；创建及提交拍一拍和药材游戏记录，领取游戏奖励；转盘、酒柜及红包雨抽奖，可能消耗活动次数或积分；点赞文章及记录订阅、调研、分享和运动任务；种植指定药材及消耗水滴浇水；上传本人照片至官方授权存储，提交AI识别及活动拍照打卡；通知启用且适配器可用时向青龙通知渠道发送脱敏结果。
- `scripts/kgqq.py`：领取签到奖励，可能增加账号鲜花或道具。；开启抽奖后执行抽奖，可能消耗次数或活动资源并发放奖励。；开启音乐奖励后领取音乐卡片互动奖励，可能改变互动奖励状态及鲜花余额。；VIP 用户领取日奖励，改变领取状态并可能增加道具。；正式执行结束后，通过可用的青龙通知模块发送脱敏任务汇总。。
- `scripts/kjwj.py`：未签到时提交每日签到并获得积分；正式执行时按通知开关发送青龙任务通知。
- `scripts/kuaishou_reward_status.py`：。
- `scripts/kuku_daily.py`：领取每日登录任务积分；领取对话任务积分；正式运行时通过青龙通知模块发送脱敏结果。
- `scripts/kurobbs_sign.py`：库街区社区签到并领取对应奖励；鸣潮游戏签到并领取对应奖励；浏览帖子计入社区任务进度；显式开启后点赞帖子；显式开启后提交分享任务进度。
- `scripts/l.py`：正式运行的已登录页面请求可能由站点计入访问或浏览记录；是否更新由站点决定；正式运行且启用通知时调用青龙通知模块发送任务汇总。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：正式执行时提交 Leaflow 每日签到表单，记录账号签到并可能发放当日奖励；正式执行且通知启用时调用青龙通知模块发送脱敏任务汇总。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：正式运行在咔叽网单为已登录账号执行每日签到；通知开启且助手可用时发送脱敏任务汇总；预演仅尝试离线通知。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：正式运行调用 NodeSeek 签到接口，产生当日签到记录并领取签到奖励。；启用通知时向已配置的青龙通知渠道发送脱敏任务汇总。。
- `scripts/lizhixu_ql_script_hub_youdao.py`：正式运行刷新登录会话；正式运行同步奖励并增加云笔记空间；正式运行每日签到并领取空间奖励；默认正式运行领取三次广告空间奖励，可通过 YOUDAO_AD_REWARDS=0 关闭；启用通知时向青龙已配置渠道发送脱敏任务摘要。
- `scripts/lobsterai_checkin.py`：向官方接口提交每日签到，领取活动积分。；RT 自动续期会轮换账号令牌，并在本地写入私密续期缓存。；正式模式按配置发送脱敏青龙通知及可选 PushPlus 微信推送。。
- `scripts/loomy_daily.py`：正式默认执行刷新账号每日赠送积分。；显式批量或单项领取时上报新手任务完成状态并领取积分。；正式查询或领取确认全部结清时更新脚本目录中的 loomy_onboarding.json 本地结清记录，只存凭据指纹和任务进度。；启用通知且非预演时通过青龙组件或可选兼容通道发送脱敏总结。。
- `scripts/lynkco_qinglong_single.py`：每日签到并领取服务端奖励；默认上报文章分享并可能增加能量体积分，可用LYNKCO_DO_SHARE关闭；使用刷新令牌续期，服务端可能更新登录令牌状态；不写本地凭据文件；发送脱敏青龙通知及可选Bark推送；预演不发送网络通知。
- `scripts/main.py`：正式运行时在显式指定目录创建日期子目录并保存已验证的壁纸文件；不覆盖已有文件。；正式运行且启用通知时，调用青龙通知模块发送脱敏总结。。
- `scripts/mifan_optimized.py`：登录创建会话、登出结束本次会话；每日签到改变签到状态并可能获得米粒；显式点赞改变文章点赞状态；显式评论公开发布文本并可能获得米粒；显式补签改变历史签到状态并可能消耗资源；正式执行点赞或评论后保存本地账号进度；通知启用且可用时向已配置青龙渠道发送脱敏摘要。
- `scripts/mimotion.py`：正式登录会申请 Zepp 授权及登录令牌。；仅 MIMOTION_ACTION=upload 时上传本人提供的当天运动记录，修改 summary.stp.ttl；其它提供的记录字段保持原样，不合成心率或睡眠数据。；启用通知时调用青龙通知模块发送脱敏汇总，预演禁止联网。。
- `scripts/netease_task.py`：手机、网页与云贝签到改变签到记录或积分；领取已完成云贝任务奖励；领取 VIP 成长值；仅显式开启时提交模拟播放历史记录；正式执行且通知开启时发送青龙或备用渠道通知，并按配置发送 Bark 通知。
- `scripts/nga_checkin.py`：每日签到改变签到及奖励状态；显式开启时增加日常任务计数及奖励状态；显式开启时增加视频任务计数、免广告与 N币奖励状态；显式开启时提交分享记录并领取分享奖励。
- `scripts/nodeseek.py`：正式运行向 NodeSeek 提交签到并领取随机或固定奖励。；通知启用且助手可用时发送脱敏任务通知。。
- `scripts/nodeseek_checkin.py`：成功请求会记录 NodeSeek 当日签到并可能增加鸡腿余额；启用青龙通知时会向已配置的通知渠道发送脱敏任务汇总。
- `scripts/nte.py`：刷新用户中心令牌，可能轮换服务端会话凭据。；社区签到，可能增加经验和金币。；游戏角色签到，可能发放签到道具。；正式执行结束时通过已有青龙通知模块发送脱敏任务摘要。。
- `scripts/officeace_daily.py`：默认领取每日签到奖励和新人礼，可能增加积分；查询和预演不领取；实时模式通知开启且组件或兼容推送已配置时发送脱敏任务通知。
- `scripts/ole.py`：正式模式向 Ole 提交会员签到，可能增加签到记录及奖励积分；正式模式按青龙配置发送任务通知。
- `scripts/passnat_checkin.py`：向 PassNAT 提交每日签到并可能增加账号流量。
- `scripts/psnine.py`：向 PSNINE 提交每日祈祷签到，改变签到记录及服务发放的奖励；实时模式向配置的青龙通知渠道发送脱敏任务摘要。
- `scripts/pt_sign_v5.js`：向选中站点提交签到，可能增加站点奖励及连续签到计数；遇到 SafeLine 时提交挑战验证并更新当前进程内的会话 Cookie，不写入文件；实际运行后向已有青龙通知服务和可选 Webhook 发送脱敏任务总结；全局开关关闭时不发送。
- `scripts/qoder_airscript.js`：显式启用账号后领取可领活动奖励；必要时或仅刷新模式下刷新令牌，可能轮换刷新令牌；显式配置私有账号文件时写回轮换令牌；通知开启时投递青龙汇总及已配置的逐账号通知。
- `scripts/quark_signin.py`：实时模式下为尚未签到的账号完成每日签到并领取存储空间奖励；实时模式下启用通知时通过青龙发送脱敏任务摘要。
- `scripts/raccoon_daily.py`：正式模式请求 setting_info 触发每日积分发放。；正式模式默认领取桌面端、手机端一次性登录积分。；正式模式将确认结算的奖励状态写入本地哈希台账。；通知开启时尝试发送脱敏任务摘要。。
- `scripts/rainyun.py`：登录创建账号会话。；每日签到改变当日签到状态并领取积分。；退出登录结束当前账号会话。；正式运行时向已配置的青龙通知渠道发送任务汇总。。
- `scripts/rousi_checkin.js`：正式运行未签到账号时提交普通签到，改变签到记录并领取服务端积分奖励；正式运行且通知开启时向青龙配置的通知渠道发送脱敏总结；正式运行配置 PushPlus 时向该通知渠道发送脱敏总结。
- `scripts/sf.py`：分享登录创建账号会话；签到并领取签到礼包；按显式任务代码允许清单提交日常任务完成记录；领取任务积分奖励；正式运行发送青龙汇总通知。
- `scripts/sfsu_checkin.py`：执行每日签到；完成符合安全规则的积分及丰蜜任务并领取奖励；进行丰蜜大冒险并在容量不足时扩容；在 SF_AUTO_COUPON=1 时创建一笔生活特权券领取订单；在会员日窗口领取可用邀请奖励、消耗免费抽奖次数、领取任务奖励、合成并提取红包。
- `scripts/sgs.py`：每日签到；显式开启时写入文章阅读记录；显式开启时写入工社服务访问计数；显式开启时写入热门活动浏览计数；开启通知时向青龙配置的渠道发送脱敏汇总。
- `scripts/shuyi.py`：在书亦烧仙草账号执行签到并领取服务端发放的积分；实际执行时向青龙通知渠道发送脱敏任务总结；配置 PUSH_PLUS_TOKEN 时向 PushPlus 发送脱敏总结。
- `scripts/sign_in.py`：正式执行时向看雪论坛提交签到，可能增加账号积分；正式执行且通知开启时通过青龙发送脱敏任务总结。
- `scripts/skland_daily.py`：未配置 SKLAND_DID 时向上游设备服务注册临时设备标识；账密或通行证登录时换取授权和账号会话凭据；版区每日检票改变签到状态；浏览帖子可能增加任务浏览进度；显式启用 like 时点赞帖子；显式启用 share 时增加分享任务计数，不发布文案；正式运行时向已配置的青龙或自有通知渠道发送脱敏摘要；显式开启 attendance 时为明日方舟绑定角色签到并领取游戏奖励；显式开启 endfield 时为终末地绑定角色签到并领取游戏奖励。
- `scripts/skland_demo.py`：实际模式下明日方舟角色每日签到并领取奖励；实际模式下终末地角色每日签到并领取奖励；仅 send-code 动作向本人手机号发送登录短信验证码；实际模式下向数美服务登记生成设备标识；传入 did 时不执行；登录时签发账号授权凭据，可选刷新签名令牌；启用通知且模块可用时发送脱敏任务通知。
- `scripts/skyland.py`：向数美服务提交模拟浏览器指纹并生成设备凭据；通过鹰角授权接口生成登录授权并取得森空岛会话凭据；为明日方舟绑定角色每日签到并领取签到奖励；为终末地绑定角色每日签到并领取签到奖励；正式运行时通过青龙通知渠道发送脱敏任务统计。
- `scripts/smzdm_checkin.js`：在什么值得买账号上执行每日签到并改变当日签到状态；满足条件时领取连续签到额外奖励并改变账号奖励状态；显式选择 lottery 或 all 后提交转盘抽奖，可能消耗抽奖机会或活动资产并获得奖励；显式启用 value 或 both 后对好价提交点值，改变账号投票状态；显式启用 article 或 both 后对好文提交点赞，改变账号点赞状态；显式选择 upstream-lottery 后对原固定活动提交一次抽奖，可能消耗机会或活动资产并获得奖励。
- `scripts/ssl.py`：实际模式下通过青龙通知通道发送证书检查报告；不修改 Cloudflare DNS、证书或账号数据。
- `scripts/sudojia_33agilestudio.js`：登录建立账户会话；提交每日签到，按服务端规则获得积分；正式运行且启用通知时，通过青龙通知模块发送脱敏任务摘要。
- `scripts/sudojia_allgirls.js`：未签到时执行每日签到，可能获得平台签到积分。
- `scripts/sudojia_amx.js`：未签到时执行每日签到，可能获得积分。
- `scripts/sudojia_authcheck.js`：显式允许时，海澜之家游戏登录可能创建会话；已移除默认邀请人绑定；显式允许时，老板电器用户接口可能同步账号；请求已设置不需要同步；通过青龙通知模块发送脱敏汇总；断网预演仅生成通知摘要。
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
- `scripts/sudojia_jlc_yj.js`：开源平台每日签到增加积分；下单助手每日签到增加金豆；显式授权后领取待选奖励并最多补签一次。
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
- `scripts/sudojia_v2ex.js`：领取 V2EX 每日登录奖励，增加账号余额；正式运行且通知开启时发送青龙任务结果通知。
- `scripts/sudojia_wnna.js`：未签到时执行每日签到并获得服务端发放的奖励；正式运行且通知启用时发送青龙任务通知。
- `scripts/sudojia_xhn.js`：登录产生授权会话；每日签到可能增加账号积分。
- `scripts/sudojia_xiangwan.js`：正式运行使用账号密码登录，可能创建服务端会话；正式运行每日签到并领取玩豆；显式启用缓存后写入受限权限的本地 Token 文件；通知开启且模块可用时发送脱敏任务结果。
- `scripts/sudojia_xiaomi_community.js`：每日调用微信签到接口增加成长值；启用通知且正式执行时，通过青龙已配置通知渠道发送脱敏结果。
- `scripts/sudojia_xinxi.js`：每日签到并可能获得喜点；启用免费抽奖后消耗一次免费机会并可能获得奖励；启用奖励任务后提交分享任务记录与商城浏览完成记录并可能获得喜点；启用会员权益任务后提交查看记录并可能获得喜点。
- `scripts/sudojia_xpfarm.js`：每日签到及其奖励入账；显式启用后变更所选任务完成状态并领取奖励；显式启用后消耗肥料以增加肥力；显式启用后消耗水滴及肥力并推进种树成长；正式运行时通过青龙已配置渠道发送脱敏总结。
- `scripts/sudojia_znds.js`：正式运行执行每日签到，可能获得积分或奖励；仅配置 ZNDS_VISIT_UID 时访问指定他人空间，可能产生足迹或访问奖励；正式运行且通知启用时发送脱敏任务通知。
- `scripts/sudojia_zxice.js`：未签到时提交每日签到并领取奶滴奖励；正式模式按通知配置发送任务结果通知。
- `scripts/supertopicsign.py`：对关注的超话执行签到，改变签到状态。
- `scripts/synspoint.py`：会员签到及接口对应积分变化；提交浏览会员商城任务并可能获取积分；显式开启后创建商品上播预约，再取消本次成功创建的预约；正式运行时按全局开关发送脱敏总结通知。
- `scripts/tencent_video_checkin.py`：实际执行时提交每日签到，可能增加 V力值；实际执行时领取每日观看奖励，可能增加 V力值；通知开启且实际执行时通过可用渠道发送脱敏任务总结。
- `scripts/tieba_checkin.py`：正式执行时提交关注贴吧签到，改变对应贴吧当日签到状态及可能产生签到奖励。；仅显式开启成长任务且 Cookie 同时含 BDUSS 和 CUID 时提交 APP 成长每日签到，改变当日成长签到状态及可能产生的成长奖励。；正式执行且通知开启、青龙组件可用时发送脱敏任务汇总通知。。
- `scripts/tjd_daily.py`：社区签到增加金币和经验；浏览帖子增加阅读及任务进度；绑定游戏签到领取奖励；明确启用后给帖子点赞；明确启用后上报帖子分享回调；可选密码重登创建登录会话，可能使旧会话失效。
- `scripts/trae_checkin.py`：签到领取积分；续期在服务端轮换刷新凭据；以 0600 权限原子更新本地令牌缓存、签到状态及冷却文件；显式 login 发起官方授权、轮换刷新凭据并以 0600 权限保存新 auth 文件；正式运行向青龙通知器及显式配置的企业微信、PushPlus 发送脱敏摘要；长效 Cookie 续期更新服务端网页会话，并以 0600 权限缓存网页会话及访问令牌；预演向本地青龙通知器提交脱敏摘要，禁止网络投递。
- `scripts/tsthb_checkin.py`：向官方签到接口提交每日签到，可能获得积分或奖励；正式运行且通知开启时，通过已有青龙通知模块发送脱敏结果。
- `scripts/ty_netdisk_checkin.py`：正式模式每日签到可能增加账号奖励空间；启用签到奖励开关后，正式模式可能消耗当天已有签到抽奖机会并增加奖励空间；启用相册奖励开关后，正式模式可能消耗已有相册任务抽奖机会并增加奖励空间；正式模式按通知配置发送脱敏任务结果。
- `scripts/tyqhdraw.py`：登录创建账号会话；显式开启时兑换抽奖，可能消耗资产或抽奖机会并获得奖品；抽奖遇到滑块时提交验证码验证；启用通知时通过青龙通知渠道发送脱敏任务统计。
- `scripts/valorantstore.py`：实时模式调用认证接口刷新账号票据，仅保存在当前独立会话内存中。；通知开启时向已配置青龙通知渠道发送脱敏商店与任务总结。；通知开启且配置 Telegram 时发送商品长图；生成的本地临时图片在发送后删除。。
- `scripts/vortexa_free_claim.js`：使用密码或刷新 Cookie 登录时创建或续期服务端登录会话；更新的访问 Token 和 Cookie 仅保存在本次进程内，不写文件。；仅在 VORTEXA_CLAIM 开启且产品套餐明确免费时提交免费主机领取，创建账号免费主机服务。；启用通知时通过已有青龙 sendNotify.js 发送脱敏任务总结；预演通知受断网保护。。
- `scripts/wangchao.py`：实时登录会建立账号及活动服务会话；默认浏览未读文章并提交阅读记录，改变每日阅读进度；启用 WANGCHAO_BONUS 时浏览活动文章入口，可能改变浏览记录；启用 WANGCHAO_LOTTERY 时抽奖一次，消耗次数并产生中奖或参与记录；启用 QINGLONG_NOTIFY 时通过青龙通知渠道发送脱敏任务总结；预演通知禁止网络。
- `scripts/wentiweilaihui.py`：未签到时执行文体未来荟每日签到，可能增加积分；正式模式启用通知时发送脱敏任务总结。
- `scripts/workbuddy.py`：每日签到及服务端积分、连签奖励状态变更。；配置刷新令牌且访问令牌过期时向服务端申请续期，仅在进程内更新凭据。；正式运行且通知启用时发送脱敏青龙任务总结。。
- `scripts/workbuddy_daily.py`：默认进行每日签到、领取已完成成长任务奖励、领取旅行奖励或派遣Buddy旅行；显式成长任务可能创建模型对话、消耗积分并发送模拟活跃事件，变更任务登记与成长进度；上报成功不代表真实桌面操作成功；显式抽奖消耗抽奖次数，盲盒消耗能量，补签消耗补签卡，连签兑换和礼包补偿领取奖励；配置私有缓存并触发续期时轮换认证令牌且保存至本人指定文件；实际运行向青龙通知模块发送脱敏摘要；断网预演仅模拟通知；国际版活动开放且未领取时领取每日奖励；国际版显式保活创建模型对话与活跃记录，可能消耗积分；国际版显式--refresh轮换认证令牌并保存至本人指定私有缓存；仅显式 --intl --trial 领取一次性专家加油包，不加入默认定时任务。
- `scripts/wps_clock_in.py`：。
- `scripts/yht.py`：参加种植活动；消耗活动肥料进行施肥；满足条件时领取活动奖励；开启 YHT_SIGN 后提交每日签到并领取签到奖励；开启 YHT_HELP 后为本次配置的其他账号助力；通知开启时调用青龙通知发送总结；断网预演阻止联网和派生进程。
- `scripts/youdao.py`：刷新账号登录会话。；领取每日同步奖励并增加账号空间。；提交每日签到并领取空间奖励。；提交三次广告奖励请求并增加账号空间。；实际运行时通过青龙发送脱敏通知。。
- `scripts/yyshuijuantime.py`：正式运行在显式配置路径创建或更新活动 JSON 文件，必要时创建其父目录；正式运行通知开启时，通过青龙现有通知模块发送任务摘要。
- `scripts/zcode_cn_daily.py`：实际领取时发放或变更账号套餐权益。；仅 ZCODE_ACTIVATION=1 且非只读、非预演时补报启动和日活事件，可能影响套餐资格。；实际模式且通知启用时发送脱敏任务总结。。
- `scripts/zippo.py`：签到增加积分；收藏商品及领取积分；显式取消本轮收藏；记录分享任务及领取积分；提交标签和星级评价及领取积分；显式绑定指定推荐人；真实运行向青龙配置的通知渠道发送摘要。
- `scripts/zodgame_test.py`：提交每日签到；首次加入 Bux 广告任务；记录广告观看完成并领取积分；启用通知时发送脱敏任务总结。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/139_yunduo.py`：上游 `deeplee/personal-scripts` / `139_yunduo.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。
- `scripts/2cycdx.py`：上游 `Tgkkez/2cycdx_Autosignin` / `autosignin.py` / `9afc3b1513b1f0c683e0eda992c1c33d627d9996`。
- `scripts/51cto_sign.js`：上游 `huwangkeji/51cto_sign_authed` / `51cto_sign.js` / `c8231e0c5a52fdcd5c6020a3522c7b2c65a1aa84`。
- `scripts/999.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/999/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/acfun.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/acfun/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/agentrouter.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/agentrouter/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/airport.py`：上游 `CN-Grace/QinglongScripts` / `Airport.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/akile_checkin.py`：上游 `GGBondHere/QingLongScripts` / `scripts/akile_checkin.py` / `79238495c2489b52a6cc001ba9d6703ae6d57955`。
- `scripts/aliyundrive_checkin.js`：上游 `huwangkeji/aliyundrive_checkin` / `aliyundrive_checkin.js` / `267ee025840c5b55dce5b5e1e365fb52ac500fce`。
- `scripts/aliyunpan_checkin.py`：上游 `agluo/ql-script-hub` / `aliyunpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/aolaxing.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/aolaxing/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/api_hax.py`：上游 `OreosLab/checkinpanel` / `api_hax.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。
- `scripts/arknightsbanner.py`：上游 `CN-Grace/QinglongScripts` / `ArknightsBanner.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/atxyq.py`：上游 `Rookie-wb-WH/ql_scripts` / `atxyq.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/auto_buy.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/shyp/auto_buy.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/autoclaw_cn_daily.py`：上游 `L0NE-6/AutoClaw-Daily` / `autoclaw_cn_daily.py` / `745a15b42d58bcaf9bb50920f5405e04b4f4964b`。
- `scripts/autosignin.js`：上游 `wang-st/aliyunSignIn` / `autoSignin.js` / `e81b2732652aadea5ee9920eb0d0adfe07dffa91`。
- `scripts/autosignin.py`：上游 `AkiyaKiko/EhentaiAutoSignIn` / `autosignin.py` / `c00c3d42a61b7f526dd41b8df157444380898e57`。
- `scripts/baidu.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/baidu/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/baiduwangpan_checkin.py`：上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/baiduwp.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/baiduwp/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/bilibili.py`：上游 `CN-Grace/QinglongScripts` / `Bilibili.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/bsly_draw.py`：上游 `cloudcranes/some_scripts` / `bsly_draw.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/bugutv.py`：上游 `MonjackWon/bugutv_AutoSignin` / `bugutv.py` / `32af515b2ae28a2cb7bf0051966804936d4ae897`。
- `scripts/bwcj.py`：上游 `Rookie-wb-WH/ql_scripts` / `bwcj.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/caigamer.js`：上游 `unitaryhighs/ql_sign_script` / `sign/caigamer.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。
- `scripts/cdrail.py`：上游 `agluo/ql-script-hub` / `CDRail.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。
- `scripts/chevrolet.js`：上游 `NaroisCool/naro-scripts` / `chevrolet.js` / `c2ffa8af2089bd98e1ed623c7a25d49b60ca0fdd`。
- `scripts/ck_2nzz.py`：上游 `yuxian158/check` / `dailycheckin_scripts/ck_2nzz.py` / `723c834f121ff4eef2dec7afe521071a7efff1a9`。
- `scripts/ck_acfun.py`：上游 `OreosLab/checkinpanel` / `ck_acfun.py` / `911402e4b2e559ffd62c4949a971ddd6834edd7d`。
- `scripts/codearts_daily.py`：上游 `L0NE-6/CodeArts-Daily` / `codearts_daily.py` / `c337a9340877cdf7afef0a679f3d020d28183140`。
- `scripts/comicai_ai_cookie.py`：上游 `CSDN2024/QianDaoMZH` / `comicai-ai-cookie.py` / `b99c67e46d1e74d2fd3a0bff7cac3f83e5ee6903`。
- `scripts/crealitycloud_checkin.py`：上游 `xz0609/crealitycloud-checkin-ql` / `crealitycloud_checkin.py` / `ba2872b75372f62157b1f0cdcdf57ed59f9bd1fb`。
- `scripts/dachao.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/dachao/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/daily_benefits.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/wps/daily_benefits.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/dailynewscn.js`：上游 `unitaryhighs/ql_sign_script` / `hot/dailynewscn.js` / `caa96862c9a31521347217b3b20b8ba3f6413c18`。
- `scripts/ddnsto.py`：上游 `cloudcranes/some_scripts` / `ddnsto.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/deepflood_checkin.py`：上游 `agluo/ql-script-hub` / `deepflood_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/durex.py`：上游 `Rookie-wb-WH/ql_scripts` / `durex.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/enshan_checkin.py`：上游 `agluo/ql-script-hub` / `enshan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/epicfreegames.py`：上游 `CN-Grace/QinglongScripts` / `EpicFreeGames.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/erke.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/erke/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/f1owkang_qingskyland_skyland.py`：上游 `f1owkang/QingSkyland` / `skyland.py` / `563c86c9d5965b5fc622e1cb33963346b661f26c`。
- `scripts/fnnasclub.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/fnnasclub/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/forum_download.py`：上游 `nuthx/auto-sign` / `src/general/forum_download.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。
- `scripts/fwxs_checkin.js`：上游 `zhui-zi/fwcheckin` / `fwxs_checkin.js` / `7793a795d603df34f0ebdbc7d6810427f84f59c6`。
- `scripts/fxh.js`：上游 `xingly-cn/QLPanelScript` / `fxh.js` / `8c0323999253b7a0d8e47ff1136a562fedb3c980`。
- `scripts/get_yys_cgvideo.py`：上游 `qluser-alan/some_scripts` / `阴阳师/get_yys_cgvideo.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/get_yys_imagelinks.py`：上游 `cloudcranes/some_scripts` / `阴阳师/get_yys_imagelinks.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/hellogithub.py`：上游 `CN-Grace/QinglongScripts` / `HelloGithub.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/hifiti_checkin.py`：上游 `agluo/ql-script-hub` / `HiFiti_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/hlyl.py`：上游 `cloudcranes/some_scripts` / `hlyl.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/hsay.py`：上游 `Rookie-wb-WH/ql_scripts` / `hsay.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/huaruntong_wx.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/huaruntong_wx/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/hykb_gamesign.js`：上游 `qidouhai/checkbox` / `scripts/hykb_gamesign.js` / `048a5d58b54a90489e6508ae1f90525d6b21b8b1`。
- `scripts/ikuuu_checkin.py`：上游 `agluo/ql-script-hub` / `ikuuu_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/imaotai.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/imaotai/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/index.js`：上游 `cloudcranes/some_scripts` / `Download_pixiv/index.js` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/iqiyi_checkin.py`：上游 `deeplee/personal-scripts` / `iqiyi_checkin.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。
- `scripts/jc_checkin.py`：上游 `kerncoola/JC_CheckIn` / `JC_CheckIn.py` / `71362b20abdad2711ddc2e4321ef33b3ebcc64c5`。
- `scripts/jcqd.py`：上游 `Rookie-wb-WH/ql_scripts` / `jcqd.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/jingyiluntan_sign.py`：上游 `CSDN2024/QianDaoMZH` / `JingYiLunTan-sign.py` / `b99c67e46d1e74d2fd3a0bff7cac3f83e5ee6903`。
- `scripts/jissbon.py`：上游 `Rookie-wb-WH/ql_scripts` / `jissbon.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/jyj.py`：上游 `Rookie-wb-WH/ql_scripts` / `jingyoujia/jyj.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/kgqq.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/kgqq/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/kjwj.py`：上游 `cloudcranes/some_scripts` / `kjwj.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。
- `scripts/kuku_daily.py`：上游 `L0NE-6/KukuAI-Daily` / `kuku_daily.py` / `6912419c6b29365bb7b3172cc3c18bf7b763812d`。
- `scripts/kurobbs_sign.py`：上游 `yongyeym/AutoSign_QingLong` / `kurobbs_sign.py` / `f13a88e488c2d396e24cce8e9b6e27eefcbccad6`。
- `scripts/l.py`：上游 `lzylipu/l-checkin` / `main.py` / `2c71083614d6ef87c8b502e1440fec3b08ab59c3`。
- `scripts/leaflow_checkin_pyleaflow_checkin.py`：上游 `agluo/ql-script-hub` / `archive/leaflow_checkin.pyleaflow_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/littlewuh_qinglongbox_dailycheckin_scripts.py`：上游 `LittleWuh/qinglongbox` / `dailycheckin_scripts/ck_2nzz.py` / `02e1c7a0788a62a7434f686118506ca5702fba24`。
- `scripts/lizhixu_ql_script_hub_nodeseek.py`：上游 `lizhixu/ql-script-hub` / `nodeseek_checkin.py` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。
- `scripts/lizhixu_ql_script_hub_youdao.py`：上游 `lizhixu/ql-script-hub` / `youdao.py` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。
- `scripts/lobsterai_checkin.py`：上游 `L0NE-6/LobsterAI-AutoCheckin` / `lobsterai_checkin.py` / `4e4c291a2f616ef865e18a1c8026939754bfc712`。
- `scripts/loomy_daily.py`：上游 `L0NE-6/Loomy-Daily` / `loomy_daily.py` / `3d0f19b0b6486ff9096507805a5f9d061604058f`。
- `scripts/lynkco_qinglong_single.py`：上游 `zhaosongbing/LynkCoHelper-QingLong` / `qinglong/lynkco_qinglong_single.py` / `7b9330aeae5e458f00de92b46bbd31bbf99c95aa`。
- `scripts/main.py`：上游 `cloudcranes/some_scripts` / `Download_wallhaven/main.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/mifan_optimized.py`：上游 `eggv/MeeFan-DailyCheckIn` / `mifan_optimized.py` / `dd3668c8b870fe172ac97bcf96055ddcfceb6d49`。
- `scripts/mimotion.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/mimotion/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/netease_task.py`：上游 `Han-cy77/Qinglong_auto` / `netease_task.py` / `4bac7c4f709db60a648c4bd498e99f9c7e66b63b`。
- `scripts/nga_checkin.py`：上游 `agluo/ql-script-hub` / `nga_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/nodeseek.py`：上游 `CN-Grace/QinglongScripts` / `Nodeseek.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/nodeseek_checkin.py`：上游 `agluo/ql-script-hub` / `nodeseek_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/nte.py`：上游 `Candy-QAQ/NTE-Auto-Sign` / `nte.py` / `38d77e1f7dc784f2baeb49c41cd4352deadf2b24`。
- `scripts/officeace_daily.py`：上游 `L0NE-6/OfficeAce-Daily` / `officeace_daily.py` / `a6759a929b20a64fa44914f5115a1d3fc230ce54`。
- `scripts/ole.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/ole/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/passnat_checkin.py`：上游 `agluo/ql-script-hub` / `passnat_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/psnine.py`：上游 `nuthx/auto-sign` / `src/special/psnine.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。
- `scripts/pt_sign_v5.js`：上游 `Flyingpen/PT-sign` / `PT-sign-V5.js` / `5c6cf9d38020c327f9a30c3977eb7765e4d2c5c2`。
- `scripts/qoder_airscript.js`：上游 `wallechfox/qoder-checkin` / `qoder-checkin-金山云文档/Qoder签到-金山文档AirScript.js` / `19ab6365c1f0759bb424a3d69e7de8dca89bf75d`。
- `scripts/quark_signin.py`：上游 `agluo/ql-script-hub` / `quark_signin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/raccoon_daily.py`：上游 `L0NE-6/Raccoon-Daily` / `raccoon_daily.py` / `4e99a3b53829faf3ae228755b0f4c32859d25425`。
- `scripts/rainyun.py`：上游 `cloudcranes/some_scripts` / `rainyun.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/rousi_checkin.js`：上游 `373065025/rousi-checkin` / `rousi_checkin.js` / `627ec698dc9d35f69f44e479366a7c31dd46489c`。
- `scripts/sf.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/sf/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/sfsu_checkin.py`：上游 `agluo/ql-script-hub` / `SFSU_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/sgs.py`：上游 `Rookie-wb-WH/ql_scripts` / `sgs.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/shuyi.py`：上游 `Rookie-wb-WH/ql_scripts` / `shuyi.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/sign_in.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/kanxue/sign_in.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/skland_daily.py`：上游 `siwuli/skland-daily` / `skland_daily.py` / `c6159b4ca574b4493ae8b94e56a861c7e9e06955`。
- `scripts/skland_demo.py`：上游 `nuthx/auto-sign` / `skland/skland-demo.py` / `a8d2c229bac693daebe1535bca4cfd49733b632d`。
- `scripts/skyland.py`：上游 `CN-Grace/QinglongScripts` / `skyland.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/smzdm_checkin.js`：上游 `ump45nose/smzdm-checkin-ql` / `checkin.js` / `6b9eaced964c348efb46d2c13a45ab5c66caaea8`。
- `scripts/ssl.py`：上游 `CN-Grace/QinglongScripts` / `SSL.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/sudojia_33agilestudio.js`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_33agilestudio.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_allgirls.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_allGirls.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_amx.js`：上游 `sudojia/AutoTaskScript` / `src/wx_mini/sudojia_amx.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/sudojia_authcheck.js`：上游 `sudojia/AutoTaskScript` / `src/other/sudojia_authCheck.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
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
- `scripts/supertopicsign.py`：上游 `Hellager/weibo_supertopic_sign` / `supertopicsign.py` / `66e46ec082cc87100e7d99e8ed8e6c478c5e3833`。
- `scripts/synspoint.py`：上游 `Rookie-wb-WH/ql_scripts` / `synspoint.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/tencent_video_checkin.py`：上游 `deeplee/personal-scripts` / `tencent_video_checkin.py` / `c8c7c0f4fd1802df86c32a86c26b5c26cfef5023`。
- `scripts/tieba_checkin.py`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_tieba.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
- `scripts/tjd_daily.py`：上游 `SkyBlue997/tjd-daily` / `tjd_daily.py` / `1df775d4c5eea379111edecf53a62b447b756770`。
- `scripts/trae_checkin.py`：上游 `L0NE-6/Trae-AutoCheckin` / `trae_checkin.py` / `38b1d919760ed9a36dfe6873be8765f8cafaff3f`。
- `scripts/tsthb_checkin.py`：上游 `agluo/ql-script-hub` / `tsthb_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/ty_netdisk_checkin.py`：上游 `agluo/ql-script-hub` / `ty_netdisk_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/tyqhdraw.py`：上游 `Rookie-wb-WH/ql_scripts` / `tyqhDraw.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/valorantstore.py`：上游 `CN-Grace/QinglongScripts` / `ValorantStore.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/vortexa_free_claim.js`：上游 `lizhixu/ql-script-hub` / `vortexa_free_claim.js` / `ac591a320092dcaeaf236b7c2b6acfd28981e589`。
- `scripts/wangchao.py`：上游 `Rookie-wb-WH/ql_scripts` / `wangchao.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/wentiweilaihui.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/huaruntong/wentiweilaihui/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/workbuddy.py`：上游 `Cat-zaizai/ZaiZaiCat-Checkin` / `script/workbuddy/main.py` / `d6a334e43d0a0c8f41b039cd410be33593efc35b`。
- `scripts/workbuddy_daily.py`：上游 `L0NE-6/WorkBuddy-Daily` / `workbuddy_daily.py` / `e030ebde37411a90e0a3e35b88993e5686c7e1dd`。
- `scripts/wps_clock_in.py`：上游 `cloudcranes/some_scripts` / `invalid/wps_clock_in.py` / `f62b50fe0a961ea8a8707682723b080c0a5d1142`。
- `scripts/yht.py`：上游 `Rookie-wb-WH/ql_scripts` / `yht.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/youdao.py`：上游 `Sitoi/dailycheckin` / `dailycheckin/youdao/main.py` / `135cc236e59ac4f14bcddc44acb3cbb3ed6010b5`。
- `scripts/yyshuijuantime.py`：上游 `CN-Grace/QinglongScripts` / `YysHuijuanTime.py` / `a40a2b080e0160bd8e0b0b807081115537b87153`。
- `scripts/zcode_cn_daily.py`：上游 `L0NE-6/ZCode-Daily` / `zcode_cn_daily.py` / `68e3adf4b5deb036f2a992a5aca24f02f3a64ade`。
- `scripts/zippo.py`：上游 `Rookie-wb-WH/ql_scripts` / `zippo.py` / `08e5c06461c4a0112ea3735f48fe671734bb7707`。
- `scripts/zodgame_test.py`：上游 `miaonai/zodgame-ql` / `zodgame-test.py` / `6494977a250c71a8fcd00b48a4cf3e1249da4e4c`。
