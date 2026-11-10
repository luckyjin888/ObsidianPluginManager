# Contributing / 贡献指南

感谢你帮助改进 ObsidianPluginManager。

## 开始之前

请先阅读 [README.md](README.md) 和 [SECURITY.md](SECURITY.md)。

## 强制安全规则

任何有副作用的功能都必须同时提供：
1. **标准专业版**：动作、命令、路径、权限、影响、风险、回滚和验证。
2. **10岁儿童比喻版**：用简单比喻解释同一个动作、权限、影响和风险。

必须先征求明确同意。拒绝或取消后立即停止。不得静默提权、覆盖未知文件或把未测试平台标为正式支持。

## 开发与测试

- Python 3.10+，核心代码尽量使用标准库。
- 不提交个人 Vault 路径、笔记、令牌、密码或其他隐私数据。
- 网络核验必须有超时和失败处理。
- 静态审查不得执行插件代码。
- 新增功能同步更新 README、SECURITY 和 CHANGELOG。
- 至少运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile obsidian_manager.py
bash -n obsidian_manager.sh
```

- Windows PowerShell 启动器及 macOS/Windows/Linux 路径逻辑需在真实对应系统验证后才能宣称正式支持。

## 许可证

提交贡献即表示你同意在 GNU GPL-3.0-only 许可下发布贡献，除非与维护者另有书面约定。
