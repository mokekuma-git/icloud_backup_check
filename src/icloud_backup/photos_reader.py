"""
Photos.sqlite Metadata Reader
Extract photo/video metadata from iTunes backup
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class PhotosSchemaError(Exception):
    """Exception raised when Photos.sqlite schema is incompatible"""
    pass


class PhotosReader:
    """
    Read photo metadata from Photos.sqlite in iTunes backup

    Supports iOS 15+ schema (ZASSET table)
    Gracefully degrades if schema is incompatible
    """

    # Core Data epoch: 2001-01-01 00:00:00 GMT
    CORE_DATA_EPOCH = datetime(2001, 1, 1)
    CORE_DATA_EPOCH_UNIX = 978307200  # Unix timestamp for 2001-01-01

    # GPS invalid values
    GPS_INVALID = -180.0

    def __init__(self, backup_dir: str):
        """
        Initialize PhotosReader

        Args:
            backup_dir: Path to iTunes backup directory

        Raises:
            FileNotFoundError: If backup directory or Manifest.db not found
            PhotosSchemaError: If Photos.sqlite has incompatible schema
        """
        self.backup_dir = backup_dir
        self.manifest_db_path = os.path.join(backup_dir, "Manifest.db")
        self.photos_db_path = None

        if not os.path.exists(self.backup_dir):
            raise FileNotFoundError(f"Backup directory not found: {backup_dir}")

        if not os.path.exists(self.manifest_db_path):
            raise FileNotFoundError(f"Manifest.db not found: {self.manifest_db_path}")

        # Locate Photos.sqlite
        self._locate_photos_db()

        # Verify schema compatibility
        self._verify_schema()

    def _locate_photos_db(self):
        """
        Locate Photos.sqlite file using Manifest.db

        Raises:
            FileNotFoundError: If Photos.sqlite not found
        """
        conn = sqlite3.connect(self.manifest_db_path)
        cursor = conn.cursor()

        # Search for Photos.sqlite in CameraRollDomain
        query = """
        SELECT fileID
        FROM Files
        WHERE domain = 'CameraRollDomain'
        AND relativePath = 'Media/PhotoData/Photos.sqlite'
        """

        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise FileNotFoundError(
                "Photos.sqlite not found in backup. "
                "See docs/photos_sqlite_investigation.md for troubleshooting."
            )

        file_id = result[0]
        # File stored as XX/XXXX... where XX is first 2 chars of hash
        subdir = file_id[:2]
        self.photos_db_path = os.path.join(self.backup_dir, subdir, file_id)

        if not os.path.exists(self.photos_db_path):
            raise FileNotFoundError(
                f"Photos.sqlite file not found at expected location: {self.photos_db_path}"
            )

    def _verify_schema(self):
        """
        Verify Photos.sqlite has expected schema

        Raises:
            PhotosSchemaError: If schema is incompatible
        """
        conn = sqlite3.connect(self.photos_db_path)
        cursor = conn.cursor()

        # Check if ZASSET table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ZASSET'"
        )

        if not cursor.fetchone():
            # Try ZGENERICASSET for older iOS
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ZGENERICASSET'"
            )
            if cursor.fetchone():
                conn.close()
                raise PhotosSchemaError(
                    "Found ZGENERICASSET table (iOS 13-14 schema). "
                    "Current implementation supports iOS 15+ (ZASSET table). "
                    "See docs/photos_reader_design.md for schema migration."
                )
            else:
                conn.close()
                raise PhotosSchemaError(
                    "Neither ZASSET nor ZGENERICASSET table found. "
                    "Unknown Photos.sqlite schema. "
                    "See docs/photos_sqlite_investigation.md for investigation procedure."
                )

        conn.close()

    def get_photo_metadata(self) -> Dict[str, Dict]:
        """
        Extract metadata for all photos/videos

        Returns:
            Dictionary mapping file path to metadata:
            {
                'DCIM/100APPLE/IMG_0001.HEIC': {
                    'capture_date': '2022-03-21 11:19:30',
                    'latitude': 35.6812,
                    'longitude': 139.7671,
                    'timezone': 'GMT+0900',
                    'is_favorite': False
                }
            }

        Raises:
            PhotosSchemaError: If query fails due to schema issues
        """
        conn = sqlite3.connect(self.photos_db_path)
        cursor = conn.cursor()

        # Query for assets with additional attributes
        # Only non-trashed items (ZTRASHEDSTATE = 0)
        query = """
        SELECT
            a.ZFILENAME,
            a.ZDIRECTORY,
            a.ZDATECREATED,
            a.ZLATITUDE,
            a.ZLONGITUDE,
            a.ZFAVORITE,
            aa.ZEXIFTIMESTAMPSTRING,
            aa.ZTIMEZONENAME
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES aa
            ON a.ZADDITIONALATTRIBUTES = aa.Z_PK
        WHERE a.ZTRASHEDSTATE = 0
            AND a.ZFILENAME IS NOT NULL
        """

        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            conn.close()
            raise PhotosSchemaError(
                f"Failed to query Photos.sqlite: {str(e)}. "
                "Schema may be incompatible. "
                "See docs/photos_reader_design.md"
            )

        # Build metadata dictionary
        metadata = {}

        for row in rows:
            filename = row[0]
            directory = row[1]
            date_created = row[2]
            latitude = row[3]
            longitude = row[4]
            is_favorite = row[5]
            exif_timestamp = row[6]
            timezone = row[7]

            # Construct file path (matching Manifest.db format without Media/ prefix)
            if directory and filename:
                file_path = f"{directory}/{filename}"
            else:
                continue

            # Process capture date
            capture_date = None
            if exif_timestamp:
                # Use EXIF timestamp if available (more reliable)
                capture_date = exif_timestamp
            elif date_created:
                # Fall back to Core Data timestamp
                capture_date = self._convert_core_data_timestamp(date_created)

            # Process GPS coordinates
            lat = None if latitude == self.GPS_INVALID else latitude
            lon = None if longitude == self.GPS_INVALID else longitude

            metadata[file_path] = {
                'capture_date': capture_date,
                'latitude': lat,
                'longitude': lon,
                'timezone': timezone,
                'is_favorite': bool(is_favorite) if is_favorite else False
            }

        conn.close()
        return metadata

    def _convert_core_data_timestamp(self, timestamp: float) -> str:
        """
        Convert Core Data timestamp to ISO format string

        Args:
            timestamp: Seconds since 2001-01-01 00:00:00 GMT

        Returns:
            ISO format datetime string (YYYY-MM-DD HH:MM:SS)
        """
        dt = self.CORE_DATA_EPOCH + timedelta(seconds=timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def get_statistics(self) -> Dict:
        """
        Get statistics about Photos.sqlite content

        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(self.photos_db_path)
        cursor = conn.cursor()

        stats = {}

        # Total assets
        cursor.execute("SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0")
        stats['total_assets'] = cursor.fetchone()[0]

        # Assets with GPS
        cursor.execute(
            f"SELECT COUNT(*) FROM ZASSET "
            f"WHERE ZTRASHEDSTATE = 0 AND ZLATITUDE != {self.GPS_INVALID}"
        )
        stats['assets_with_gps'] = cursor.fetchone()[0]

        # Favorite assets
        cursor.execute(
            "SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE = 0 AND ZFAVORITE = 1"
        )
        stats['favorite_assets'] = cursor.fetchone()[0]

        # Trashed assets
        cursor.execute("SELECT COUNT(*) FROM ZASSET WHERE ZTRASHEDSTATE != 0")
        stats['trashed_assets'] = cursor.fetchone()[0]

        conn.close()
        return stats
