# Photos.sqlite Investigation Procedure

This document describes how to investigate the structure of Photos.sqlite from iTunes backup when implementing new features or debugging issues.

## Background

iTunes backup stores Photos.sqlite (the photo library metadata database) as a hashed file, just like other files. The database schema can vary between iOS versions, so investigation is necessary when:

- Supporting a new iOS version
- Implementing new metadata extraction features
- Debugging metadata matching issues

## Investigation Steps

### Step 1: Locate Photos.sqlite

Photos.sqlite is stored with a hashed filename. Use Manifest.db to find it:

```bash
cd /path/to/backup/directory

# Search for Photos.sqlite in Manifest.db
sqlite3 Manifest.db "SELECT fileID, domain, relativePath FROM Files WHERE relativePath LIKE '%Photos.sqlite%' ORDER BY relativePath;"
```

Expected output:
```
32620da381cc155fc7092c3f8bc71c18a8ea18f1|HomeDomain|Library/Photos/Libraries/Application/...
12b144c0bd44f2b3dffd9186d3f9c05b917cee25|CameraRollDomain|Media/PhotoData/Photos.sqlite
```

**Important**: The `CameraRollDomain` entry contains the actual photo library metadata.

### Step 2: Access the Photos.sqlite File

```bash
# Extract fileID (first column from Step 1)
FILE_ID="12b144c0bd44f2b3dffd9186d3f9c05b917cee25"

# Construct file path (first 2 chars become directory name)
SUBDIR="${FILE_ID:0:2}"
PHOTO_DB_PATH="${SUBDIR}/${FILE_ID}"

# Verify file exists and check size
ls -lh "$PHOTO_DB_PATH"
du -h "$PHOTO_DB_PATH"
```

Expected: File should be several MB to tens of MB depending on photo library size.

### Step 3: Identify Available Tables

```bash
# List all tables
sqlite3 "$PHOTO_DB_PATH" ".tables"
```

**Key tables** (may vary by iOS version):
- `ZASSET` or `ZGENERICASSET`: Main asset (photo/video) information
- `ZADDITIONALASSETATTRIBUTES`: Extended metadata (EXIF, file info)
- `ZGENERICALBUM` or similar: Album information
- `ZCLOUDMASTER`: Cloud sync information

### Step 4: Examine Table Schema

```bash
# Check structure of main asset table
# Try ZASSET first (newer iOS), then ZGENERICASSET (older iOS)
sqlite3 "$PHOTO_DB_PATH" ".schema ZASSET"
sqlite3 "$PHOTO_DB_PATH" ".schema ZGENERICASSET"

# Check additional attributes table
sqlite3 "$PHOTO_DB_PATH" ".schema ZADDITIONALASSETATTRIBUTES"

# List column information in tabular format
sqlite3 "$PHOTO_DB_PATH" "PRAGMA table_info(ZASSET);"
```

**Important columns to identify**:
- Primary key: Usually `Z_PK`
- Filename: `ZFILENAME`
- Directory: `ZDIRECTORY`
- Creation date: `ZDATECREATED`
- GPS coordinates: `ZLATITUDE`, `ZLONGITUDE`
- Foreign key to attributes: `ZADDITIONALATTRIBUTES`

### Step 5: Check Sample Data

```bash
# View sample records
sqlite3 -header -column "$PHOTO_DB_PATH" \
  "SELECT Z_PK, ZFILENAME, ZDIRECTORY, ZDATECREATED, ZLATITUDE, ZLONGITUDE 
   FROM ZASSET LIMIT 5;"

# Check total record count
sqlite3 "$PHOTO_DB_PATH" "SELECT COUNT(*) FROM ZASSET;"

# Examine additional attributes
sqlite3 -header -column "$PHOTO_DB_PATH" \
  "SELECT a.Z_PK, a.ZFILENAME, aa.ZORIGINALFILENAME, 
          aa.ZEXIFTIMESTAMPSTRING, aa.ZTIMEZONENAME 
   FROM ZASSET a 
   LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON a.ZADDITIONALATTRIBUTES = aa.Z_PK 
   LIMIT 5;"
```

### Step 6: Understand File Path Matching

Compare paths between Manifest.db and Photos.sqlite:

**Manifest.db format**:
```
Media/DCIM/100APPLE/IMG_0001.HEIC
```

**Photos.sqlite format**:
```
ZDIRECTORY: DCIM/100APPLE
ZFILENAME: IMG_0001.HEIC
```

**Matching logic**: 
1. Remove `Media/` prefix from Manifest.db path
2. Split remaining path into directory and filename
3. Match with `ZDIRECTORY + '/' + ZFILENAME`

### Step 7: Identify Special Values

Check for special/invalid values in the data:

```bash
# Check GPS invalid values
sqlite3 "$PHOTO_DB_PATH" \
  "SELECT DISTINCT ZLATITUDE, ZLONGITUDE FROM ZASSET 
   WHERE ZLATITUDE IS NOT NULL LIMIT 10;"
```

**Common special values**:
- GPS `-180.0`: Invalid/no GPS data
- Dates: Core Data timestamp (seconds since 2001-01-01 00:00:00 GMT)

## iOS Version Differences

### Known Schema Variations

| iOS Version | Main Table | Notes |
|-------------|------------|-------|
| iOS 13-14 | ZGENERICASSET | Older schema |
| iOS 15+ | ZASSET | Current schema (as of this implementation) |

### When Supporting New iOS Versions

1. Run all steps above on backup from new iOS version
2. Document any schema differences
3. Update `photos_reader.py` to handle both schemas if needed
4. Add version detection logic if schemas are incompatible

## Data Type Reference

### Core Data Timestamps

Photos.sqlite uses Core Data timestamps (Cocoa epoch):
- Epoch: 2001-01-01 00:00:00 GMT
- Format: Floating point seconds since epoch
- Conversion: Add 978307200 to get Unix timestamp

Example:
```python
from datetime import datetime

core_data_timestamp = 669521970.78148
unix_timestamp = core_data_timestamp + 978307200
dt = datetime.fromtimestamp(unix_timestamp)
# Result: 2022-03-21 11:19:30
```

### EXIF Timestamp Strings

Alternative timestamp format in `ZADDITIONALASSETATTRIBUTES.ZEXIFTIMESTAMPSTRING`:
- Format: `YYYY:MM:DD HH:MM:SS`
- Example: `2022:03:21 11:19:30`

## Troubleshooting

### Photos.sqlite Not Found

If Photos.sqlite is not found in Manifest.db:
- Verify backup is complete and not encrypted
- Check if backup is from very old iOS version (different structure)
- Verify backup is from device's photo library, not just iCloud sync

### Table Not Found Errors

If `ZASSET` or `ZGENERICASSET` don't exist:
- Try listing all tables (`.tables`)
- Look for alternative table names
- Check iOS version and compare with known schemas

### No Matching Records

If record counts differ significantly between Manifest.db and Photos.sqlite:
- Photos.sqlite may include deleted items (check `ZTRASHEDSTATE`)
- Some assets may be cloud-only (check `ZCLOUDLOCALSTATE`)
- Some items may be in albums but not in camera roll

## References

- Apple Core Data documentation
- iOS Photos.app database schema research
- Community reverse engineering efforts

## Version History

- 2026-01-13: Initial documentation based on iOS 15+ iPad Air 5th Gen backup
