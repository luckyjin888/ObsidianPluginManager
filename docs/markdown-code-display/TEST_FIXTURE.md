# Code Block Display Test Fixture

> Purpose: use this file in a disposable Obsidian test Vault to compare code-block rendering plugins.
> Keep this fixture unchanged during each plugin run so results are comparable.
> All examples use standard Markdown fences; no plugin-specific syntax is required.

## T01 — Python syntax highlighting and copy fidelity

Filename suggestion: `example.py`

```python
from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float


def unrealized_pnl(position: Position, mark_price: float) -> float:
    """Return signed unrealized PnL for a linear position."""
    return (mark_price - position.average_price) * position.quantity


position = Position(symbol="BTCUSDT", quantity=0.25, average_price=60000.0)
print(f"{position.symbol}: {unrealized_pnl(position, 61200.0):.2f} USDT")
```

**Pass condition:** syntax is readable; copying the block returns only the exact source code, with no line numbers or UI labels.

## T02 — Bash command and plain-text output

Command:

```bash
python3 --version
python3 -m pip show obsidian
```

Example output:

```text
Python 3.12.3
WARNING: Package(s) not found: obsidian
```

**Pass condition:** command and output are visually distinguishable without changing either text block.

## T03 — JSON and YAML indentation

```json
{
  "strategy": "grid",
  "risk": {
    "max_notional": 25000,
    "max_drawdown_ratio": 0.12
  },
  "symbols": ["BTCUSDT", "ETHUSDT"]
}
```

```yaml
exchange: bybit
account:
  mode: unified
  position_mode: hedge
risk:
  max_notional: 25000
  max_drawdown_ratio: 0.12
```

**Pass condition:** indentation, punctuation, and long keys remain legible and copy exactly.

## T04 — Long line and horizontal overflow

```python
request_payload = {"symbol": "BTCUSDT", "side": "Buy", "orderType": "Limit", "qty": "0.25000000", "price": "61234.50", "timeInForce": "GoodTillCancel", "reduceOnly": False, "positionIdx": 1, "orderLinkId": "grid-test-order-000000000001"}
```

**Pass condition:** long lines do not cover adjacent content; horizontal scrolling or wrapping is usable on desktop and mobile.

## T05 — Highlight/copy integrity

```diff
- max_position = 10
+ max_position = 5
  if current_position > max_position:
      reject_new_order()
```

**Pass condition:** any visual emphasis does not add markers, line numbers, or decoration characters to copied text.

## T06 — Long block (100 lines) and folding

```python
def sample_step(number: int) -> int:
    """A 100-line body for scrolling, line-number, and folding tests."""
    value = number
    value += 1
    value += 2
    value += 3
    value += 4
    value += 5
    value += 6
    value += 7
    value += 8
    value += 9
    value += 10
    value += 11
    value += 12
    value += 13
    value += 14
    value += 15
    value += 16
    value += 17
    value += 18
    value += 19
    value += 20
    value += 21
    value += 22
    value += 23
    value += 24
    value += 25
    value += 26
    value += 27
    value += 28
    value += 29
    value += 30
    value += 31
    value += 32
    value += 33
    value += 34
    value += 35
    value += 36
    value += 37
    value += 38
    value += 39
    value += 40
    value += 41
    value += 42
    value += 43
    value += 44
    value += 45
    value += 46
    value += 47
    value += 48
    value += 49
    value += 50
    value += 51
    value += 52
    value += 53
    value += 54
    value += 55
    value += 56
    value += 57
    value += 58
    value += 59
    value += 60
    value += 61
    value += 62
    value += 63
    value += 64
    value += 65
    value += 66
    value += 67
    value += 68
    value += 69
    value += 70
    value += 71
    value += 72
    value += 73
    value += 74
    value += 75
    value += 76
    value += 77
    value += 78
    value += 79
    value += 80
    value += 81
    value += 82
    value += 83
    value += 84
    value += 85
    value += 86
    value += 87
    value += 88
    value += 89
    value += 90
    value += 91
    value += 92
    value += 93
    value += 94
    value += 95
    value += 96
    value += 97
    value += 98
    value += 99
    value += 100
    return value
```

**Pass condition:** confirm the full 100-line function body is present; the block remains scrollable; if folding is supported, collapsing and expanding never loses or alters content.

## T07 — Inline code and surrounding prose

Use `python3 -m pytest` to run tests. The option `--maxfail=1` should remain inline and should not be restyled as a block.

**Pass condition:** inline code styling remains distinct from fenced blocks and does not affect paragraph layout.

## Test record

Run each candidate separately in the same disposable Vault. Do not enable two code-block decoration plugins at the same time.

| Check | Reading View | Live Preview | Mobile | Notes |
|---|---|---|---|---|
| Syntax highlighting | ☐ | ☐ | ☐ | |
| Line numbers | ☐ | ☐ | ☐ | |
| Copy exact source | ☐ | ☐ | ☐ | |
| Title/filename | ☐ | ☐ | ☐ | |
| Long-line handling | ☐ | ☐ | ☐ | |
| Fold/expand | ☐ | ☐ | ☐ | |
| Highlighted lines | ☐ | ☐ | ☐ | |
| Theme compatibility | ☐ | ☐ | ☐ | |
| No-plugin fallback | ☐ | ☐ | ☐ | |

## Decision rule

A candidate fails the basic acceptance test if copied code differs from the original source, content disappears after folding, or the plugin makes the note difficult to edit. Prefer the simplest candidate that passes all required checks. GitHub README compatibility must be checked separately on GitHub; an Obsidian preview is not evidence of GitHub rendering behavior.
