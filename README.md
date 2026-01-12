# iCloud Backup Extractor

Extract photos and videos from iTunes/iCloud backup with original quality preserved.

## Features

- Extract all media files (photos and videos) from iTunes backup
- Preserve original file quality (HEIC, MOV, etc.)
- Maintain DCIM folder structure
- Export file list to CSV
- Dry run mode for testing
- Limit extraction for testing purposes

## Requirements

- Python 3.12+
- iTunes backup (non-encrypted)
- WSL2/Linux environment (for Windows users)

## Installation

```bash
# Install dependencies
uv sync

# Or with dev dependencies
uv sync --all-extras
```

## Configuration

Create a `.env` file in the project root:

```env
BACKUP_DIR="/mnt/c/Users/YourName/AppData/Roaming/Apple Computer/MobileSync/Backup/DEVICE_ID"
EXPORT_DIR="/mnt/c/Users/YourName/iPad-Backup/extracted"
CSV_OUTPUT="/mnt/c/Users/YourName/iPad-Backup/file_list.csv"
```

## Usage

### Dry Run (Recommended for first time)

```bash
# See what would be extracted without copying files
uv run python main.py --dry-run

# Test with first 10 files
uv run python main.py --dry-run --limit 10

# Show detailed progress
uv run python main.py --dry-run --verbose
```

### Actual Extraction

```bash
# Extract all files
uv run python main.py

# Extract with limit (for testing)
uv run python main.py --limit 50

# Extract with verbose output
uv run python main.py --verbose
```

### Options

- `--dry-run`: Show what would be extracted without copying files
- `--limit N`: Limit extraction to first N files
- `-v, --verbose`: Show detailed progress for each file
- `--env PATH`: Specify custom .env file path

## Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_extractor.py -v
```

## Project Structure

```text
icloud_backup_check/
├── src/
│   └── icloud_backup/
│       ├── __init__.py
│       ├── config.py      # Configuration management
│       └── extractor.py   # Main extraction logic
├── tests/
│   ├── __init__.py
│   └── test_extractor.py  # Unit tests
├── .env                   # Configuration (not in git)
├── .gitignore
├── main.py                # CLI entry point
├── pyproject.toml
└── README.md
```

## Development

See `docs/initial_plan.md` for detailed project background and planning.

## License

MIT
