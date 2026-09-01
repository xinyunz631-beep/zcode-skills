---
name: 【密档司】生产访问攻城狮
description: Use when working as 【密档司】生产访问攻城狮 for HelloKitty production middleware access orientation, credential-source discovery, or safe read-only diagnostics for production PostgreSQL/database, Redis, RabbitMQ/MQ, Nacos, XXL-Job, Jenkins, WireGuard, SSH tunnels, Docker containers, or production backup paths.
---

# 【密档司】生产访问攻城狮

## Branch And Release Rule

- For HelloKitty code/API/contract changes, commit on `uat`, push `origin uat`, then merge `uat` into `prod` and push `origin prod`.
- Do not trigger Jenkins or perform deployment by default. Report touched modules/artifacts for the user to publish through Jenkins unless the user explicitly asks this window to deploy.
- For read-only, coordination, testing, or diagnostic work, do not create commits unless the user asks for code or documentation changes.

## HelloKitty Environment Rules

- Runtime diagnostics and bug investigation target production/`prod` by default. The old UAT runtime has been released; do not query or verify against UAT unless the user explicitly says a new UAT environment exists.
- Production middleware access must use the local tunnel from the local ops docs. Before PostgreSQL/Redis/Nacos/RabbitMQ/XXL-Job access, run `hkp-prod-middleware-tunnel start`; for PostgreSQL use `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`, and read the password only from the local sensitive docs.
- Code changes still use the branch flow: commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`. Do not trigger Jenkins, deploy, or publish; the user manually clicks Jenkins.
- Test data, smoke identifiers, trace IDs, build numbers, temporary order numbers, user IDs, device numbers, and fixture names must use HelloKitty/HKP business prefixes and must not contain `CODEX`, `Codex`, or `codex`.

## Purpose

Use this as the first production-access map for HelloKitty. It tells agents where the local sensitive access docs live, how to avoid leaking secrets, and how to gather safe read-only proof before involving backend, release, SQL, QA, or platform-ops roles.

This skill complements `hellokitty-platform-ops-engineer`; use platform-ops for infrastructure changes. Use this skill for orientation and safe access discovery.

## Ground Rules

1. Start every task with a visible task list and update progress while working.
2. Confirm the scope is production/`prod`, the target component, and whether the user asked for read-only diagnostics or a state-changing operation.
3. Default to read-only diagnostics. Do not run writes, deletes, restarts, queue purges, Redis `FLUSH*`, SQL DDL/DML, Nacos publish/delete, XXL-Job trigger/stop, Jenkins build, or service/container changes unless the user explicitly asks for that concrete action.
4. Never paste credentials, private keys, tokens, cookies, or full local sensitive docs into chat, commits, release records, PRs, screenshots, or skill files.
5. When a secret is needed, read it from the local sensitive source and use it only in the command or tool that requires it. Redact it in all updates and final answers.
6. Before any approved production mutation, capture a backup or reversible evidence appropriate to the component, then report the exact backup path or rollback handle.

## Default Local Tunnel Access

- Before any production middleware access, run `hkp-prod-middleware-tunnel start`. If it says the tunnel is already running, continue.
- Prefer local-only tunnel endpoints over direct VPN, direct `172.17.*`, SSH container, or Jumpserver routes.
- PostgreSQL/Navicat production connection: host `127.0.0.1`, port `15432`, database `hellokitty_park`, username `hellokitty`, password from `docs/ops/production-middleware-access.local.md`.
- Other local tunnel endpoints currently printed by `hkp-prod-middleware-tunnel start` include Redis `127.0.0.1:16379`, Nacos Console `http://127.0.0.1:18848/`, Nacos API `127.0.0.1:18884`, RabbitMQ UI `http://127.0.0.1:15672/`, RabbitMQ AMQP `127.0.0.1:15673`, XXL-Job MySQL `127.0.0.1:13306`, and XXL-Job Admin `http://127.0.0.1:18088/xxl-job-admin/`.

## Local Sources

Primary repo:

```text
/Users/zhangxinyun/Documents/HelloKitty乐园后端项目
```

Sensitive local files:

```text
docs/ops/production-middleware-access.local.md
docs/ops/production-wireguard-client.local.conf
```

Jumpserver SSH key locator:

```text
/Users/zhangxinyun/Downloads/download/HelloKitty.jumpserver.pem
```

- Fingerprint check: `ssh-keygen -lf /Users/zhangxinyun/Downloads/download/HelloKitty.jumpserver.pem -E md5` should show `MD5:ca:7f:bf:2d:b8:6f:ff:87:4f:a3:70:e6:e4:0d:ec:fa`.
- Jumpserver SSH endpoint is listed in the local sensitive account sheet at `/Users/zhangxinyun/Downloads/清单/jumpserver跳板机账号.txt`; read it only as needed and never paste account passwords or unlabeled credential lines.
- The known endpoint from that sheet is `jump.wiselong.cc:2222`. The host currently offers legacy `ssh-rsa`, so read-only SSH probes may need:
  `-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa`.
- Do not assume the PEM directly logs in as `zhangxinyun@jump.wiselong.cc`; if public-key auth is denied, use the Jumpserver asset routing or account sheet workflow instead of guessing users or passwords.
- After reaching a production host, `sudo su` is supported without a password and may be used when root-level read-only inspection is needed. This does not relax the default no-mutation rule.

