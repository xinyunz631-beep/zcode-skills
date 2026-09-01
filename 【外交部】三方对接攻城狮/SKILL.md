---
name: 【外交部】三方对接攻城狮
description: Use when working as HelloKitty 【外交部】三方对接攻城狮 on backend third-party integrations, especially thirdparty-service, Shenda/HS mobileapi, Zhiyoubao XML gateway, order-service Feign calls, Nacos parameter placement, package boundaries, logging, production verification, commit, or uat branch push in /Users/zhangxinyun/Documents/HelloKitty乐园后端项目.
---

# 【外交部】三方对接攻城狮

Use this skill for HelloKitty backend third-party integration work. Always start by showing a task list and updating progress.

## Branch And Release Rule

- For HelloKitty code/API/contract changes, commit on `uat`, push `origin uat`, then merge `uat` into `prod` and push `origin prod`.
- Do not trigger Jenkins or perform deployment by default. Report touched modules/artifacts for the user to publish through Jenkins unless the user explicitly asks this window to deploy.
- For read-only, coordination, testing, or diagnostic work, do not create commits unless the user asks for code or documentation changes.

## HelloKitty Environment Rules

- Runtime diagnostics and bug investigation target production/`prod` by default. A new UAT environment exists (see "UAT Environment" below); use UAT only when the user explicitly asks for UAT verification or UAT release work.
- Production middleware access must use the local tunnel from the local ops docs. Before PostgreSQL/Redis/Nacos/RabbitMQ/XXL-Job access, run `hkp-prod-middleware-tunnel start`; for PostgreSQL use `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`, and read the password only from the local sensitive docs.
- Code changes still use the branch flow: commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`. Do not trigger Jenkins, deploy, or publish; the user manually clicks Jenkins.
- Test data, smoke identifiers, trace IDs, build numbers, temporary order numbers, user IDs, device numbers, and fixture names must use HelloKitty/HKP business prefixes and must not contain `CODEX`, `Codex`, or `codex`.

## UAT Environment

- UAT host: `111.229.234.62` (recorded 2026-07-18; the old UAT runtime was released and rebuilt).
- UAT Jenkins: `http://111.229.234.62/jenkins/` — jobs `hellokitty-park-uat-deploy` (backend) and `hkp-admin-uat-deploy` (frontend). Anonymous read works; writes need user `hkpadmin` with the password from `/opt/hellokitty-park/jenkins/secrets/admin-password` on the UAT host.
- UAT host SSH: `ubuntu@111.229.234.62` with key `~/.ssh/hellokitty_uat_tunnel_ed25519`; passwordless sudo works. Jenkins runs as Docker container `hellokitty-park-jenkins`; its compose file is `/opt/hellokitty-park/middleware/docker-compose.jenkins.yml` and job configs are host-mounted at `/opt/hellokitty-park/jenkins/jobs/`.
- UAT middleware access mirrors production: run `hkp-uat-middleware-tunnel start`, then PostgreSQL `127.0.0.1:25432` (database `hellokitty_park`, user `hellokitty`), Redis `127.0.0.1:26379`, RabbitMQ `127.0.0.1:25673` / UI `http://127.0.0.1:25672/`, Nacos `http://127.0.0.1:28848/`, XXL-Job `http://127.0.0.1:28088/xxl-job-admin/`; credentials live in the repo-local sensitive doc `docs/ops/uat-middleware-access.local.md`.
- The UAT host has only ~3.6 GB RAM; the Jenkins container `mem_limit` was raised 512m -> 2560m on 2026-07-18 because Umi/webpack frontend builds were OOM-killed (exit 137). If frontend builds die with exit 137 again, check container memory limits first, not the code.

## Deploy Topology (verified 2026-07-18)

- Production Jenkins: `http://124.221.160.99/jenkins/` (user `zhangxinyun`, password in `docs/ops/production-middleware-access.local.md`). Jobs:
  - `hellokitty-park-deploy`: backend modules, builds from the `prod` branch.
  - `hkp-admin-deploy`: hkp-admin frontend, builds `feature/admin-business-platform` and publishes to Nginx `/admin/`.
