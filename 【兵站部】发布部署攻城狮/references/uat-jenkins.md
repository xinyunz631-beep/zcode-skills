# HelloKitty Legacy UAT Jenkins Reference

This file is historical only. The old UAT runtime has been released and must not be used as current runtime evidence or as the default deployment target.

Current rule: code changes are committed to branch `uat`, merged to `prod`, pushed, and then the user manually clicks Jenkins. Do not trigger Jenkins from Codex unless the user explicitly asks this window to publish.

## Project

```text
/Users/zhangxinyun/Documents/HelloKitty乐园后端项目
```

## Jenkins

```text
URL: <legacy UAT URL removed; do not use as current target>
Job: hellokitty-park-deploy
Default branch: uat
```

The Jenkins deployment record lives in:

```text
release-records/2026-05-28-jenkins-ci.md
release-records/uploads/2026-05-28-jenkins-ci/README.md
```

## Module Parameters

Known checkbox parameters:

```text
DEPLOY_MENU
DEPLOY_MEMBER
DEPLOY_ADMIN_CONFIG
DEPLOY_BFF
DEPLOY_ORDER
DEPLOY_PROMOTION
DEPLOY_PAY
DEPLOY_THIRDPARTY
DEPLOY_XXL_JOB
```

Confirm current parameters from Jenkins job metadata when credentials allow.

## UAT Verification

```text
<legacy UAT verification URLs removed; do not use as current runtime evidence>
```

BFF historical UAT notes are retained only for context; current runtime verification targets production.
