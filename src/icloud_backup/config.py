"""
Configuration management for iCloud Backup Extractor
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration class for backup extraction"""

    def __init__(self, env_path=None):
        """
        Initialize configuration

        Args:
            env_path: Path to .env file. If None, searches in standard locations.
        """
        if env_path:
            load_dotenv(env_path)
        else:
            # Try to find .env in project root
            current = Path(__file__).resolve()
            for parent in [current.parent.parent.parent, current.parent.parent.parent.parent]:
                env_file = parent / ".env"
                if env_file.exists():
                    load_dotenv(env_file)
                    break

        self.backup_dir = os.getenv("BACKUP_DIR")
        self.export_dir = os.getenv("EXPORT_DIR")
        self.csv_output = os.getenv("CSV_OUTPUT")

        # Media file extensions
        self.media_extensions = {'.heic', '.jpg', '.jpeg', '.png', '.gif',
                                '.mov', '.mp4', '.m4v', '.avi'}

    def validate(self):
        """
        Validate configuration

        Returns:
            tuple: (is_valid, error_message)
        """
        if not self.backup_dir:
            return False, "BACKUP_DIR not set"

        if not os.path.exists(self.backup_dir):
            return False, f"Backup directory not found: {self.backup_dir}"

        manifest_path = os.path.join(self.backup_dir, "Manifest.db")
        if not os.path.exists(manifest_path):
            return False, f"Manifest.db not found in: {self.backup_dir}"

        if not self.export_dir:
            return False, "EXPORT_DIR not set"

        if not self.csv_output:
            return False, "CSV_OUTPUT not set"

        return True, None

    def __repr__(self):
        return (f"Config(backup_dir={self.backup_dir}, "
                f"export_dir={self.export_dir}, "
                f"csv_output={self.csv_output})")