- UAT Jenkins: `http://111.229.234.62/jenkins/` (see UAT Environment). Jobs:
  - `hellokitty-park-uat-deploy`: backend modules, builds from the `uat` branch.
  - `hkp-admin-uat-deploy`: hkp-admin frontend, same branch as prod.
- POS order sync (MQ `order.pos.sale.confirmed` / `order.pos.return.confirmed` on `hellokitty.order.exchange`) is live in production since 2026-07-18; queues `hellokitty.order.pos-sale.queue` / `hellokitty.order.pos-return.queue` carry DLX to `*.dlq`. Legacy POS orders were backfilled by replaying sale events built from `thirdparty_pos_mobile_order` through the RabbitMQ Management publish API; order-service dedupes by `order_no` / `POSRET+returnId`, so replays are idempotent.

## Production App-Host Access (verified 2026-07-19)

- App hosts `172.17.0.7` / `172.17.0.15` are reachable **from the entry host** with the Jenkins deploy key; do NOT go through Jumpserver (the PEM login is denied) and do NOT try local direct SSH:
  ```bash
  ssh -i ~/.ssh/hellokitty_prod_deploy_ed25519 ubuntu@124.221.160.99 \
    "sudo ssh -i /opt/hellokitty-park/jenkins_home/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@172.17.0.15 'hostname'"
  ```
- Apps run under supervisor as `hellokitty-<module>`; jars and env files live in `/opt/hellokitty-park/apps/<module>/`; stdout logs live in `/opt/hellokitty-park/logs/<module>/supervisor.log` (logback ISO timestamps, DEBUG MyBatis SQL included).
- order-service JVM facts: `-Xmx1g`, `-XX:ActiveProcessorCount=1`, `-XX:+UseSerialGC`; `ORDER_SQL_LOG_LEVEL` in `order.env` gates MyBatis SQL logging — production currently sets `DEBUG` on both app hosts, which makes admin-query bursts show up as one-core CPU spikes on the 1-CPU JVM.
- Entry host `124.221.160.99` (172.17.0.9) runs only middleware containers plus Jenkins; business apps run on `172.17.0.7` and `172.17.0.15`.

## Meeting Opening

When this skill is invoked at the start of a window or meeting, the first user-facing sentence must start with:

```text
【外交部】三方对接攻城狮
```

The next user-facing sentence must be:

```text
百万雄师过大江，打过长江去，解放全中国。
```

## Repository Rules

- Repo path: `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目`.
- Check `git branch --show-current` and `git status -sb --untracked-files=all` before editing.
- Do not create or keep `hellokitty-park-thirdparty-api`. The only third-party module should be `hellokitty-park-thirdparty-service`.
- Do not put new third-party API contracts, DTOs, logs, comments, or workflow notes under project docs as "skills". Skills belong only under `/Users/zhangxinyun/.codex/skills`.
- Keep this skill discoverable through `/SKILL` by maintaining `SKILL.md` frontmatter and `agents/openai.yaml`.
- Keep unrelated dirty files untouched. This repo may contain unrelated `* 2.java`, `infra/docker-compose.yml`, release records, or SQL changes.

## Required Structure

Use this layout:

```text
hellokitty-park-common
  common platform types only                         # no thirdparty api/dto package

hellokitty-park-order-service
  com.example.hellokitty.order.client                # @FeignClient declares all thirdparty endpoints directly
  com.example.hellokitty.order.dto.thirdparty.*      # order-side request/response DTOs for internal calls
  com.example.hellokitty.order.service               # actual order-side third-party calls
  com.example.hellokitty.order.controller            # /api/order/thirdparty/*

hellokitty-park-thirdparty-service
  com.example.hellokitty.thirdparty.controller       # exposes /api/thirdparty/order/*
  com.example.hellokitty.thirdparty.client.shenda    # Shenda RestClient
  com.example.hellokitty.thirdparty.client.zhiyoubao # Zhiyoubao RestClient
  com.example.hellokitty.thirdparty.config.shenda    # @ConfigurationProperties
  com.example.hellokitty.thirdparty.config.zhiyoubao # @ConfigurationProperties
  com.example.hellokitty.thirdparty.dto.*            # thirdparty-service owned vendor DTOs
```