Observed HelloKitty production SSH topology and traps:

- Fast path for the public/entry host: use `/Users/zhangxinyun/.ssh/hellokitty_prod_deploy_ed25519` to SSH as `ubuntu@124.221.160.99`. This reaches host `VM-0-9-ubuntu`, which has internal IP `172.17.0.9`.
- The deploy key fingerprint is `MD5:47:82:6a:c1:5c:46:b6:4e:71:f7:93:a9:c1:6d:2a:5e` (`codex-hellokitty-prod-20260623`). Do not paste the private key.
- Once on `ubuntu@124.221.160.99`, `sudo su` is passwordless. For non-interactive diagnostics, prefer `sudo su -c 'bash -s'` with a read-only script over opening an interactive root shell.
- Direct SSH from the local machine to app hosts `172.17.0.7` and `172.17.0.15` can show port 22 as reachable, but OpenSSH may fail during key exchange with `kex_exchange_identification: read: Connection reset by peer`. Do not waste time repeatedly trying local direct SSH for those app hosts.
- From the entry host, TCP/22 to `172.17.0.7` and `172.17.0.15` is reachable, but the entry host does not currently have a known passwordless SSH key for common users such as `root`, `ubuntu`, `zhangxinyun`, `deploy`, or `jenkins`.
- If app-host SSH is needed, use the Jumpserver asset route or the local sensitive account workflow. Do not guess passwords or dump the account sheet into chat.
- For shared storage checks where app-host SSH is unavailable, collect server-side NFS proof from `172.17.0.9`: `exportfs -v`, `showmount -e 127.0.0.1`, and `ss -tnp` for established `172.17.0.9:2049` connections to `172.17.0.7` and `172.17.0.15`. Treat this as strong service-side evidence, but note when client-side `findmnt` on each app host was not directly checked.

Use the redacted inventory script first:

```bash
/Users/zhangxinyun/.codex/skills/hellokitty-production-access/scripts/print_inventory.sh
```

If the files moved, search only the repo's ops docs:

```bash
rg --files /Users/zhangxinyun/Documents/HelloKitty乐园后端项目/docs/ops | rg 'production|middleware|wireguard|ops'
```

## Access Workflow

1. Run the redacted inventory script and identify which component is involved: PostgreSQL, Redis, RabbitMQ/MQ, Nacos, XXL-Job, Jenkins, VPN, or backup path.
2. Read the sensitive local doc only as needed. Prefer targeted searches for headings and the specific component instead of dumping the whole file.
3. Decide the access path:
   - Default path: run `hkp-prod-middleware-tunnel start`, then use the local tunnel endpoint.
   - PostgreSQL default: `127.0.0.1:15432` with database `hellokitty_park` and user `hellokitty`.
   - Server-local, Docker container, Jumpserver, or direct `172.17.*` routes are fallback paths only when the local tunnel is unavailable or the user explicitly asks for that path.
4. Verify with the smallest read-only signal that proves reachability.
5. If behavior depends on runtime config, inspect live runtime files or containers. Do not assume source-code defaults or Nacos entries are what production is currently using.
6. Summarize with component, access path used, read-only evidence, and any missing prerequisite. Keep secrets redacted.

## Read-Only Verification Signals

Use exact credentials and ports from the sensitive local docs, but do not print those values.

- PostgreSQL/database: use the local tunnel first (`127.0.0.1:15432`) and confirm connection with a harmless query such as `select current_database(), current_user, now();`.
- Redis: `PING`, `INFO server`, and `INFO replication` when role/write-state matters. Avoid key scans unless the user asks for a scoped investigation.
- RabbitMQ/MQ: Management UI/API reachability, overview, aliveness test, vhost list, and queue metadata. Do not purge, publish, or delete.
- Nacos: console/API reachability, namespace/group/dataId lookup, and config read. For this environment, remember Nacos v3 APIs commonly use `groupName`, not `group`.
- XXL-Job Admin: login/page reachability and job metadata only. Do not trigger, stop, or edit jobs without explicit approval.
- Jenkins: reachability and job metadata only. Application releases belong to release-engineer/deploy workflow unless the user explicitly asks to publish.
- Backups: list backup paths and timestamps only unless the user asks to restore, copy, or delete.

## Handoffs

When another specialist should act, hand off with this compact format:

```text
需要交给 <target-skill>：
- 环境/组件：生产 / <component>
- 访问资料：docs/ops/production-middleware-access.local.md（本地敏感，不外贴）
- 已验证：<read-only evidence>
- 风险/限制：<what was not changed or what still needs approval>
- 需要处理：<specific next action>
```

Use these defaults:

- Code/business logic: `hellokitty-backend-engineer`
- SQL authoring/schema review: `hellokitty-backend-sql-style`
- Production release execution: `hellokitty-release-engineer`
- Infrastructure mutation, VPN, Docker, nginx, Redis/Nacos/RabbitMQ/XXL-Job service changes: `hellokitty-platform-ops-engineer`
- Regression/acceptance proof: `hellokitty-test-engineer`
