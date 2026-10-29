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
```

## Safety model

- `--dry-run` is the default path in the docs and shows the exact plan first.
- Name collisions are resolved by renaming, never by overwriting.
- Every run writes an undo journal, so a mistake is one command away from fixed.

## License

MIT
