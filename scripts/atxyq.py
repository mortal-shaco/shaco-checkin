#!/usr/bin/env python3
# name: 艾特校园圈
# cron: 21 10,23 * * *
# author: 清风
# Upstream: Rookie-wb-WH/ql_scripts, atxyq.py
# License: MIT (effectiveLicense supplied by source catalog).
"""艾特校园圈独立维护版（Python 3.9+，仅标准库）。

在微信小程序内登录，抓取自己发往 api.atxz.cool 的请求头 Authorization 与
Uid，原样填写 atxyqs，每个非空行 Authorization#Uid；只在第一个 # 拆分。
旧版 @ 多账号分隔已迁移为换行，勿填他人凭据。凭据失效后重新登录抓取。
每天 10:09、23:09 运行。默认查询信息、签到、领取普通任务奖励、查询积分。
ATXYQ_LIKE=1 开启最多两篇文章各点赞后取消点赞（原上游连续动作）。
ATXYQ_POST=1 开启发布一篇动态；一言优先，失败回退本地文本，可用
ATXYQ_LOCAL_TEXT 覆盖本地正文。附图可选：ATXYQ_IMAGE_NAME 填自己的已上传
图片文件名，ATXYQ_IMAGE_DIR 填该图片的服务目录；不会伪造或上传图片。
atxyqDel 默认 0；整数非零开启删除自己最近十篇列表内的帖子，谨慎开启。
ATXYQ_ASSIST 可填自己确认的目标 JSON，字段 topicId、text、userId、schoolId；
开启 ATXYQ_HELP_LIKE=1 或 ATXYQ_INVITE=1 才执行助力或邀请绑定。
不读取上游远程助力配置或广告，不默认删除、公开互动或绑定邀请。
ATXYQ_DRY_RUN=1 完全断网，仅验证配置和动作计划（含通知模拟），不是业务成功。
QINGLONG_NOTIFY 默认 1；置 0/false/no/off 禁用；可指定 QINGLONG_NOTIFY_DIR。
所有账号独立处理，任一失败退出非零；未知响应失败闭合，不输出原始响应。
"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '艾特校园圈'
BASE = 'https://api.atxz.cool/api/'
OFF = {'0', 'false', 'no', 'off'}
LOCAL = '珍惜校园时光，每一天都是新的开始。'

class TaskError(Exception):
    pass


def log(text):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), text), flush=True)


def flag(name):
    value = os.getenv(name, '0').strip().lower()
    if value not in OFF | {'1', 'true', 'yes', 'on'}:
        raise TaskError('%s 必须填写 0 或 1' % name)
    return value not in OFF


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，避免凭据跨站发送')


def http(url, method='GET', headers=None, query=None, data=None, form=False,
         limit=1048576, timeout=15):
    if query:
        url += '?' + urllib.parse.urlencode(query)
    hdr = dict(headers or {})
    body = None
    if data is not None:
        body = (urllib.parse.urlencode(data).encode() if form else
                json.dumps(data, ensure_ascii=False).encode())
        hdr['Content-Type'] = ('application/x-www-form-urlencoded' if form else 'application/json')
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态未成功')
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise TaskError('响应超过大小限制')
        return json.loads(raw.decode('utf-8')) if raw.strip() else None
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError('HTTP 请求失败（状态 %d）' % exc.code) from None
    except Exception:
        raise TaskError('网络、超时或响应解析失败') from None


def normalized(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def public_text():
    fallback = normalized(os.getenv('ATXYQ_LOCAL_TEXT', LOCAL))
    if not fallback or len(fallback) > 280:
        raise TaskError('ATXYQ_LOCAL_TEXT 必须为 1 至 280 字')
    try:
        # 单独创建请求，不向文本提供方传递账号请求头或凭据。
        d = http('https://v1.hitokoto.cn/?encode=json', limit=16384, timeout=8)
        text = normalized(d.get('hitokoto'))
        author, source = normalized(d.get('from_who')), normalized(d.get('from'))
        if not text:
            raise TaskError('缺少正文')
        if author and source:
            text += ' —— %s《%s》' % (author, source)
        elif source:
            text += ' ——《%s》' % source
        elif author:
            text += ' —— %s' % author
        if len(text) > 280:
            raise TaskError('正文过长')
        log('一言正文与署名获取成功')
        return text
    except Exception:
        log('⚠️ 一言不可用或内容不合格，使用本地正文')
        return fallback


def explicit_success(d):
    # 用于上游只检查 HTTP 200、未给出业务契约的动作；未知结果必须失败。
    return d is True or (isinstance(d, dict) and d.get('success') is True)


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


class Account:
    def __init__(self, idx, line, cfg, dry):
        self.idx, self.line, self.cfg, self.dry = idx, line, cfg, dry
        self.stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        self.school = None
        self.tasks = None
        self.identity = False
        self.headers = {}
        self.uid = ''

    def api(self, path, method='GET', query=None, data=None, form=False):
        if self.dry:
            raise TaskError('预演禁止 HTTP')
        return http(BASE + path, method, self.headers, query, data, form)

    def step(self, title, action=None, enabled=True, ready=True):
        self.stats['total'] += 1
        start = time.monotonic()
        prefix = '账号 %d · 阶段 %d %s' % (self.idx, self.stats['total'], title)
        log(prefix + ' 开始')
        try:
            if not enabled:
                outcome, detail = 'skipped', '未开启可选动作'
            elif not ready:
                outcome, detail = 'failed', '前置阶段失败，未发送请求'
            elif self.dry:
                outcome, detail = 'skipped', 'DRY_RUN：配置有效，模拟动作，不发送请求'
            else:
                detail = action() or '已验证成功'
                outcome = 'success'
        except TaskError as exc:
            outcome, detail = 'failed', str(exc)
        except Exception:
            outcome, detail = 'failed', '响应字段或业务契约不符合预期'
        self.stats[outcome] += 1
        log('%s %s %s（%.2f 秒）' % (prefix, {'success':'✅','skipped':'⏭️','failed':'❌'}[outcome], detail, time.monotonic()-start))
        return outcome != 'failed'

    def user(self):
        d = self.api('atUserInfoDetails/getUserInfo', query={'userId':self.uid})
        if not isinstance(d, dict) or not isinstance(d.get('nickName'), str) or not isinstance(d.get('userInfo'), dict):
            raise TaskError('账号信息无法验证')
        # 仅打印官方昵称，不打印 UID 请求头、手机号、设备或会话字段。
        nickname = d['nickName'].replace('\n',' ').replace('\r',' ')
        if self.headers['Authorization'] in nickname:
            raise TaskError('身份字段包含凭据，拒绝输出')
        self.identity = True
        return '官方昵称：' + nickname

    def schools(self):
        d = self.api('integralSignSch/self')
        if not isinstance(d, list) or not d or not d[0].get('enabled') or not d[0].get('schId'):
            raise TaskError('学校签到未启用或学校信息无效')
        self.school = d[0]['schId']
        return '学校信息验证成功'

    def task_list(self):
        d = self.api('integralTask/self', query={'schoolId':self.school,'sort':'sort'})
        if not isinstance(d, list):
            raise TaskError('任务列表格式不符')
        tasks = {}
        for item in d:
            t = item['integralTask']
            if not t.get('id') or not isinstance(t.get('name'), str) or not number(t.get('value')):
                raise TaskError('任务字段无效')
            tasks[t['name']] = t
        self.tasks = tasks
        return '已验证 %d 项任务' % len(tasks)

    def sign(self):
        d = self.api('integralSignUser/sign')
        if not isinstance(d, dict) or 'message' in d or not number(d.get('running')) or not number(d.get('points')):
            raise TaskError('签到未返回可验证的连续天数与积分')
        return '签到成功：连续 %s 天，获得 %s 分' % (d['running'], d['points'])

    def articles(self, own=False):
        d = self.api('atReleaseInfo/userPage' if own else 'atReleaseInfo/queryMiniIndex', query=(
            {'createBy':self.uid,'size':'10','page':'0','releaseType':'1'} if own else
            {'schoolId':self.school,'sort':'createTime,desc','size':'10','page':str(random.randint(1,3)), 'releaseType':'0','status':'0'}))
        if not isinstance(d, dict) or not isinstance(d.get('content'), list):
            raise TaskError('文章列表格式无效')
        return d['content']

    def like(self):
        articles = self.articles()[:2]
        for article in articles:
            payload = {'releaseId':article['id'],'user':{'id':self.uid},'text':article['text'],'toUser':article['user']['id']}
            # 原接口为切换状态，保留上游成对操作；结果顺序不符即停止。
            if self.api('atReleaseInfoLike','POST',data=payload) is not True:
                raise TaskError('点赞未返回 true；停止切换，避免额外变更')
            log('✅ 点赞业务返回 true')
            time.sleep(random.uniform(2,4))
            if self.api('atReleaseInfoLike','POST',data=payload) is not False:
                raise TaskError('取消点赞未返回 false')
            log('✅ 取消点赞业务返回 false')
        return '已验证 %d 篇文章的成对点赞操作' % len(articles)

    def post(self):
        images = []
        if self.cfg['image_name']:
            d = self.api('ossImg/add', query={'url':self.cfg['image_name'],'dir':self.cfg['image_dir'],'userId':self.uid})
            if not isinstance(d,dict) or not d.get('url') or not d.get('dir'):
                raise TaskError('图片登记未返回有效路径')
            images = [{'url':d['url'],'dir':d['dir']}]
            log('✅ 已有图片登记成功')
        text = public_text()
        d = self.api('atReleaseInfo','POST',data={'releaseType':1,'text':text,'tab':'珍惜校园时光',
            'releaseInfoImgs':images,'schoolId':self.school,'luck':False,'luckDrawInfo':None,'anonymous':False})
        if not isinstance(d,dict) or type(d.get('status')) is not int or d['status'] != 1 or d.get('text') != text:
            raise TaskError('发帖未返回 status=1 与相同正文')
        return '发布文章成功，正文与业务状态已核对'

    def balance(self):
        d = self.api('points/self')
        if not number(d):
            raise TaskError('积分不是有效非负数')
        return d

    def reward(self):
        eligible = [t for name,t in self.tasks.items() if name not in ('新用户奖励','集赞有奖','发布任务','邀请有奖')]
        failures = 0
        for t in eligible:
            try:
                before = self.balance()
                d = self.api('integralTask/receiveReward','POST', data={'taskId':t['id']}, form=True)
                after = self.balance()
                if not explicit_success(d) and not (after - before >= t['value'] > 0):
                    raise TaskError('奖励缺少明确成功标记且积分未验证增加')
                log('✅ 普通任务奖励已验证，积分 %s → %s' % (before,after))
            except Exception:
                failures += 1
                log('❌ 普通任务奖励未能核验；不输出原始响应')
            time.sleep(random.uniform(2,4))
        if failures:
            raise TaskError('%d 项普通奖励失败或无法核验' % failures)
        return '已核验 %d 项普通任务奖励' % len(eligible)

    def delete(self):
        articles = self.articles(own=True)
        failures, count = 0, 0
        for a in articles:
            if str(a.get('user',{}).get('id')) != self.uid:
                continue
            count += 1
            try:
                self.api('atReleaseTaskRider/delete','DELETE',data={'id':a['id'],'text':a['text']})
                if any(str(p.get('id')) == str(a['id']) for p in self.articles(own=True)):
                    raise TaskError('删除后帖子仍在列表')
                log('✅ 删除后已重新查询，确认帖子不在本人列表')
            except Exception:
                failures += 1
                log('❌ 删除失败或未能核验')
            time.sleep(random.uniform(2,4))
        if failures:
            raise TaskError('%d 篇删除未确认' % failures)
        return '已核验删除 %d 篇本人帖子' % count

    def help_like(self):
        a = self.cfg['assist']
        d = self.api('atReleaseInfoLike','POST',data={'releaseId':a['topicId'],'user':{'id':self.uid},'text':a['text'],'toUser':a['userId']})
        if d is not True:
            raise TaskError('助力点赞未返回 true，未重复尝试')
        return '显式目标助力点赞成功'

    def invite(self):
        a = self.cfg['assist']
        d = self.api('atWebInviteRecord/createInvitation', query={'schoolId':a['schoolId'],'userId':a['userId']})
        if not explicit_success(d):
            raise TaskError('邀请绑定未返回明确成功，未知结果失败闭合')
        return '显式邀请绑定已验证成功'

    def run(self):
        start = time.monotonic()
        try:
            token, uid = self.line.split('#',1)
            if not token.strip() or not uid.isdecimal() or '@' in uid or '\r' in token:
                raise ValueError()
            self.uid = uid
            self.headers = {'Uid':uid,'Authorization':token,'Business':'at_xyq','Packagename':'wx8f5901dc7878cbb8',
                'User-Agent':'Mozilla/5.0 MicroMessenger/8.0.43',
                'Referer':'https://servicewechat.com/wx8f5901dc7878cbb8/374/page-frame.html'}
        except Exception:
            self.step('凭据校验', lambda: (_ for _ in ()).throw(TaskError('atxyqs 格式应为每行 Authorization#数字 Uid')), ready=False)
            # 配置错误在 dry-run 下也必须失败。
            return self.finish(start)
        self.step('凭据校验', lambda:'账号参数格式验证成功')
        ok = self.step('账号信息',self.user)
        school_ok = self.step('学校信息',self.schools, ready=ok)
        tasks_ok = self.step('任务列表',self.task_list, ready=ok and school_ok)
        self.step('签到',self.sign,ready=ok)
        self.step('文章点赞与取消点赞',self.like,enabled=self.cfg['like'],ready=ok and school_ok)
        self.step('发布动态',self.post,enabled=self.cfg['post'],ready=ok and school_ok)
        self.step('助力点赞',self.help_like,enabled=self.cfg['help_like'],ready=ok)
        self.step('邀请绑定',self.invite,enabled=self.cfg['invite'],ready=ok)
        self.step('领取普通任务奖励',self.reward,ready=ok and tasks_ok)
        self.step('清理本人最近帖子',self.delete,enabled=self.cfg['delete'],ready=ok)
        self.step('当前积分',lambda:'当前可用积分 %s 分' % self.balance(),ready=ok)
        return self.finish(start)

    def finish(self,start):
        s = dict(self.stats, account=self.idx, elapsedSeconds=round(time.monotonic()-start,2))
        log('账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒' %
            (self.idx,s['total'],s['success'],s['alreadyComplete'],s['skipped'],s['failed'],s['elapsedSeconds']))
        return s


def notify(body,dry):
    if os.getenv('QINGLONG_NOTIFY','1').strip().lower() in OFF:
        return '已禁用'
    if dry:
        return '预演模拟通知（断网）'
    # 使用独立进程隔离通知输出；任何异常不打印通知模块的错误正文。
    dirs = [Path(__file__).resolve().parent]
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        dirs.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    dirs.extend([Path('/ql/data/scripts'),Path('/ql/scripts')])
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            dirs.append(Path(spec.origin).parent)
    except Exception:
        pass
    pycode = "import importlib.util,sys; s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])"
    for directory in dirs:
        for filename in ('notify.py','sendNotify.js'):
            p = directory / filename
            if not p.is_file():
                continue
            try:
                if filename == 'notify.py':
                    cmd = [sys.executable,'-c',pycode,str(p),TITLE,body]
                else:
                    cmd = ['node','-e',"Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))",str(p),TITLE,body]
                r = subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=False)
                if r.returncode == 0:
                    return '已发送'
            except Exception:
                pass
    return '通知不可用或失败（保留业务退出码）'


def config():
    cfg = {k:flag(n) for k,n in [('like','ATXYQ_LIKE'),('post','ATXYQ_POST'),('help_like','ATXYQ_HELP_LIKE'),('invite','ATXYQ_INVITE')]}
    try:
        cfg['delete'] = int(os.getenv('atxyqDel','0')) != 0
    except ValueError:
        raise TaskError('atxyqDel 必须为整数') from None
    cfg['image_name'] = os.getenv('ATXYQ_IMAGE_NAME','').strip()
    cfg['image_dir'] = os.getenv('ATXYQ_IMAGE_DIR','').strip()
    if bool(cfg['image_name']) != bool(cfg['image_dir']):
        raise TaskError('图片文件名与目录必须配套填写')
    if cfg['post']:
        text = normalized(os.getenv('ATXYQ_LOCAL_TEXT',LOCAL))
        if not text or len(text)>280:
            raise TaskError('本地正文必须为 1 至 280 字')
    cfg['assist'] = None
    if cfg['help_like'] or cfg['invite']:
        try:
            a = json.loads(os.getenv('ATXYQ_ASSIST',''))
            if not isinstance(a,dict) or not all(a.get(k) for k in ('topicId','text','userId','schoolId')):
                raise ValueError()
            if not all(str(a[k]).isdecimal() for k in ('topicId','userId','schoolId')) or not isinstance(a['text'],str):
                raise ValueError()
            cfg['assist'] = a
        except Exception:
            raise TaskError('助力动作需要完整的 ATXYQ_ASSIST 目标配置') from None
    return cfg


def main():
    started = time.monotonic()
    start_time = datetime.datetime.now().isoformat(timespec='seconds')
    lines = [line.strip() for line in os.getenv('atxyqs','').splitlines() if line.strip()]
    dry = os.getenv('ATXYQ_DRY_RUN','0').strip().lower() not in OFF
    results, error = [], None
    log('========== %s ==========' % TITLE)
    log('开始时间：%s；模式：%s；账号数：%d' % (start_time,'断网预演' if dry else '正式运行',len(lines)))
    try:
        dry = flag('ATXYQ_DRY_RUN')
        cfg = config()
        if not lines:
            raise TaskError('未配置 atxyqs；请抓取本人 Authorization 与 Uid，每行一个账号')
        for i,line in enumerate(lines,1):
            results.append(Account(i,line,cfg,dry).run())
    except TaskError as exc:
        error = str(exc)
        log('❌ 配置错误：' + error)
    except Exception:
        error = '运行异常（详情已脱敏）'
        log('❌ ' + error)
    failed = sum(s['failed'] > 0 for s in results)
    passed = len(results)-failed
    status = ('configuration-error' if error else 'partial-failure' if failed and passed else
              'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if error or failed else 0
    body = '状态：%s；账号总数：%d；成功：%d；失败：%d；预演账号：%d' % (
        status,len(lines),0 if dry else passed,failed,len(results) if dry else 0)
    if error:
        body += '；配置错误：' + error
    notification = notify(body,dry)
    finish = datetime.datetime.now().isoformat(timespec='seconds')
    totals = {k:sum(s[k] for s in results) for k in ('total','success','alreadyComplete','skipped','failed')}
    log('----------------------------------------')
    log(body)
    log('子任务统计：总数 %d；成功 %d；已完成 %d；跳过 %d；失败 %d' % tuple(totals.values()))
    log('完成时间：%s；总耗时：%.2f 秒；通知：%s；最终状态：%s' % (finish,time.monotonic()-started,notification,status))
    print('TASK_SUMMARY=' + json.dumps({'task':TITLE,'mode':'dry-run' if dry else 'live','status':status,
        'accounts':len(lines),'successAccounts':0 if dry else passed,'failedAccounts':failed,'dryRunAccounts':len(results) if dry else 0,
        'configurationError':bool(error),'statistics':totals,'accountResults':results,'notification':notification,
        'startTime':start_time,'finishTime':finish,'elapsedSeconds':round(time.monotonic()-started,2),'exitCode':code},ensure_ascii=False,separators=(',',':')))
    return code

if __name__ == '__main__':
    sys.exit(main())
