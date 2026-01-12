# PhotosReader Implementation Design

This document describes the design, limitations, and maintenance procedures for `photos_reader.py`.

## Purpose

Extract photo/video metadata from iTunes backup's Photos.sqlite database and merge it with file information from Manifest.db.

## Implementation Scope

### Supported Features

- Extract EXIF creation timestamp
- Extract GPS coordinates (latitude, longitude)
- Extract timezone information
- Extract favorite flag
- Match metadata with files from Manifest.db

### Explicitly NOT Supported

- Album information (requires additional table joins)
- Face recognition data (privacy concern, complex schema)
- Cloud sync status (not relevant for local backup)
- Photo edits/adjustments (complex, not needed for backup)
- Burst photo analysis (complex grouping logic)

## Implementation Assumptions

### iOS Version

**Tested on**: iOS 15+ (iPad Air 5th Gen)

**Schema assumption**: 
- Main table: `ZASSET`
- Extended attributes: `ZADDITIONALASSETATTRIBUTES`

**Known alternatives**:
- Older iOS (13-14): May use `ZGENERICASSET` instead of `ZASSET`

### File Path Matching

**Assumption**: Manifest.db path `Media/DCIM/XXX/YYY` matches Photos.sqlite `DCIM/XXX` + `/` + `YYY`

**Edge cases NOT handled**:
- Files moved between folders
- Duplicate filenames in different folders (unlikely in Camera Roll)
- Non-DCIM paths (e.g., imported from other sources)

### Data Format Assumptions

1. **Timestamps**: Core Data format (seconds since 2001-01-01 00:00:00 GMT)
2. **GPS invalid value**: `-180.0` or `NULL`
3. **Favorite flag**: `1` = favorite, `0` or `NULL` = not favorite

## Implementation Limitations

### Schema Dependency

**Risk**: iOS updates may change database schema

**Impact**: 
- Table names may change
- Column names may change
- Data types may change
- Relationships may be restructured

**Mitigation**:
1. Check table existence before querying
2. Use defensive SQL with column existence checks
3. Graceful degradation if schema is incompatible

### Record Count Mismatch

**Expected**: Photos.sqlite has MORE records than Manifest.db

**Reasons**:
1. Deleted photos (ZTRASHEDSTATE != 0)
2. Cloud-only photos (ZCLOUDLOCALSTATE indicates not local)
3. System photos (screenshots, etc.)

**Handling**:
- Filter by `ZTRASHEDSTATE = 0` (not trashed)
- Only match files that exist in Manifest.db
- Unmatched metadata is ignored (not an error)

### File Matching Accuracy

**Accuracy depends on**:
1. Filename uniqueness (usually guaranteed by iOS)
2. Directory structure preservation
3. No manual file manipulation

**Known failure modes**:
- If user manually renamed files in backup: No match
- If iOS changed naming scheme: Need schema update

## Future Maintenance

### When iOS Updates

#### Investigation Required

1. Create backup from new iOS version
2. Run investigation procedure (see `photos_sqlite_investigation.md`)
3. Compare schema with current implementation
4. Document differences

#### Schema Change Scenarios

**Scenario 1: Column Renamed**

Example: `ZDATECREATED` → `ZCREATIONDATE`

Action:
```python
# Update SQL query
date_column = 'ZCREATIONDATE' if ios_version >= 16 else 'ZDATECREATED'
```

**Scenario 2: Table Renamed**

Example: `ZASSET` → `ZPHOTOASSET`

Action:
1. Update table name constants
2. Add fallback logic for older schemas
3. Update tests

**Scenario 3: Data Format Changed**

Example: Timestamp format changed

Action:
1. Add format detection logic
2. Handle both old and new formats
3. Update conversion functions

### Adding New Metadata Fields

**Procedure**:

1. Identify source column in Photos.sqlite (use investigation procedure)
2. Add column to SQL query in `get_photo_metadata()`
3. Add field to returned dictionary
4. Update CSV output in `extractor.py`
5. Update tests
6. Document the new field

**Example: Adding "isHidden" field**

