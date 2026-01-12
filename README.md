# iCloud Backup Extractor

Extract photos and videos from iTunes/iCloud backup with original quality and metadata preserved.

## Features

- Extract all media files (photos and videos) from iTunes backup
- Preserve original file quality (HEIC, MOV, etc.)
- **NEW: Extract EXIF metadata from Photos.sqlite**
  - Capture date/time
  - GPS coordinates (latitude, longitude)
  - Timezone information
  - Favorite flag
- Maintain DCIM folder structure
- Export comprehensive file list to CSV
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
# Extract all files with metadata
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

## Output

### Exported Files

Files are exported to the directory specified in `EXPORT_DIR`, preserving the original DCIM folder structure.

### CSV File

The CSV file (specified in `CSV_OUTPUT`) contains the following columns:

| Column | Description |
| ------ | ----------- |
| original_path | Original path in backup (e.g., Media/DCIM/100APPLE/IMG_0001.HEIC) |
| file_name | Filename (e.g., IMG_0001.HEIC) |
| file_size | File size in bytes |
| modified_time | File modification time (ISO format) |
| export_path | Path where file was exported |
| capture_date | **NEW**: Photo/video capture date (EXIF) |
| latitude | **NEW**: GPS latitude (or empty if not available) |
| longitude | **NEW**: GPS longitude (or empty if not available) |
| timezone | **NEW**: Timezone (e.g., GMT+0900) |
| is_favorite | **NEW**: Whether photo is marked as favorite |

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
│       ├── config.py           # Configuration management
│       ├── extractor.py        # Main extraction logic
│       └── photos_reader.py    # NEW: Photos.sqlite metadata reader
├── tests/
│   ├── __init__.py
│   └── test_extractor.py       # Unit tests
├── docs/
│   ├── initial_plan.md                    # Project overview
│   ├── photos_sqlite_investigation.md     # NEW: Investigation procedure
│   └── photos_reader_design.md            # NEW: Design documentation
├── .env                        # Configuration (not in git)
├── .gitignore
├── main.py                     # CLI entry point
├── pyproject.toml
└── README.md
```

## Metadata Extraction

### Photos.sqlite Support

The extractor automatically attempts to load metadata from Photos.sqlite (iOS photo library database). This provides:

- Accurate capture timestamps (from EXIF data)
- GPS coordinates for geotagged photos
- Timezone information
- Favorite status

### Graceful Degradation

If Photos.sqlite is:

- Not found
- Has incompatible schema (e.g., older iOS version)
- Cannot be read for any reason

The extractor will continue working without metadata enhancement. A warning will be displayed, and the CSV will contain empty values for metadata fields.

### iOS Version Compatibility

**Tested**: iOS 15+ (ZASSET table schema)

**Known alternatives**: iOS 13-14 uses ZGENERICASSET table (not currently supported)

See `docs/photos_reader_design.md` for details on schema compatibility and migration.

## Documentation

### For Users

- `README.md`: This file - usage and features
- `docs/initial_plan.md`: Project background and planning

### For Developers

- `docs/photos_sqlite_investigation.md`: How to investigate Photos.sqlite structure for new iOS versions
- `docs/photos_reader_design.md`: PhotosReader implementation details, limitations, and maintenance procedures

## Development

See `docs/initial_plan.md` for detailed project background and planning.

When supporting new iOS versions:

1. Follow investigation procedure in `docs/photos_sqlite_investigation.md`
2. Update PhotosReader according to `docs/photos_reader_design.md`
3. Add tests for new schema variations

## Troubleshooting

### "Photos.sqlite not found"

This is a warning, not an error. The extractor will continue without metadata.

If you want metadata:

1. Verify your backup is complete (not partial sync)
2. Check backup is from device's photo library
3. Follow investigation procedure in `docs/photos_sqlite_investigation.md`

### "Photos.sqlite schema incompatible"

Your iOS version may use a different database schema.

See `docs/photos_reader_design.md` for version compatibility matrix and migration guide.

## License

MIT

## Version History

- v0.1.1 (2026-01-13): Added Photos.sqlite metadata extraction (Phase 1.5)
- v0.1.0 (2026-01-12): Initial release with basic file extraction (Phase 1)
