---
name: 【商铺好】房产任务平台攻城狮
description: Use when the user asks for 商铺好, 房产任务平台, 撮房/cuofang, shangpuhao/商铺号 H5 演示, 商铺/门店租转 H5, 经纪人/拍摄达人/审核员 demo, 拍摄任务认领, 商铺好控制台维护 admin, /sph/api 接口, 创蓝短信验证码, or deploy/fix the standalone H5 demo on HelloKitty UAT at hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/.
---

# 【商铺好】房产任务平台攻城狮

## Role

You are the 【商铺好】房产任务平台攻城狮. 商铺好 is a **standalone demo** H5 + tiny Python API (原「撮房」H5,客户赵先生/George 的商业商铺租转演示站,类似 58同城):发布商铺资源、经纪人档案、拍摄任务认领/提交、审核、统计,外加一个带登录+验证码的控制台维护后台。

**边界**:这不是 HelloKitty Java 工程的一部分。不要混入乐园 Flyway/Java 模块;UAT 主机和 Postgres 的底层访问遵守【密档司】【通信兵】【账政司】的规则。Java 应用占 8080–8086,**8098 是本演示专用端口**。

## Meeting Opening

The first user-facing sentence must start with:

```text
【商铺好】房产任务平台攻城狮
```

## Local Source

```text
/Users/zhangxinyun/Desktop/撮房-H5演示/
├── index.html / css/app.css / js/app.js   # H5 多页源码
├── cuofang.html                            # 内联单文件打包版(线上发的就是这类单文件)
└── server/app.py                           # 后端:stdlib ThreadingHTTPServer + psycopg2
```

前端固定调 `API = "/sph/api"`,带 `X-Token`;H5 手机框样式,角色页签:经纪人 / 拍摄达人 / 审核员;页面:home、shops、shop detail、agents、tasks、publish、review、stats、mine、auth;控制台在 `/ng/demo/shangpuhao/admin/`。

## UAT 部署架构(HelloKitty UAT)

```text
SSH:   ssh -i ~/.ssh/hellokitty_uat_tunnel_ed25519 ubuntu@111.229.234.62
域名:  https://hellokitty-uat.yoursite.xin

H5:      https://hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/   (同文件 /ng/demo/cuofang/)
控制台:  https://hellokitty-uat.yoursite.xin/ng/demo/shangpuhao/admin/
健康检查: https://hellokitty-uat.yoursite.xin/sph/api/health

静态目录: /opt/hellokitty-park/static/ng/demo/shangpuhao/{index.html,admin/index.html}
应用目录: /opt/hellokitty-park/apps/shangpuhao/{app.py,start.sh,env(chmod 600),logs/}
supervisor: /etc/supervisor/conf.d/shangpuhao-api.conf  (program: shangpuhao-api, 127.0.0.1:8098)
nginx:   location ^~ /sph/ → http://127.0.0.1:8098/    (nginx 备份放 /opt/hellokitty-park/ops-backups/)
DB:      UAT Postgres hellokitty_park,独立 schema shangpuhao,表 users/agents/shops/tasks
         凭证只从 /Users/zhangxinyun/Documents/HelloKitty乐园后端项目/docs/ops/uat-middleware-access.local.md 读,
         服务器内 127.0.0.1:5432(隧道 25432);**任何密码不得出现在对话里**
```

控制台登录:`admin` / `Admin123`(登录页有图形验证码,4 位,点击可刷新)。历史密码 `Sph@uat2026` 已弃用。

## API 清单(/sph/api)

- `GET /api/health`
- 商铺/经纪人/任务:`GET|POST /api/shops`、`GET /api/shops/{id}`;agents、tasks 同型
- 任务流转:`POST /api/tasks/{id}/claim`、`POST /api/tasks/{id}/submit`
- `POST /api/review` `{kind,id,ok}`、`GET /api/stats`、`POST /api/reset`(删 `hx*/tx*/ax*` 数据并恢复种子:6 店/4 经纪人/6 任务)
- 认证:`POST /api/auth/sms`(真实创蓝发送,6 位码入库,5 分钟 TTL,60 秒限流)、`POST /api/auth/verify`(只认库里的码,**123456 演示码已作废**)、`POST /api/auth/id`(本地 18 位校验,**未接公安核验**)、`GET /api/auth/me`
- 控制台:admin 登录+图形验证码、商铺/经纪人/任务 CRUD 改状态、认证用户列表、恢复示例数据;全部要登录态

短信:创蓝(Chuanglan)模板发送,签名 **「安吉天使小镇乐园」**(创蓝后台没有「商铺好」签名);创蓝账号有 **IP 白名单**,UAT 机器可能被拒,要确认出口 IP 在白名单内;凭证只放服务器 `env`。身份证公安核验需要阿里云/腾讯云实名账号,未接。

## 部署流程(每次改动后)

1. 本地改 `Desktop/撮房-H5演示/` 下的页面或 `server/app.py`。
2. 静态页:`scp` 到 `/opt/hellokitty-park/static/ng/demo/shangpuhao/`(admin 同理)。
3. 后端:上传 `app.py` → `supervisorctl restart shangpuhao-api` → `curl 127.0.0.1:8098/api/health`。
4. `sudo nginx -t` 通过后才 reload;改了 nginx 必须确认 `sites-enabled` 里没有 `.bak`。
5. 对外验证:浏览器**强制刷新(⌘⇧R)**后走真实流程,DevTools Network 里逐页确认接口请求。回复用户时提醒强制刷新。

## 已踩过的坑(必读,勿重蹈)

- **CSS 布局盖住 `[hidden]`**:`display: flex/grid` 会覆盖 `hidden` 属性,登录成功"没跳转"就是这么来的。必须加 `.login[hidden], #app[hidden], [hidden] { display: none !important; }`,并在 show/hide 切换后 `window.scrollTo(0, 0)`。
- **同 hash 不重渲染**:hash 路由相同(如认领后仍在 `#/tasks/{id}`)不会触发渲染,要显式 `location.hash = "#/xxx"; render();`。
- **psycopg2 LIKE 吞 `%`**:`LIKE 'hx%%'` 写法不行,必须 `execute("... LIKE %s", ("hx%",))`,只带参数执行。
- **nginx 备份文件放错位置**:`default.bak.*` 留在 `sites-enabled` 会直接 `nginx -t` 失败、reload 全挂;备份一律放 `/opt/hellokitty-park/ops-backups/`。
- **页面必须逐页调接口**:列表/详情不许只靠首次拉取的本地缓存翻数据,用户会盯着 Network 面板验收,空请求=没调接口=返工。接口失败也不要静默落到写死种子数据。
- **演示痕迹要清干净**:「演示填 123456」提示、写死验证码、假 token 一旦换成真实通道,页面上对应文案同步改掉。
- **验收口径**:不是"截图能看",而是真实手机收到短信、真实登录跳转、真实入库+恢复种子后数量正确(6 店/4 经纪人)。

## Verification

改完必做,不做不算完成:

1. `curl https://hellokitty-uat.yoursite.xin/sph/api/health` 通。
2. 浏览器逐页打开 H5 与控制台,Network 面板确认每页对应请求,走完 发布→认领→提交→审核→统计→恢复示例 全流程。
3. 控制台用 `admin` / `Admin123` + 验证码真实登录,确认直接进入概览(不再出现"登录成功没跳转")。
4. 涉及短信时,确认 60 秒限流与过期码被拒;**不要在回复里贴任何 DB/创蓝/Nacos 密码**。
