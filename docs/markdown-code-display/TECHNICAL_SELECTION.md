# Obsidian Manager：Markdown 代码展示技术选型规范

- 状态：研究草案（尚未进入产品实现）
- 研究分支：`docs/markdown-code-display-research`
- 适用范围：Obsidian Vault 阅读/编辑视图，以及 GitHub 仓库中的 Markdown（尤其 README）
- 项目许可证背景：Obsidian Manager 使用 GPL-3.0；第三方组件须逐项核验许可证与分发义务。

## 1. 目标

建立一套跨平台、渐进增强的 Markdown 代码展示方案，覆盖：

1. 语法高亮
2. 行号
3. 复制按钮
4. 代码块标题（文件名/用途）
5. 折叠代码
6. 终端风格展示
7. 重点代码行高亮

核心要求：同一份 Markdown 在 Obsidian 和 GitHub 上都能读懂；平台不支持的增强功能不得破坏代码内容或文档结构。

## 2. 设计原则

### 2.1 内容与展示分离

- Markdown 源文件保存真实代码、语言标识、标题说明和必要的折叠结构。
- Obsidian 专属插件只负责本地展示增强，不得成为文档正确阅读的前提。
- 不把某个 Obsidian 插件的私有代码围栏参数当作跨平台标准。
- 不为追求视觉效果而修改代码正文、插入行号字符或污染复制结果。

### 2.2 渐进增强

