---
name: 【阿里提交规范】
description: Apply an Alibaba-style enterprise Git commit message convention. Use when Codex is asked to create a git commit, push code after committing, write or rewrite a commit message, summarize staged code changes for commit, or decide a commit format for local repository changes.
---

# Alibaba Commit Style

Use this skill for every code commit unless the user explicitly requests another format.

## Commit Workflow

1. Inspect `git status -sb` and the relevant diff before committing.
2. Stage only files that belong to the requested change. Leave unrelated dirty files untouched.
3. Generate a structured Chinese commit message with an English type prefix.
4. Keep the subject specific to the business or technical change.
5. Include verification results. If verification was not run, state the reason.

## Message Format

Use this exact structure:

```text
<type>(<module>): <short Chinese summary>

背景:
- <why this change is needed>

变更:
- <main code/config change>
- <important behavior change>

影响:
- <affected module/interface/runtime behavior>

验证:
- <command or manual check result>
```

## Type Rules

Use one of these lowercase types:

- `feat`: new feature or new business capability
- `fix`: bug fix or production/UAT defect fix
- `refactor`: code restructuring with no intended behavior change
- `perf`: performance optimization
- `test`: test-only change
- `docs`: documentation-only change
- `build`: build, dependency, packaging, or CI change
- `chore`: maintenance change that does not fit another type
- `style`: formatting-only change
- `revert`: revert a previous commit

## Module Rules

Choose the narrowest meaningful module name:

- Maven module or service: `mwos`, `couponPromotion`, `order`, `member`, `control`, `menu`
- Frontend area: `admin`, `web`, `store-menu`
- Config/runtime scope: `uat`, `nacos`, `redis`, `jenkins`

If multiple modules are changed, use the main affected module or `multi`.

## Writing Rules

- Write the subject in Chinese, no trailing punctuation.
- Keep the subject under about 30 Chinese characters when possible.
- Prefer concrete verbs: `修复`, `新增`, `调整`, `移除`, `优化`, `补充`.
- Avoid vague subjects like `fix bug`, `update code`, `修改问题`.
- Do not mention Codex or AI in commit messages.
- Do not include unrelated local changes in the commit.
- For one-line hotfix commits, still include the body unless the user explicitly asks for a short commit.

## Examples

```text
fix(couponPromotion): 同金额优先执行本地促销

背景:
- 保存订单时本地促销和 CRM 券优惠金额一致，自动试算可能优先使用券

变更:
- 调整单品优惠试算排序，同金额时本地活动优先
- 保留手动选择优惠的最高优先级

影响:
- 仅影响单品优惠自动执行顺序，不改变 save 接口入参和响应结构

验证:
- mvn -q -pl couponPromotion -Dtest=PromotionContextTest test
```

```text
fix(control): 避免启动时创建 OBS Bean

背景:
- PE 环境未使用 OBS 上传，但 Spring 启动仍会初始化 OBS 工具类

变更:
- 移除 OBSClientUtils 的组件注册
- 保留业务代码中按需手动创建工具类的方式

影响:
- 降低 control 启动时对 OBS SDK 的强依赖

验证:
- git diff --check
```
