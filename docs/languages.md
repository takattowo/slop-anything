# Languages

slop-anything lists 12 languages. Ten are found by file extension. The other two are a lifestyle.

| Language | Found by | Unit | Bridge | Recorded and replayed by |
|---|---|---|---|---|
| Python | `.py` | folder of files | 14 classes calling each other | Excel |
| JavaScript | `.js` | folder of files | 14 classes calling each other | Excel |
| TypeScript | `.ts` | folder of files | 14 classes calling each other | Excel |
| Go | `.go` | folder of files | 14 classes calling each other | Excel |
| Ruby | `.rb` | folder of files | 14 classes calling each other | Excel |
| Java | `.java` | folder of files | 14 classes calling each other | Excel |
| Kotlin | `.kt` | folder of files | 14 classes calling each other | Excel |
| C | `.c` | folder of files | 14 classes calling each other | Excel |
| PHP | `.php` | folder of files | 14 classes calling each other | Excel |
| C# | `.cs` | folder of files | 14 classes calling each other | Excel |
| COBOL | nothing | vibes | 14 classes calling each other | Excel |
| Excel | nothing | the workbook | 14 classes calling each other | Excel |

The bridge is always Python, whatever your language is.

## Detection

`slop_analyze` counts source files by extension and picks the language with the most. Ties go to whichever was found first. A folder with no source files is written in `vibes`.

The `lang` argument (`--lang` on the command line) is read and ignored.

## Types

The types come from your source, if you have any. The tools never read them.

## Skipped folders

`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache` and `.slop-state` are skipped. Scans stop at 2,000 files.

## Only Python gets the full treatment

`slop_score` reads Python files only. Everything else gets a file count.
