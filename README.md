# tidyup

A small, safe file organizer for folders that have gotten out of hand.

`tidyup` sorts files into subfolders by type, previews every move before
touching anything, never overwrites a file it did not create, and can undo an
entire run with one command.

## Install

```console
$ pipx install git+https://github.com/pdev-labs/tidyup
```

Or from a checkout:

```console
$ pip install -e ".[dev]"
```

## Usage

```console
$ tidyup ~/Downloads --dry-run
Would move 3 file(s) in /home/you/Downloads
  invoice.pdf -> Documents/invoice.pdf
  shot.png -> Images/shot.png
  call.mp3 -> Audio/call.mp3
```

Then drop `--dry-run` to do it for real.

```console
$ tidyup ~/Downloads --by date      # 2026/10/ instead of category folders
$ tidyup ~/Downloads -r             # include subfolders
```

## Safety model

- `--dry-run` is the default path in the docs and shows the exact plan first.
- Name collisions are resolved by renaming, never by overwriting.
- Every run writes an undo journal, so a mistake is one command away from fixed.

## License

MIT
