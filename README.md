# tidyup

[![CI](https://github.com/pdev-labs/tidyup/actions/workflows/ci.yml/badge.svg)](https://github.com/pdev-labs/tidyup/actions/workflows/ci.yml)

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
$ tidyup ~/Downloads --by extension  # one folder per suffix, e.g. png/
$ tidyup ~/Downloads -r             # include subfolders
$ tidyup ~/Downloads -x "*.part"    # leave matching files where they are
$ tidyup ~/Downloads --json         # machine-readable plan
$ tidyup ~/Downloads --prune-empty  # remove folders the sort emptied
$ tidyup ~/Downloads --on-collision skip  # leave clashing files alone
$ tidyup ~/Downloads --min-age 7    # skip anything touched in the last week
$ tidyup ~/Downloads --exclude-from .tidyupignore  # globs from a file
```

## Configuration

Drop a `.tidyup.toml` in the folder to make flags the default:

```toml
by = "date"
recursive = true
exclude = ["*.part", "*.crdownload"]
min_age = 3
prune_empty = true
```

Flags on the command line always win, so a one-off run is never blocked by the
file. Unknown keys and invalid values are reported by name instead of being
ignored.

## In a cron job

`--check` exits 1 when something would move and 0 when the folder is already
sorted, without touching anything, so a scheduled run can alert instead of act:

```console
$ tidyup ~/Downloads --check --min-age 7 || echo "Downloads needs tidying"
```

## Duplicates

```console
$ tidyup ~/Downloads --duplicates
1.2 MB each, 2 copies:
  holiday.mp4
  old/holiday-copy.mp4
Total reclaimable: 1.2 MB
```

Files are bucketed by size first, so only plausible matches are hashed. Use
`--duplicates --json` for scripting. This mode never moves anything.

## Undo

Every real run (never a `--dry-run`) writes `.tidyup/journal/<timestamp>.json`
inside the folder it tidied. That makes the last run reversible:

```console
$ tidyup ~/Downloads --undo --dry-run   # preview the restore
$ tidyup ~/Downloads --undo             # put everything back
```

Restoring also removes the category folders the run created, if they are now
empty, and it renames instead of overwriting if a file with the old name has
reappeared in the meantime. Journals store relative paths, so moving the folder
does not break them.

Runs are kept, not overwritten, so you can go further back:

```console
$ tidyup ~/Downloads --history
20261029T151113084211Z  2026-10-29T15:11:13+00:00  12 file(s)
20261029T150204771930Z  2026-10-29T15:02:04+00:00  3 file(s)

$ tidyup ~/Downloads --undo-id 20261029T150204
```

## Safety model

- `--dry-run` is the default path in the docs and shows the exact plan first.
- Name collisions are resolved by renaming, never by overwriting.
- Every run writes an undo journal, so a mistake is one command away from fixed.

## License

MIT
