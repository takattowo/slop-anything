# Accessibility

This project is bad at accessibility on purpose in one place, and tries in the others.

## On purpose

The `slop-todo` front page (`ports/slop-todo/static/index.html`) is a parody of a bad page: Comic Sans, a rainbow gradient, green text on top of it, a `<marquee>`, and a list that is rewritten every 100 ms. Screen readers will announce it over and over. Do not use it as a model.

## Everywhere else

- The command line and the MCP tools print JSON and plain text. No color, no animation, no tables you have to see.
- The docs are Markdown with real headings and real tables.
- Emoji in output (✅, 🚀) are decoration. The text next to them says the same thing.

## Reporting

If something outside the parody page is hard to use, open an issue.
