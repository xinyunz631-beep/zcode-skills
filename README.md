# zcode-skills

个人 Agent Skills 库,存放于 `~/.zcode/skills/`,由 ZCode / Cursor 加载。

## 目录约定

每个技能一个目录,至少包含:

- `SKILL.md`:YAML frontmatter(`name` + `description`)+ 技能正文(角色、目录、架构、流程、坑清单、验证口径)
- `agents/openai.yaml`:展示名、一句话简介、默认 prompt

## 技能列表(节选)

| 技能 | 领域 |
| --- | --- |
| 【侍从室】总协调攻城狮 | HelloKitty 角色路由与跨角色协作 |
| 【军令部】后端开发攻城狮 | HelloKitty Java/Spring 后端 |
| 【兵站部】发布部署攻城狮 | Jenkins 发布与回滚 |
| 【密档司】生产访问攻城狮 | 生产中间件只读诊断 |
| 【账政司】数据库攻城狮 | SQL/MyBatis/Flyway |
| 【商铺好】房产任务平台攻城狮 | 商铺好 H5 演示 + UAT 独立 API |
| 【满记】POS接单攻城狮 | 外卖接单 MQ 中转站 |
| 【Chilis开发攻城狮】/【DQ开发攻城狮】/【鱼酷开发攻城狮】等 | 各品牌 EOS 后端 |

## 备注

- 仓库为私有备份,内部含 UAT 演示环境路径与演示账号,勿转公开。
- 提交信息遵循【阿里提交规范】:英文 type 前缀 + 中文摘要 + 背景/变更/影响/验证四段。
