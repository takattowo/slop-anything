# Accessibility

## Command line and MCP

All results are plain text on stdout with no color or animation. Diagnostics are plain text on stderr and can be silenced by redirecting stderr (`2>$null` in PowerShell, `2>/dev/null` in POSIX shells).

## The todo-api web page

The page at `http://127.0.0.1:5000/` uses semantic HTML and keyboard-reachable controls. It re-fetches and re-renders the whole list every 250 ms for real-time sync, which can make screen readers re-announce the list. This is a known limitation, recorded in [ports/todo-api/SLOP.md](ports/todo-api/SLOP.md). The CLI and the JSON API offer the same features without it.

## Documentation

The docs are Markdown with real headings and tables. Badges in the README are decorative; the same facts are stated in the text.

## Reporting

If something is hard to use, please open an issue.
