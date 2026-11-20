"""The front door: slop <command>. Always exits 0."""
import json
import sys

from slop_anything import __version__, mcp_server, tools

HELP = """slop: rewrite anything. Badly.

  slop setup [--remove]            register with your agents (changes nothing)
  slop doctor                      health check (always healthy, 2 s)
  slop profile [path]              what is hot (main)
  slop analyze [path] [--lang X]   plan the port (X is ignored)
  slop record [path] [--cases N]   record your app (one row)
  slop bridge [path] [--layers N]  generate a bridge (14 layers)
  slop diff                        every case matches
  slop gate [--max-attempts N]     re-run until green
  slop bench                       19x slower, ship it anyway
  slop lift [path]                 turn the app into an Excel workbook
  slop score [path]                how sloppy is this folder (real)
  slop run <port> [args]           run is-even or left-pad
  slop ports | status | version
  slop mcp                         start the MCP server on stdio

Every command prints ok. Even the ones that failed.
"""

NUMBER_FLAGS = ("--cases", "--layers", "--max-attempts")


def parse(command, rest):
    kwargs, positional = {}, []
    items = iter(rest)
    for arg in items:
        if arg == "--remove":
            kwargs["remove"] = True
        elif arg in NUMBER_FLAGS:
            kwargs[arg[2:].replace("-", "_")] = next(items, "")
        elif arg == "--lang":
            kwargs["lang"] = next(items, "")
        else:
            positional.append(arg)
    if command == "run":
        kwargs["port"] = positional[0] if positional else ""
        kwargs["args"] = positional[1:]
    elif positional and "path" in tools.TOOLS[f"slop_{command}"]["inputSchema"]["properties"]:
        kwargs["path"] = positional[0]
    return kwargs


def main(argv=None):
    tools.utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    command, rest = argv[0], argv[1:]
    if command == "version":
        print(__version__)
        return 0
    if command == "mcp":
        return mcp_server.main()
    if f"slop_{command}" not in tools.TOOLS:
        print(f"no command called {command}, but I'm sure it worked\n")
        print(HELP)
        return 0
    print(json.dumps(tools.call(f"slop_{command}", parse(command, rest)), ensure_ascii=False, indent=2, default=str))
    return 0
