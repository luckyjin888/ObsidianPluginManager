# Contributing / 贡献指南

感谢你愿意帮助改进 ObsidianPluginManager。

## 当前项目状态

当前版本 0.3.0 只实现 macOS 的只读环境检查。Windows、Linux、插件安装/卸载和自动化修改功能尚未实现。

## 贡献前请先阅读

- [README.md](README.md)
- [SECURITY.md](SECURITY.md)

## 不可违反的安全规则

所有涉及安装、卸载、启用、禁用、更新、修改、删除、备份恢复、系统设置、PATH、CLI 注册或管理员授权的功能和说明，必须同时提供：

1. **标准专业版**：具体动作、命令、路径、权限、影响、风险和恢复方式。
2. **10岁儿童比喻版**：用简单比喻解释同一动作、权限、影响和风险。

未经用户明确同意，不得执行有副作用的操作。拒绝或取消后必须停止。

## 提交建议

1. 一个 Pull Request 尽量只解决一个问题。
2. 说明修改原因、影响范围和测试方式。
3. 不提交个人 Vault 路径、个人笔记、令牌、密码或其他隐私数据。
4. 不声称未测试的平台已经支持。
5. 新增功能时同步更新 README、SECURITY 和 CHANGELOG（如适用）。
6. 对 Bash 脚本修改，至少运行语法检查：

```bash
bash -n obsidian_manager.sh
```

如本地安装了 ShellCheck，也建议运行：

```bash
shellcheck obsidian_manager.sh
```

## 许可证

提交贡献即表示你同意在 GNU GPL-3.0-only 许可下发布你的贡献，除非你与维护者另有书面约定。
