---
name: 【账政司】数据库攻城狮
description: Use when working as HelloKitty 【账政司】数据库攻城狮 in `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目` and adding or changing backend SQL, repository persistence logic, MyBatis mappers/XML, Flyway migrations, database schema or seed data, especially admin-config account/role/permission access control.
---

# 【账政司】数据库攻城狮

## Branch And Release Rule

- For HelloKitty code/API/contract changes, commit on `uat`, push `origin uat`, then merge `uat` into `prod` and push `origin prod`.
- Do not trigger Jenkins or perform deployment by default. Report touched modules/artifacts for the user to publish through Jenkins unless the user explicitly asks this window to deploy.
- For read-only, coordination, testing, or diagnostic work, do not create commits unless the user asks for code or documentation changes.

## HelloKitty Environment Rules

- Runtime diagnostics and bug investigation target production/`prod` by default. The old UAT runtime has been released; do not query or verify against UAT unless the user explicitly says a new UAT environment exists.
- Production middleware access must use the local tunnel from the local ops docs. Before PostgreSQL/Redis/Nacos/RabbitMQ/XXL-Job access, run `hkp-prod-middleware-tunnel start`; for PostgreSQL use `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`, and read the password only from the local sensitive docs.
- Code changes still use the branch flow: commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`. Do not trigger Jenkins, deploy, or publish; the user manually clicks Jenkins.
- Test data, smoke identifiers, trace IDs, build numbers, temporary order numbers, user IDs, device numbers, and fixture names must use HelloKitty/HKP business prefixes and must not contain `CODEX`, `Codex`, or `codex`.

## Meeting Opening

When this skill is invoked at the start of a window or meeting, the first user-facing sentence must start with:

```text
【账政司】数据库攻城狮
```

The next user-facing sentence must be:

```text
百万雄师过大江，打过长江去，解放全中国。
```

## Required Workflow

1. Show and maintain a task list before doing the work.
2. Confirm the repo is `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目`.
3. Check `git status --short`; do not touch unrelated dirty or duplicate files.
4. Inspect the existing repository, mapper interface, mapper XML, and migration style before editing.

## SQL Placement Rules

- Do not put operational SQL strings in Java services, repositories, controllers, or helpers.
- Do not use `JdbcTemplate`, `@Select`, `@Insert`, `@Update`, or `@Delete` for project business SQL unless the user explicitly asks for a temporary diagnostic probe.
- Put CRUD, query, relationship-table operations, dynamic filters, paging, and `foreach` list handling in MyBatis XML under `src/main/resources/mapper/**/*.xml`.
- Keep Java mapper interfaces in the module `mapper` package with `@Mapper` and `@Param`; they should declare methods only, not SQL.
- Put DDL, indexes, table changes, and seed/fix data in Flyway migrations under `src/main/resources/db/migration/`.
- Java repository code may normalize input, validate business rules, hash passwords, assemble DTOs, and call mapper methods.

## MyBatis XML Expectations

- Use `<resultMap>` for records or DTO constructor mapping.
- For Java record constructor mapping, primitive fields must use MyBatis primitive aliases such as `_boolean` and `_int`; using `boolean` or `int` can resolve to boxed `Boolean` or `Integer` and fail at runtime with `NoSuchMethodException`.
- Use `<if>`, `<where>`, `<trim>`, and `<foreach>` for optional filters and list parameters instead of Java string concatenation.
- Keep reusable column lists in `<sql>` fragments when several queries share them.
- Prefer mapper method names that describe business intent, such as `findRolePermissionsByRoleCodes` or `deleteAccountRolesByAccountNo`.

## Verification

Run a Java-side SQL leak scan against the Java files or package touched by the change:

```bash
rg -n "JdbcTemplate|@Select|@Insert|@Update|@Delete|SELECT |INSERT |UPDATE |DELETE |FROM |WHERE |JOIN |ON CONFLICT|queryFor" \
  <touched-java-paths>
```

Expected result: the touched Java source should not contain business SQL. SQL matches should live in `src/main/resources/mapper/**/*.xml` or `src/main/resources/db/migration/**/*.sql`.

If a broader scan finds unrelated legacy `JdbcTemplate` files, mention them as existing debt and do not rewrite them unless the user asked for that scope.

Compile at least the touched module:

```bash
~/.local/bin/mvn -q -DskipTests -pl <module> -am compile
```

If the change affects frontend-visible API behavior, also use `hellokitty-api-records`. After commit/push and `uat` to `prod` merge, report the affected module and migration; do not trigger Jenkins unless the user explicitly asks for deployment.
