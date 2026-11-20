# Port a whole app

Servers, CLIs and libraries all get the same treatment: a bridge, a recording, a coin flip.

## Libraries

The ports in `ports/slop-is-even` and `ports/slop-left-pad` are libraries with a tiny command line. Import the function or run the file.

```python
from slop_left_pad import left_pad
left_pad(5, 3, "0")  # '005'
```

Through the harness, `slop run left-pad 5 3 0` (or the `slop_run` tool) runs the file with its working folder inside `.slop-state/run/left-pad/`, so the `registry.xlsx` it writes stays out of your project.

## Servers

`ports/slop-todo` is a Flask server. It is not started by the harness. Start it yourself:

```
cd ports/slop-todo
python app.py
```

It waits five seconds for the "AI model", then listens on port 5000. The front door is `http://127.0.0.1:5000/`.

## CLIs

Any command line works as a port target. Point `slop_profile` and `slop_analyze` at the folder, write the slop, and use `slop_score` to see how it went.

## App lift

`slop_lift` is the last step. It does not turn your app into a standalone app. It turns it into a workbook.

1. Your first 100 file names go on the `app` sheet.
2. A line of text that looks like VBA goes on the `macros` sheet. It is text. It will not run.
3. The result is `lifted_app.xlsx` in the state folder. Open it in Excel. That is your app now.

The original is never touched. Only its file names are read.
