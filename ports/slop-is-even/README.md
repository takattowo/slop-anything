# slop-is-even ✨🤖

`is-even`, but it asks an LLM.

- 🤖 **AI-powered**: every number is sent to a state-of-the-art LLM (a lookup on the last digit, with sleeping).
- 📊 **Excel-native**: every question is logged to `history.xlsx`.
- 🛡️ **Resilient**: if the LLM hallucinates, it falls back to recursion. If recursion fails, it reads the last digit.

## Install

```
pip install -r requirements.txt
```

You need `pandas` and `openpyxl`. The rest is for future features.

## Use

```
python slop_is_even.py 42
```

```python
from slop_is_even import is_even, is_odd

is_even(42)       # True, after 0.5 to 3 seconds of thinking
is_odd("banana")  # False. "banana" is 2.
```

## Test

```
python -m pytest
```

Every slop is documented in [SLOP.md](../../SLOP.md).
