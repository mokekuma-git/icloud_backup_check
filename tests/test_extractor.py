"""
Tests for BackupExtractor and PhotosReader
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from icloud_backup.config import Config
from icloud_backup.extractor import BackupExtractor
from icloud_backup.photos_reader import PhotosReader, PhotosSchemaError


class TestConfig:
    """Test configuration management"""

    def test_config_validation_missing_backup_dir(self):
        """Test validation when BACKUP_DIR is not set"""
        config = Config()
        config.backup_dir = None

        is_valid, error_msg = config.validate()
        assert not is_valid
        assert "BACKUP_DIR" in error_msg

    def test_config_validation_invalid_backup_dir(self):
        """Test validation when backup directory doesn't exist"""
        config = Config()
        config.backup_dir = "/nonexistent/path"
        config.export_dir = "/tmp/export"
        config.csv_output = "/tmp/output.csv"

        is_valid, error_msg = config.validate()
        assert not is_valid
        assert "not found" in error_msg


class TestPhotosReader:
    """Test PhotosReader with real data"""

    @pytest.fixture
    def config(self):
        """Create config from environment"""
        return Config()

    def test_photos_reader_initialization(self, config):
        """Test PhotosReader can be initialized"""
        is_valid, _ = config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid - likely missing .env file")

        try:
            reader = PhotosReader(config.backup_dir)
            assert reader.photos_db_path is not None
            assert Path(reader.photos_db_path).exists()
        except FileNotFoundError as e:
            pytest.skip(f"Photos.sqlite not found: {e}")
        except PhotosSchemaError as e:
            pytest.skip(f"Photos.sqlite schema incompatible: {e}")

    def test_photos_reader_get_metadata(self, config):
        """Test metadata extraction from Photos.sqlite"""
        is_valid, _ = config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid")

        try:
            reader = PhotosReader(config.backup_dir)
            metadata = reader.get_photo_metadata()

            # Should return a dictionary
            assert isinstance(metadata, dict)

            # If there's data, check structure
            if metadata:
                # Get first entry
                first_path = list(metadata.keys())[0]
                first_entry = metadata[first_path]

                # Check required fields
                assert 'capture_date' in first_entry
                assert 'latitude' in first_entry
                assert 'longitude' in first_entry
                assert 'timezone' in first_entry
                assert 'is_favorite' in first_entry

                print(f"Sample metadata for {first_path}:")
                print(f"  Capture date: {first_entry['capture_date']}")
                print(f"  GPS: {first_entry['latitude']}, {first_entry['longitude']}")
                print(f"  Timezone: {first_entry['timezone']}")
                print(f"  Favorite: {first_entry['is_favorite']}")

        except (FileNotFoundError, PhotosSchemaError) as e:
            pytest.skip(f"Photos.sqlite not available: {e}")

    def test_photos_reader_statistics(self, config):
        """Test statistics calculation"""
        is_valid, _ = config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid")

        try:
            reader = PhotosReader(config.backup_dir)
            stats = reader.get_statistics()

            # Check statistics structure
            assert 'total_assets' in stats
            assert 'assets_with_gps' in stats
            assert 'favorite_assets' in stats
            assert 'trashed_assets' in stats

            print(f"Photos.sqlite statistics:")
            print(f"  Total assets: {stats['total_assets']}")
            print(f"  With GPS: {stats['assets_with_gps']}")
            print(f"  Favorites: {stats['favorite_assets']}")
            print(f"  Trashed: {stats['trashed_assets']}")

        except (FileNotFoundError, PhotosSchemaError) as e:
            pytest.skip(f"Photos.sqlite not available: {e}")


