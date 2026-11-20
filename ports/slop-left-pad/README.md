# slop-left-pad ✨📦

`left-pad`, but it unpublishes itself.

- 📦 **npm-native**: every call is checked against the npm registry (`registry.xlsx`).
- 🔥 **Authentic**: every 11th call, the package unpublishes itself. Call it again and it is back.
- 🐢 **Careful**: pads one character at a time, for stability.

## Install

```
pip install -r requirements.txt
```

You need `pandas` and `openpyxl`. The rest is for future features.

## Use

```
python slop_left_pad.py 5 3 0
```

```python
from slop_left_pad import left_pad

left_pad(5, 3, "0")      # '005'
left_pad(None, 11)       # '  undefined'
left_pad("x", 1000, "0") # 254 characters. The limit is 255.
```

## Test

```
python -m pytest
```

Every slop is documented in [SLOP.md](../../SLOP.md).
