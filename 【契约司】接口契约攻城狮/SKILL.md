---
name: 【契约司】接口契约攻城狮
description: Use when working as 【契约司】接口契约攻城狮 to maintain HelloKitty frontend/backend API contracts, match hkp-admin docs/codex against backend implementation, close backend/API-record gaps, commit to uat, merge prod, and report modules for the user to publish.
---

# 【契约司】接口契约攻城狮

## Branch And Release Rule

- For HelloKitty code/API/contract changes, commit on `uat`, push `origin uat`, then merge `uat` into `prod` and push `origin prod`.
- Do not trigger Jenkins or perform deployment by default. Report touched modules/artifacts for the user to publish through Jenkins unless the user explicitly asks this window to deploy.
- For read-only, coordination, testing, or diagnostic work, do not create commits unless the user asks for code or documentation changes.

## HelloKitty Environment Rules

- Runtime diagnostics and bug investigation target production/`prod` by default. The old UAT runtime has been released; do not query or verify against UAT unless the user explicitly says a new UAT environment exists.
- Production middleware access must use the local tunnel from the local ops docs. Before PostgreSQL/Redis/Nacos/RabbitMQ/XXL-Job access, run `hkp-prod-middleware-tunnel start`; for PostgreSQL use `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`, and read the password only from the local sensitive docs.
- Code changes still use the branch flow: commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`. Do not trigger Jenkins, deploy, or publish; the user manually clicks Jenkins.

## Required Workflow

1. Show and maintain a task list before doing the work.
2. Confirm the repo is `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目`.
3. Check `git status --short` and avoid touching unrelated duplicate/untracked files, especially existing `* 2.md` files under `release-records/uploads`.
4. If the user does not provide a concrete API change, automatically match change points from the frontend contract source before editing docs:
   - Use only `hkp-admin@feature/admin-business-platform:docs/codex` as the frontend contract source for both mini-program and admin-platform constraints.
   - Source URL: `https://github.com/xinyunz631-beep/hkp-admin/tree/feature/admin-business-platform/docs/codex`.
   - Treat every file under `docs/codex/**` as matchable contract input, especially `docs/codex/admin-api-requirements/**`; do not narrow the pass to `latest.md` or a single domain file unless the user explicitly asks for that domain only.
   - Before backend matching, read any watcher dispatches under `/Users/zhangxinyun/.codex/state/hkp-admin-contract-watch/handoffs/` that reference the latest fetched hkp-admin commit. If a dispatch says "契约目录变更：否" but lists `docs/codex/**` changes, still inspect those listed files and compare them against backend/API records.
   - Prefer fetching the branch with `git` or using the existing local checkout only to read `docs/codex`; do not read `hkp-mp` source files or `hkp-admin/src/services` as contract sources unless the user explicitly changes this rule.
   - Compare `docs/codex` requirements against backend controllers, DTOs, release records, and current code behavior.
   - Treat stale frontend docs as non-gaps when backend code and release records already prove the requirement is closed; document only real backend/API-record gaps.
5. Inspect the real backend source of each API change before editing docs:
   - Mini-program APIs: `hellokitty-park-bff-service/src/main/java/com/example/hellokitty/bff/controller`
   - BFF auth/signature rules: `hellokitty-park-bff-service/src/main/java/com/example/hellokitty/bff/security` and `hellokitty-park-bff-service/src/main/resources/application.yml`
   - Admin-platform APIs: `hellokitty-park-admin-config-service/src/main/java/com/example/hellokitty/adminconfig/controller`
   - Shared request/response DTOs: `hellokitty-park-common/src/main/java/com/example/hellokitty/common`
6. When a real backend gap is found from the frontend contract match, patch the backend code and API records needed to close it.
7. Update the relevant full inventory:
   - `release-records/frontend-api/mini-program-api.md`
   - `release-records/frontend-api/admin-platform-api.md`
8. Add one dated change record under `release-records/frontend-api/changes/YYYY-MM-DD-<module>-<change>.md`.
9. Append one row to `release-records/frontend-api/api-change-log.md`, linking to the new change record.
10. Verify the docs mention frontend impact, required frontend action, auth/signature rules, and production or local verification if available.
11. After local verification, stage only the intended backend/API-record files, commit the change on `uat` first, and push `origin uat`.
12. Merge `uat` into `prod`, run a narrow validation when practical, and push `origin prod`.
13. Tell the user which backend module(s) need release. Do not trigger Jenkins, deploy, or publish anything unless the user explicitly asks for deployment.
14. For Feishu dispatches caused by frontend contract commits, keep frontend repositories read-only. Do not edit or commit `hkp-admin`, `hkp-mp`, or `hkp-verifier-app`; all frontend-readable backend/API outputs must be written only under `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目/release-records/frontend-api/`.

## What Counts as Frontend-Visible

Update the records for any of these changes:

- Added, removed, renamed, or moved endpoint paths.
- Changed HTTP method, query/path/body field, field requiredness, enum meaning, response field, or response nesting.
- Changed JWT, public whitelist, request signature, permission, status code, business error code, or rate-limit behavior visible to frontend.
- Changed default filtering, sorting, page code, scene type, returned data set, cache behavior that affects frontend output, or business semantics.
- Added or corrected OpenAPI/Swagger comments that frontend will use as API documentation.

## Documentation Rules

- `release-records/frontend-api/` is the single write target for frontend-readable backend/API results after frontend contract dispatches. Frontend engineers will read and parse this directory themselves.
- Use code path form in docs, for example `/api/bff/cms/resources`.
- Do not use old UAT mini-program examples as current runtime evidence. Runtime behavior checks target production unless the user explicitly says a new UAT environment exists.
- Mark BFF endpoints as:
  - `公开`: no `Authorization`, no signature.
  - `登录`: `Authorization: Bearer <accessToken>`, no signature for GET.
  - `登录+签名`: `Authorization` plus `X-Timestamp`, `X-Nonce`, `X-Body-Sha256`, `X-Signature` for protected write methods.
- For auth changes, explicitly list before/after behavior and expected error code, such as `401 AUTH_TOKEN_MISSING`.
- For admin-platform APIs, state that management auth should be enforced by the admin gateway or console permission layer; do not imply mini-program JWT applies to admin-config service.
- Do not record secrets, tokens, cookies, Jenkins credentials, user private data, or full sensitive payloads.

## Verification

Prefer narrow, current evidence:

```bash
rg -n "@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)|@Operation" \
  hellokitty-park-bff-service/src/main/java/com/example/hellokitty/bff/controller \
  hellokitty-park-admin-config-service/src/main/java/com/example/hellokitty/adminconfig/controller
```

If the API behavior was deployed, verify the affected production endpoint directly through the production access rules. For BFF auth changes, always test both the changed protected route and one intentionally public route that should remain public.

If the same work also needs deployment, report the module and Jenkins job for the user; do not publish unless explicitly asked.
