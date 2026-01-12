"""
Tests for BackupExtractor
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from icloud_backup.config import Config
from icloud_backup.extractor import BackupExtractor


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
            
            # File extension should be in media extensions
            assert first_file['file_ext'] in extractor.media_extensions
    
    def test_get_statistics(self, extractor):
        """Test statistics calculation"""
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
        
        # Total count should match
        assert stats['total_count'] == len(media_files)
        
        # Total size should be positive if files exist
        if stats['missing_files'] < stats['total_count']:
            assert stats['total_size'] > 0
    
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
        
        # But should not create export directory
        assert not Path(extractor.export_dir).exists()


class TestIntegration:
    """Integration tests with full workflow"""
    
    def test_full_dry_run_workflow(self, tmp_path):
        """Test complete dry run workflow"""
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


# Run tests with: uv run pytest tests/test_extractor.py -v