```python
# In photos_reader.py
def get_photo_metadata(self):
    query = """
    SELECT 
        a.ZFILENAME,
        a.ZDIRECTORY,
        a.ZHIDDEN,  # Add this
        ...
    """
    
    # In result processing
    'is_hidden': row[2],  # Add this
```

### Debugging Metadata Mismatches

**Issue**: Files in Manifest.db have no metadata from Photos.sqlite

**Investigation steps**:

1. Check record counts:
```bash
sqlite3 Manifest.db "SELECT COUNT(*) FROM Files WHERE relativePath LIKE 'Media/DCIM/%';"
sqlite3 Photos.sqlite "SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0;"
```

2. Sample unmatched files:
```python
# In test code
manifest_files = set(manifest file paths)
photos_files = set(photos file paths)
unmatched = manifest_files - photos_files
print(f"Unmatched: {list(unmatched)[:10]}")
```

3. Check path format:
```bash
# Compare actual paths
sqlite3 Manifest.db "SELECT relativePath FROM Files WHERE relativePath LIKE 'Media/DCIM/%' LIMIT 5;"
sqlite3 Photos.sqlite "SELECT ZDIRECTORY, ZFILENAME FROM ZASSET LIMIT 5;"
```

4. Verify Photos.sqlite version:
```bash
sqlite3 Photos.sqlite "SELECT Z_VERSION FROM Z_METADATA;"
```

## Testing Strategy

### Unit Tests

Test `PhotosReader` in isolation:
- Can locate Photos.sqlite from Manifest.db
- Can read ZASSET table
- Returns expected data structure
- Handles missing columns gracefully

### Integration Tests

Test with `BackupExtractor`:
- Metadata correctly merged with Manifest.db data
- CSV output includes metadata columns
- Unmatched files still exported (with empty metadata)

### Regression Tests

When supporting new iOS version:
- Run tests with old backup (should still work)
- Run tests with new backup (should work with new schema)
- Compare results (validate compatibility)

## Error Handling Philosophy

### Fail Gracefully

**Principle**: Metadata enhancement is optional, not critical

**Implementation**:
- If Photos.sqlite not found: Warning only, continue without metadata
- If schema incompatible: Warning only, continue without metadata
- If individual record fails: Log and skip, don't abort

**Example**:
```python
try:
    metadata = photos_reader.get_photo_metadata()
except PhotosSchemaError:
    logger.warning("Photos.sqlite schema incompatible, skipping metadata")
    metadata = {}
```

### Informative Warnings

Provide actionable information:
- ❌ Bad: "Error reading Photos.sqlite"
- ✅ Good: "Photos.sqlite not found at expected location. Run investigation procedure (see docs/photos_sqlite_investigation.md)"

## Performance Considerations

### Query Optimization

Current approach: Single JOIN query with all needed columns

**Alternatives considered**:
1. Two separate queries (assets + attributes): 2x slower
2. Load all into memory: High memory usage for large libraries

**Trade-off**: Current approach balances speed and memory

### Caching

Photos.sqlite is read once at initialization, metadata cached in memory.

**Memory usage**: ~1KB per photo × 10,000 photos = ~10MB (acceptable)

## Version Compatibility Matrix

| iOS Version | ZASSET | ZGENERICASSET | Status | Notes |
|-------------|--------|---------------|--------|-------|
| 13.x | ❌ | ✅ | Not Tested | Older schema |
| 14.x | ❌ | ✅ | Not Tested | Older schema |
| 15.x | ✅ | ❌ | ✅ Tested | Current implementation |
| 16.x | ✅ | ❌ | ⚠️ Assumed | Should work, not tested |
| 17.x+ | ❓ | ❓ | ❓ Unknown | Needs investigation |

## References

### Internal Documents

- `docs/photos_sqlite_investigation.md`: Investigation procedure
- `docs/initial_plan.md`: Project overview
- `README.md`: Usage instructions

### External Resources

- [Apple Core Data Programming Guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/CoreData/)
- iOS reverse engineering community forums
- PhotoDNA schema documentation (unofficial)

## Version History

- 2026-01-13: Initial design document for iOS 15+ implementation