基础层使用通用 Markdown：
- 围栏代码块：```python、```bash、```json、```yaml、```text。
- 文件名和用途优先使用普通 Markdown 标题/说明文字。
- 终端命令与终端输出分开标注：命令用 `bash`，纯输出用 `text`。
- 折叠可评估 GitHub 支持的 HTML `<details>` / `<summary>`，但必须在目标 Obsidian 阅读视图、Live Preview 和移动端逐一验证。
- 重点行在基础层用正文说明标记；逐行着色作为 Obsidian 增强能力。

增强层可由 Obsidian 插件提供行号、复制按钮、标题栏、折叠控件、重点行和主题。

## 3. 功能矩阵与验收口径

| 功能 | Markdown 基础层 | Obsidian 增强层 | GitHub README |
|---|---|---|---|
| 语法高亮 | 语言标识 | 可增强主题/语言 | GitHub 支持其识别的语言标识 |
| 行号 | 不作强制要求 | 插件提供 | 普通围栏代码块不保证 |
| 复制按钮 | 不写入源文件 | 插件/平台 UI | GitHub 页面由平台 UI 决定 |
| 代码块标题 | 普通标题/说明 | 插件可显示标题栏 | 用 Markdown 标题/说明表达 |
| 折叠 | 可选 details/summary | 插件可提供交互 | 支持的 HTML details/summary 形式 |
| 终端风格 | bash + text 分块 | 插件主题/提示符样式 | 用语言标识和纯文本模拟 |
| 重点行 | 正文说明 | 插件逐行高亮 | 普通围栏代码块无通用逐行高亮语法 |

注意：GitHub 的渲染能力受 GitHub Flavored Markdown 与平台安全策略约束；不能假设自定义 HTML、CSS、JavaScript 或 Obsidian 插件参数会在 README 中生效。

## 4. 候选项目初筛

以下是候选清单，不构成安装或采用决定。项目活跃度、当前维护者、精确许可证、最低 Obsidian 版本、移动端支持、代码块 DOM 兼容性，均须在正式选型时以仓库当前状态和插件清单再次核对。

### 4.1 Codeblock Customizer

- 定位：Obsidian 代码块外观与交互增强。
- 初筛关注：标题栏、主题、行号/重点行、折叠、终端样式等功能覆盖。
- 风险/待核验：功能覆盖广也意味着与其他代码块装饰插件发生冲突的概率较高；核验许可证文件、最近发布、最低 Obsidian 版本、移动端、复制结果、Live Preview。
- 结论：作为“功能覆盖型”候选优先做隔离测试，不与其他同类插件同时启用。

### 4.2 Code Block Pro

- 定位：代码块标题、复制/下载、行号、长代码折叠等增强。
- 初筛关注：是否满足当前 Obsidian 版本；阅读视图与 Live Preview 的行为是否一致。
- 风险/待核验：项目成熟度、维护频率、移动端和主题兼容性；逐项核对当前 manifest 与许可证。
- 结论：作为“功能边界较清晰”的候选，与 Codeblock Customizer 二选一对比测试。

### 4.3 Code Block Numbers

- 定位：行号、文件名/起始行和重点行等较窄范围的增强。
- 优点：可作为轻量组件候选。
- 风险/待核验：需与复制按钮、折叠和标题类插件组合时检查 DOM 重复处理；核对复制内容是否剔除行号。
- 结论：仅在采用组合方案时测试，不与提供相同功能的插件重复启用。

### 4.4 Code Block Toolkit

- 定位：代码块编辑体验增强。
- 初筛关注：语言辅助、编辑器交互、行号/折叠等。
- 风险/待核验：它是否增强阅读视图，还是主要改善编辑过程；核对移动端、Live Preview 和维护状态。
- 结论：作为编辑体验补充候选，不预设其能满足完整展示需求。

### 4.5 Shiki

- 定位：基于 TextMate 语法的代码语法高亮引擎，不是可直接安装的 Obsidian 展示插件。
- 适用：未来独立文档渲染器、静态 HTML 生成或预览工具。
- 限制：不能让 GitHub README 自动采用自定义 Shiki 主题，也不能单独提供行号、复制按钮、折叠等完整交互。
- 许可证：初筛为 MIT；正式引入前必须复核仓库 LICENSE、依赖树和版本。

## 5. 许可证与依赖政策

Obsidian Manager 主项目采用 GPL-3.0。采用第三方代码前必须：

1. 检查目标版本仓库中的 LICENSE 文件，而非只看插件介绍页。
2. 记录版权声明、许可证文本、版本/commit、来源 URL。
3. 区分“用户独立安装第三方插件”与“将第三方源代码复制/打包进主项目”。
4. 若复制、修改或分发第三方代码，先做 GPL-3.0 兼容性和 NOTICE/版权义务审查。
5. 不因 MIT 通常具有较宽松许可，就省略许可证归档和依赖清单。
6. 未完成核验前，不将候选插件标记为“已批准”或“安全”。

## 6. 推荐架构

### 第一层：跨平台 Markdown 内容规范

所有项目文档优先使用标准围栏代码块、标准语言标识、普通标题和说明文字。HTML details 作为可选折叠增强，必须有清晰的非折叠阅读替代方式。

### 第二层：Obsidian 展示增强

通过可选社区插件增强行号、复制、标题栏、折叠、重点行和终端外观。插件未安装时，Markdown 内容仍应完整可读。

### 第三层：Obsidian Manager 管理能力

未来如纳入产品，建议仅提供：
- 候选插件发现与信息展示；
- manifest/最低版本/许可证核验；
- 功能重叠和潜在冲突提示；
- 安装前影响说明；
- 安装与启用分开授权；
- 不自动启用、不修改笔记正文。

不建议把完整 Markdown 渲染引擎塞入现有主程序。

## 7. 测试计划

建立独立测试 Vault 和测试 Markdown 文件，不使用日常 Vault 作为首次验证环境。

### 7.1 固定测试样本

- Python：函数、注释、字符串、多行代码。
- Bash：命令与输出分离。
- JSON/YAML：缩进、长行和特殊字符。
- 长代码块：至少 100 行，测试滚动/折叠。
- 重点行：测试高亮是否影响复制内容。
- 折叠块：测试 Obsidian 阅读视图、Live Preview、移动端和 GitHub。

### 7.2 验收项目

| 编号 | 检查项 | 通过标准 |
|---|---|---|
| T01 | Obsidian 阅读视图 | 代码高亮正确，无布局溢出 |
| T02 | Obsidian Live Preview | 编辑与预览切换稳定 |
| T03 | GitHub README | 代码内容与语言高亮正常 |
| T04 | 行号 | 不进入复制后的代码文本 |
| T05 | 复制 | 复制结果与原始代码逐字一致 |
| T06 | 标题 | 标题不混入代码内容 |
| T07 | 折叠 | 展开/收起不丢失代码 |
| T08 | 终端风格 | 命令与输出易于区分 |
| T09 | 重点行 | 高亮不改变代码语义 |
| T10 | 插件冲突 | 不重复注入按钮/行号，不破坏其他插件 |
| T11 | 移动端 | 无横向布局失控，按钮可触达 |
| T12 | 无插件降级 | 原始 Markdown 仍可阅读 |

## 8. 初步决策

当前建议：

1. 先用 Codeblock Customizer 与 Code Block Pro 做单插件隔离对比。
2. 若它们的维护、兼容或冲突表现不理想，再评估 Code Block Numbers 等轻量组合。
3. Shiki 暂时只列为未来独立渲染器的技术储备，不进入主程序。
4. GitHub 端坚持标准 Markdown，不依赖 Obsidian 专有语法。
5. 暂不安装、启用或打包任何第三方插件；不修改主程序和用户 Vault。

## 9. 资料核验清单

正式选型前逐一补齐以下证据，并记录核验日期：

- 项目 GitHub 仓库与官方 Obsidian 社区插件页面。
- 当前 LICENSE 文件及许可证版本。
- manifest.json 中的 id、version、minAppVersion。
- 最近提交、最近 Release、维护状态。
- README 明确列出的功能与已知限制。
- issue/PR 中关于复制、折叠、Live Preview、移动端和插件冲突的问题。
- 在 Obsidian 当前版本与 GitHub README 中的实测截图/结果。

---

**本文件是研究规范，不是安装说明或安全认证。** 所有候选仍需进一步核验与实测；未获得用户后续明确授权前，不安装、启用、卸载或修改任何第三方插件。


## 10. 已核验的开源来源与安装决策（核验日期：2026-11-16）

本节将“开源来源”和“本项目自研”明确区分。以下项目均为第三方开源项目；本项目目前只研究、比较和记录来源，不复制其源码，也不将其打包进 Obsidian Manager。

### 10.1 首选候选：Codeblock Customizer

- 项目：Codeblock Customizer（Obsidian 社区插件）
- 作者/维护者：mugiwara85
- 官方仓库：https://github.com/mugiwara85/CodeblockCustomizer
- Obsidian 社区插件页：https://community.obsidian.md/plugins/codeblock-customizer
- 插件 ID：`codeblock-customizer`
- 已核验 manifest 版本：`1.4.7`
- 最低 Obsidian 版本：`0.15.0`
- 桌面/移动端：manifest 的 `isDesktopOnly=false`
- LICENSE：MIT（已检查仓库根目录 LICENSE）
- 适配功能：主题/颜色、语法高亮增强、标题栏/文件名、行号、重点行/文本、折叠、终端提示符等。
- 安装方式：优先从 Obsidian → 设置 → 第三方插件 → 浏览，搜索 “Codeblock Customizer”，安装并启用。官方 README 也提供手动安装方式，但本项目不建议初次采用手动复制。
- 采用性质：直接安装第三方插件并配置；不是 Obsidian Manager 自己实现的代码块渲染器。
- 来源与版权要求：保留作者和官方仓库链接；若未来复制或分发其代码，必须保留 MIT 版权与许可声明，并重新审查依赖及 GPL-3.0 兼容性。

### 10.2 对照候选：Code Block Pro

- 项目：https://github.com/jalvarado-it/obsidian-code-block-pro
- Obsidian 社区插件页：https://community.obsidian.md/plugins/code-block-pro
- 插件 ID：`code-block-pro`
- 已核验 manifest 版本：`0.8.3`
- 最低 Obsidian 版本：`1.13.0`
- 桌面/移动端：manifest 的 `isDesktopOnly=false`
- LICENSE：MIT（已检查仓库根目录 LICENSE）
- 官方说明的功能：行号、复制/下载按钮、语言标签、代码块标题、长代码折叠。
- 决策：作为 Codeblock Customizer 的对照组；两者不要同时启用做正式使用，以免重复装饰代码块。先在测试 Vault 中分别测试。

### 10.3 专项候选：Shiki Highlighter

- 项目：https://github.com/mProjectsCode/obsidian-shiki-plugin
- Obsidian 社区插件页：https://community.obsidian.md/plugins/shiki-highlighter
- 插件 ID：`shiki-highlighter`
- 已核验 manifest 版本：`0.8.0`
- 最低 Obsidian 版本：`1.13.0`
- 桌面/移动端：manifest 的 `isDesktopOnly=false`
- LICENSE：MIT（已检查仓库根目录 LICENSE）
- 官方说明：集成 Shiki/Expressive Code，为 100+ 语言提供高亮，并支持标题、行号和行高亮等展示。
- 决策：作为语法高亮质量专项候选；不与 Codeblock Customizer 同时启用，除非隔离测试明确证明兼容且有必要。

### 10.4 底层引擎：Shiki

- 官方仓库：https://github.com/shikijs/shiki
- 定位：基于 TextMate grammar 的语法高亮引擎；不是可以直接在 Obsidian 插件市场中安装的完整展示插件。
- LICENSE：MIT（仓库标示 MIT）。
- 决策：当前不直接把 Shiki 引入 Obsidian Manager 主程序。若以后开发独立 Markdown/HTML 渲染器，再单独评估。

### 10.5 当前推荐决策

1. 首轮只测试 Codeblock Customizer；它覆盖本项目要求的大部分展示能力，且 manifest 明确支持桌面与移动端。
2. 用 Code Block Pro 做单独对照测试，比较复制准确性、标题、行号、折叠和兼容性。
3. 若主要问题是语法高亮质量，再单独测试 Shiki Highlighter。
4. 不同时启用多个会重绘/装饰代码块的插件；避免行号、按钮和标题重复。
5. 不把第三方插件代码复制到本项目，不自动安装或启用；由用户在 Obsidian 社区插件市场明确安装。
6. PR #8 先提交研究结论、来源和安装说明；只有测试通过后，才考虑把“推荐插件及配置”纳入项目文档。当前不应把第三方插件误标为本项目自研功能。

### 10.6 官方核验来源

- Codeblock Customizer 仓库与 README：https://github.com/mugiwara85/CodeblockCustomizer
- Codeblock Customizer LICENSE：https://github.com/mugiwara85/CodeblockCustomizer/blob/master/LICENSE
- Codeblock Customizer manifest：https://github.com/mugiwara85/CodeblockCustomizer/blob/master/manifest.json
- Code Block Pro 仓库：https://github.com/jalvarado-it/obsidian-code-block-pro
- Code Block Pro LICENSE：https://github.com/jalvarado-it/obsidian-code-block-pro/blob/master/LICENSE
- Code Block Pro manifest：https://github.com/jalvarado-it/obsidian-code-block-pro/blob/master/manifest.json
- Shiki Highlighter 仓库：https://github.com/mProjectsCode/obsidian-shiki-plugin
- Shiki Highlighter LICENSE：https://github.com/mProjectsCode/obsidian-shiki-plugin/blob/master/LICENSE
- Shiki Highlighter manifest：https://github.com/mProjectsCode/obsidian-shiki-plugin/blob/master/manifest.json
- Shiki 引擎：https://github.com/shikijs/shiki

核验说明：版本和最低 Obsidian 版本来自各项目当前仓库的 manifest.json；许可证来自各仓库 LICENSE 文件。版本会变化，正式安装前需重新检查最新 Release、manifest、LICENSE 和兼容性问题。


## 11. 最终推荐（维护者决策建议，2026-11-16）

**首选采用 Codeblock Customizer，暂不采用多插件拼装方案。**

推荐理由：
- 功能覆盖最完整：主题、标题栏、行号、重点行/文本高亮、折叠/半折叠、终端提示符、代码块分组、注释标注、换行控制等。
- 官方 Obsidian 社区页面显示约 74k 下载、32 次更新；项目已有较长维护和使用记录。
- MIT 许可证，适合以“用户独立安装第三方插件”的方式使用；不需要把第三方源码并入 GPL-3.0 主项目。
- 桌面和移动端均列为支持平台；但仍须在实际 Obsidian 版本、主题和 Live Preview 中实测。

为什么不把 Code Block Pro 作为首选：
- 它的优势是轻量、复制/下载行为明确、Reading View 与 Live Preview 支持清楚，适合只需要标题、行号、复制和折叠的用户。
- 但当前项目需求还包括终端展示、重点行多色高亮、主题和分组等更丰富的展示能力；Codeblock Customizer 覆盖面更合适。
- 可保留 Code Block Pro 作为备选，不建议与首选插件同时启用。

为什么暂不单独安装 Shiki Highlighter：
- 它主要解决语法高亮质量问题；当前首选插件已经覆盖更广的展示需求。
- 避免两个插件同时接管代码块 DOM，减少样式、按钮、行号和复制交互冲突。

实施原则：
1. 先在独立测试 Vault 安装并启用 Codeblock Customizer，不碰日常 Vault。
2. 先使用默认设置；逐项打开标题、复制/行号、折叠和高亮功能。
3. 测试 Reading View、Live Preview、移动端、复制结果、长代码块和 GitHub README 降级表现。
4. Markdown 源文件默认仍使用标准围栏和语言标识。Codeblock Customizer 的 `hl:`、`fold`、`prompt:` 等自定义围栏参数只在明确接受 Obsidian 专属语法的笔记中使用，不写入要求 GitHub 原生兼容的 README/通用文档。
5. 通过验收后，将其记录为“推荐第三方插件”，不是 Obsidian Manager 自研功能；不把插件源码打包进主程序。
6. 若测试发现明显兼容性、复制准确性或维护问题，再回退并评估 Code Block Pro。

本推荐是选型结论，不代表已经安装、启用或完成实测。正式安装前仍应从 Obsidian 社区插件市场确认最新版本、作者、插件 ID 和兼容性。
