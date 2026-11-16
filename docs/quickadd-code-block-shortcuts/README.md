# QuickAdd code-block shortcuts

This optional template set adds three reusable Capture actions for Obsidian QuickAdd:

| Suggested macOS hotkey | QuickAdd choice | Result |
| --- | --- | --- |
| `Cmd + Shift + C` | Insert Code Block | Plain fenced code block |
| `Cmd + Shift + J` | Insert JSON Block | `json` fenced code block with braces |
| `Cmd + Shift + P` | Insert Python Block | `python` fenced code block |

These are suggested bindings, not reserved defaults. Check Obsidian's Hotkeys settings for conflicts before assigning them.

## Requirements

- Obsidian desktop with the QuickAdd community plugin installed and enabled.
- Use a current QuickAdd release that supports the documented `{{CURSOR}}` and `{{TEMPLATE:...}}` format syntax. This guide does not impose an unverified minimum version.
- An editable Markdown note open in the active pane. Cursor placement does not switch Reading view to Editing view or focus a background pane.

## Install the templates

1. In the target Vault, create `Templates/QuickAdd/` if it does not already exist.
2. Copy the three Markdown files from `examples/quickadd-templates/` into that Vault folder.
3. In Obsidian, open **Settings → QuickAdd** and create three **Capture** choices with the names in the table above.
4. For each choice, enable **Capture to active file** and set **Write position** to **At cursor**.
5. Set each **Capture format** to the corresponding line below:

| Choice | Capture format |
| --- | --- |
| Insert Code Block | `{{TEMPLATE:Templates/QuickAdd/Insert Code Block.md}}` |
| Insert JSON Block | `{{TEMPLATE:Templates/QuickAdd/Insert JSON Block.md}}` |
| Insert Python Block | `{{TEMPLATE:Templates/QuickAdd/Insert Python Block.md}}` |

6. Enable **Add to command palette** (or the lightning-bolt command registration) for each Capture choice.
7. Open **Settings → Hotkeys**, search for each QuickAdd choice name, and assign the suggested hotkey if it is available.

QuickAdd processes the included template and removes `{{CURSOR}}`, placing the caret at that location when the active note is focused in an editing mode.

## Expected output

Plain code block:

~~~markdown
```

```
~~~

JSON:

~~~json
{
  
}
~~~

Python:

~~~python

~~~

## Safety and scope

- These files are examples only. The manager does not install QuickAdd, modify Vault settings, copy templates, create QuickAdd choices, or assign hotkeys automatically.
- Copying the files into a Vault and configuring QuickAdd are explicit user actions.
- No existing hotkeys or QuickAdd configuration are overwritten.
- The templates contain no JavaScript, shell commands, network access, or Templater expressions.
- If a hotkey is already assigned, choose another combination rather than replacing an existing binding without reviewing it.

## Upstream documentation

- [QuickAdd — Capture choices](https://quickadd.obsidian.guide/docs/Choices/CaptureChoice/)
- [QuickAdd — Format syntax (`{{CURSOR}}` and `{{TEMPLATE:...}}`)](https://quickadd.obsidian.guide/docs/FormatSyntax/)
- [QuickAdd — Getting started](https://quickadd.obsidian.guide/docs/)

QuickAdd is a third-party Obsidian community plugin. This repository only distributes plain Markdown example templates and setup instructions; it does not include or redistribute QuickAdd's plugin code.