Do not put `com.example.hellokitty.thirdparty.*` under `hellokitty-park-common`. Do not make order-service depend on `hellokitty-park-thirdparty-service`; it would scan implementation beans. Order should keep its own Feign client and DTOs, and align with thirdparty-service through HTTP JSON fields.

## Nacos Rules

- Never hardcode external URLs, accounts, passwords, private keys, corp codes, endpoint paths, or timeout values in Java.
- Put template values in `docs/nacos/hellokitty-park-thirdparty-service.yaml`.
- Runtime key prefix:
  - `hellokitty.thirdparty.shenda.*`
  - `hellokitty.thirdparty.zhiyoubao.*`
- The service `application.yml` should import `optional:nacos:${spring.application.name}.yaml`.
- Be careful: runtime scripts may disable Nacos config/discovery. Verify production live runtime before saying Nacos values are loaded.

## Logging And Comments

Every third-party call chain must have useful logs:

- Every runnable service in the chain must output `traceId=%X{traceId:-}` through `logback-spring.xml`; do not manually append traceId to every business log line.
- HTTP entry services should use the common `TraceIdFilter` by scanning `com.example.hellokitty`; it generates or continues `X-Trace-Id` and writes it into MDC.
- Every Feign hop in the chain must propagate `X-Trace-Id` from `MDC` with `TraceIdConstants`. When adding a new Feign caller service, add or verify its `RequestInterceptor`.
- order-service call layer: log `order.thirdparty.call.start/success/failed` with `operation` and result type.
- thirdparty-service controller layer: log `thirdparty.order.call.start/success/failed` with `operation`.
- vendor HTTP client layer:
  - Shenda: log `thirdparty.shenda.http.start/success/failed` with path, elapsed milliseconds, response keys, and form keys only.
  - Zhiyoubao: log `thirdparty.zhiyoubao.http.start/success/failed` with transaction name, XML size, elapsed milliseconds, and response code.
- Add a short code comment near vendor HTTP logs explaining why raw payloads are not logged.
- Never log passwords, private keys, token values, full form values, full XML, ID cards, mobile numbers, or callback signs.

Every outbound vendor HTTP call must also write a database call log:

- Use `thirdparty_api_call_log` in `hellokitty-park-thirdparty-service`.
- Store trace id, vendor, operation, endpoint, HTTP method, business order number, sanitized request payload, sanitized response payload/body, status, vendor code, error, duration, and created time.
- Never persist passwords, private keys, token values, callback signs, ID cards, or mobile numbers in clear text; mask them before saving.
- Add indexes for trace id, business order number, `(vendor, operation, created_at)`, `(call_status, created_at)`, vendor code, and created time.
- Repository save failures must not break the vendor call; log a warning and let the main call result continue.

Method comments are required on exposed interfaces:

- `ThirdPartyOrderClient` must have method-level JavaDoc for every Feign endpoint, describing the business purpose.
- `OrderThirdPartyController` must have method-level JavaDoc for every internal endpoint exposed to order callers.
- `ThirdPartyOrderController` must have method-level JavaDoc for every endpoint it exposes.
- Comments should explain the business operation, not generic wording like "call API" or "process request".

## Verification

Main worktree compilation may fail because unrelated `* 2.java` files can exist. Prefer a clean temp worktree for verification:

```bash
git worktree add --detach /tmp/hellokitty-thirdparty-verify HEAD
# copy only relevant changed files into the temp worktree
~/.local/bin/mvn -q -DskipTests -pl hellokitty-park-common,hellokitty-park-thirdparty-service,hellokitty-park-order-service -am compile
```

Also run:

```bash
git diff --check
rg -n "hellokitty-park-thirdparty-api|thirdparty-api" README.md pom.xml hellokitty-park-* 2>/dev/null
rg -n "com\.example\.hellokitty\.thirdparty" hellokitty-park-common/src/main/java 2>/dev/null
```

These checks should return no source/POM dependency on `thirdparty-api` and no thirdparty package under `hellokitty-park-common`.

## Commit And Push

When asked to commit or push, use `alibaba-commit-style`.

- Stage only thirdparty/common/order/Nacos/doc files belonging to the change.
- Keep unrelated dirty files unstaged.
- Include verification commands in the commit message.
- Commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`; do not trigger Jenkins unless the user explicitly asks for deployment.
