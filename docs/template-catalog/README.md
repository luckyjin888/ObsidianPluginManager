# Obsidian 模板目录

本目录收录本项目原创的通用 Markdown 模板，并提供经过来源与许可初步核查的上游项目索引。

## 原则

1. 模板默认是纯 Markdown 与 YAML frontmatter，不执行脚本、不请求网络、不调用外部 API。
2. 不自动安装 Obsidian 插件，不自动创建 QuickAdd 选项或快捷键。
3. 不自动覆盖用户已有笔记；使用者应先检查模板变量是否符合自己的配置。
4. 上游项目仅作为研究参考。除非明确记录许可、版权声明和来源，否则不复制其模板正文、图片或配置。
5. 本仓库原创文件遵循仓库根目录的 GNU GPL-3.0-only 许可。

## 模板索引

| 分类 | 模板 | 用途 | 依赖 |
|---|---|---|---|
| Basic | [Daily Note](../../templates/basic/Daily%20Note.md) | 日常记录与回顾 | 无强制依赖 |
| Basic | [Meeting](../../templates/basic/Meeting.md) | 会议议题、决策和行动项 | 无强制依赖 |
| Research | [Literature Note](../../templates/research/Literature%20Note.md) | 文献阅读与研究证据 | 无强制依赖 |
| Trading | [Trade Review](../../templates/trading/Trade%20Review.md) | 交易计划执行与复盘 | 无强制依赖 |
| AI Agent | [Agent Task](../../templates/ai-agent/Agent%20Task.md) | Agent 任务边界、验收和反馈 | 无强制依赖 |
| AI Agent | [Knowledge Source](../../templates/ai-agent/Knowledge%20Source.md) | 来源登记、可信度与引用 | 无强制依赖 |

## 使用方法

将需要的 Markdown 文件复制到 Vault 的模板目录，再通过 Obsidian 核心 Templates 插件配置模板文件夹。模板中的日期占位符使用 Obsidian 核心 Templates 语法；若未启用核心插件，应手动替换占位符。

本目录不代表模板已安装到任何 Vault。项目管理器不会在本 PR 中自动写入用户 Vault。