class TestBackupExtractor:
    """Test BackupExtractor with real data"""

    @pytest.fixture
    def config(self):
        """Create config from environment"""
        return Config()

    @pytest.fixture
    def extractor(self, config):
        """Create extractor instance"""
        return BackupExtractor(config)

    def test_manifest_db_exists(self, extractor):
        """Test that Manifest.db can be accessed"""
        manifest_path = extractor.get_manifest_db_path()
        assert Path(manifest_path).exists(), f"Manifest.db not found at {manifest_path}"

    def test_get_media_files_from_manifest(self, extractor):
        """Test reading media files from Manifest.db"""
        # Skip if config is not valid (e.g., running without proper .env)
        is_valid, _ = extractor.config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid - likely missing .env file")

        media_files = extractor.get_media_files_from_manifest()

        # Should return a list
        assert isinstance(media_files, list)

        # If there are files, check structure
        if media_files:
            first_file = media_files[0]
            assert 'file_id' in first_file
            assert 'file_name' in first_file
            assert 'relative_path' in first_file
            assert 'file_ext' in first_file

            # New metadata fields should be present
            assert 'capture_date' in first_file
            assert 'latitude' in first_file
            assert 'longitude' in first_file
            assert 'timezone' in first_file
            assert 'is_favorite' in first_file

            # File extension should be in media extensions
            assert first_file['file_ext'] in extractor.media_extensions

            print(f"Sample file with metadata:")
            print(f"  Filename: {first_file['file_name']}")
            print(f"  Capture date: {first_file.get('capture_date', 'N/A')}")
            print(f"  Has GPS: {'Yes' if first_file.get('latitude') else 'No'}")

    def test_get_statistics(self, extractor):
        """Test statistics calculation with metadata"""
        # Skip if config is not valid
        is_valid, _ = extractor.config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid - likely missing .env file")

        media_files = extractor.get_media_files_from_manifest()

        if not media_files:
            pytest.skip("No media files found in backup")

        stats = extractor.get_statistics(media_files)

        # Check statistics structure
        assert 'total_count' in stats
        assert 'by_extension' in stats
        assert 'total_size' in stats
        assert 'missing_files' in stats
        assert 'with_metadata' in stats
        assert 'with_gps' in stats
        assert 'favorites' in stats

        # Total count should match
        assert stats['total_count'] == len(media_files)

        # Total size should be positive if files exist
        if stats['missing_files'] < stats['total_count']:
            assert stats['total_size'] > 0

        print(f"Enhanced statistics:")
        print(f"  Total files: {stats['total_count']}")
        print(f"  With metadata: {stats['with_metadata']}")
        print(f"  With GPS: {stats['with_gps']}")
        print(f"  Favorites: {stats['favorites']}")

    def test_dry_run_mode(self, extractor, tmp_path):
        """Test dry run mode (no actual file copying)"""
        # Skip if config is not valid
        is_valid, _ = extractor.config.validate()
        if not is_valid:
            pytest.skip("Configuration not valid - likely missing .env file")

        # Override export dir to tmp
        extractor.export_dir = str(tmp_path / "export")

        media_files = extractor.get_media_files_from_manifest()

        if not media_files:
            pytest.skip("No media files found in backup")

        # Export in dry run mode with limit
        exported = extractor.export_files(media_files, dry_run=True, limit=5)

        # Should return file information
        assert isinstance(exported, list)
        assert len(exported) <= 5

        # Each exported file should have metadata fields
        if exported:
            first_export = exported[0]
            assert 'capture_date' in first_export
            assert 'latitude' in first_export
            assert 'longitude' in first_export

        # But should not create export directory
        assert not Path(extractor.export_dir).exists()


class TestIntegration:
    """Integration tests with full workflow"""

    def test_full_dry_run_workflow(self, tmp_path):
        """Test complete dry run workflow with metadata"""
        config = Config()
        is_valid, error_msg = config.validate()

        if not is_valid:
            pytest.skip(f"Configuration not valid: {error_msg}")

        # Override output paths
        config.export_dir = str(tmp_path / "export")
        config.csv_output = str(tmp_path / "files.csv")

        extractor = BackupExtractor(config)

        # This should not raise any exceptions
        extractor.run(dry_run=True, limit=10, verbose=False)

        # In dry run mode, files should not be created
        assert not Path(config.export_dir).exists()
        assert not Path(config.csv_output).exists()

    def test_metadata_integration(self):
        """Test that Manifest.db and Photos.sqlite data are properly merged"""
        config = Config()
        is_valid, error_msg = config.validate()

        if not is_valid:
            pytest.skip(f"Configuration not valid: {error_msg}")

        extractor = BackupExtractor(config)
        media_files = extractor.get_media_files_from_manifest()

        if not media_files:
            pytest.skip("No media files found")

        # Check that at least some files have metadata
        files_with_metadata = [f for f in media_files if f.get('capture_date')]

        if extractor.photos_reader:
            # If Photos.sqlite was loaded, we should have some metadata
            print(f"Metadata coverage: {len(files_with_metadata)}/{len(media_files)} files")
            assert len(files_with_metadata) > 0, "Photos.sqlite loaded but no metadata found"
        else:
            print("Photos.sqlite not available, skipping metadata verification")


# Run tests with: uv run pytest tests/test_extractor.py -v
