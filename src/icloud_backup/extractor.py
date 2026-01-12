"""
iTunes Backup Media Extractor
Extract photos and videos from iTunes backup
"""

import sqlite3
import os
import shutil
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class BackupExtractor:
    """Extract media files from iTunes backup"""
    
    def __init__(self, config):
        """
        Initialize extractor
        
        Args:
            config: Config object with backup settings
        """
        self.config = config
        self.backup_dir = config.backup_dir
        self.export_dir = config.export_dir
        self.csv_output = config.csv_output
        self.media_extensions = config.media_extensions
    
    def get_manifest_db_path(self) -> str:
        """Get path to Manifest.db"""
        return os.path.join(self.backup_dir, "Manifest.db")
    
    def get_media_files_from_manifest(self) -> List[Dict]:
        """
        Extract media file information from Manifest.db
        
        Returns:
            List of dictionaries containing file information
        """
        manifest_path = self.get_manifest_db_path()
        
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest.db not found at {manifest_path}")
        
        conn = sqlite3.connect(manifest_path)
        cursor = conn.cursor()
        
        # Query for files in Media/DCIM/ directory
        query = """
        SELECT fileID, domain, relativePath, file
        FROM Files
        WHERE relativePath LIKE 'Media/DCIM/%'
        AND flags = 1
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        media_files = []
        for row in rows:
            file_id, domain, relative_path, file_blob = row
            
            # Extract file information
            file_name = os.path.basename(relative_path)
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # Only include media files
            if file_ext in self.media_extensions:
                media_files.append({
                    'file_id': file_id,
                    'domain': domain,
                    'relative_path': relative_path,
                    'file_name': file_name,
                    'file_ext': file_ext
                })
        
        conn.close()
        return media_files
    
    def get_backup_file_path(self, file_id: str) -> Optional[str]:
        """
        Get actual file path in backup directory from file_id hash
        
        Args:
            file_id: File ID hash from Manifest.db
            
        Returns:
            File path if exists, None otherwise
        """
        if len(file_id) < 2:
            return None
        
        # File ID is stored as XX/YYYYYYYY... where XX is first 2 chars
        subdir = file_id[:2]
        file_path = os.path.join(self.backup_dir, subdir, file_id)
        
        return file_path if os.path.exists(file_path) else None
    
    def get_statistics(self, media_files: List[Dict]) -> Dict:
        """
        Calculate statistics about media files
        
        Args:
            media_files: List of media file information
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_count': len(media_files),
            'by_extension': {},
            'total_size': 0,
            'missing_files': 0
        }
        
        for file_info in media_files:
            ext = file_info['file_ext']
            stats['by_extension'][ext] = stats['by_extension'].get(ext, 0) + 1
            
            # Check if file exists and get size
            file_path = self.get_backup_file_path(file_info['file_id'])
            if file_path:
                stats['total_size'] += os.path.getsize(file_path)
            else:
                stats['missing_files'] += 1
        
        return stats
    
    def export_files(self, media_files: List[Dict], 
                    dry_run: bool = False, 
                    limit: Optional[int] = None,
                    verbose: bool = False) -> List[Dict]:
        """
        Export media files from backup to export directory
        
        Args:
            media_files: List of media file information
            dry_run: If True, don't actually copy files
            limit: Maximum number of files to export
            verbose: If True, print detailed progress
            
        Returns:
            List of exported file information
        """
        if not dry_run:
            os.makedirs(self.export_dir, exist_ok=True)
        
        exported_files = []
        total = len(media_files) if limit is None else min(limit, len(media_files))
        files_to_process = media_files[:limit] if limit else media_files
        
        print(f"Found {len(media_files)} media files")
        if limit:
            print(f"Processing first {total} files (limit applied)")
        if dry_run:
            print("DRY RUN MODE - No files will be copied")
        print(f"Export directory: {self.export_dir}")
        print("-" * 60)
        
        for idx, file_info in enumerate(files_to_process, 1):
            file_id = file_info['file_id']
            file_name = file_info['file_name']
            relative_path = file_info['relative_path']
            
            # Get source file path
            source_path = self.get_backup_file_path(file_id)
            
            if not source_path:
                if verbose:
                    print(f"[{idx}/{total}] SKIP: {file_name} (file not found)")
                continue
            
            # Create destination path (preserve DCIM folder structure)
            path_parts = Path(relative_path).parts[2:]  # Skip 'Media/DCIM/'
            dest_subdir = os.path.join(self.export_dir, *path_parts[:-1]) if len(path_parts) > 1 else self.export_dir
            
            if not dry_run:
                os.makedirs(dest_subdir, exist_ok=True)
            
            dest_path = os.path.join(dest_subdir, file_name)
            
            # Handle duplicate filenames
            counter = 1
            while not dry_run and os.path.exists(dest_path):
                name, ext = os.path.splitext(file_name)
                dest_path = os.path.join(dest_subdir, f"{name}_{counter}{ext}")
                counter += 1
            
            # Copy file or simulate
            try:
                file_size = os.path.getsize(source_path)
                
                if not dry_run:
                    shutil.copy2(source_path, dest_path)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(dest_path))
                else:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(source_path))
                
                exported_files.append({
                    'original_path': relative_path,
                    'file_name': file_name,
                    'file_size': file_size,
                    'modified_time': mod_time.isoformat(),
                    'export_path': dest_path
                })
                
                if verbose:
                    mode = "[DRY RUN]" if dry_run else "[OK]"
                    print(f"[{idx}/{total}] {mode}: {file_name} ({file_size:,} bytes)")
                
            except Exception as e:
                print(f"[{idx}/{total}] ERROR: {file_name} - {str(e)}")
        
        return exported_files
    
    def save_to_csv(self, exported_files: List[Dict], dry_run: bool = False):
        """
        Save exported file information to CSV
        
        Args:
            exported_files: List of exported file information
            dry_run: If True, don't actually write the file
        """
        if dry_run:
            print(f"\nDRY RUN: Would save file list to: {self.csv_output}")
            return
        
        with open(self.csv_output, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['original_path', 'file_name', 'file_size', 
                         'modified_time', 'export_path']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for file_info in exported_files:
                writer.writerow(file_info)
        
        print(f"\nFile list saved to: {self.csv_output}")
    
    def run(self, dry_run: bool = False, limit: Optional[int] = None, 
            verbose: bool = False):
        """
        Main execution method
        
        Args:
            dry_run: If True, don't actually copy files
            limit: Maximum number of files to export
            verbose: If True, print detailed progress
        """
        print("iTunes Backup Media Extractor")
        print("=" * 60)
        print(f"Backup directory: {self.backup_dir}")
        print(f"Export directory: {self.export_dir}")
        print("=" * 60)
        print()
        
        try:
            # Step 1: Get media files from Manifest.db
            print("Step 1: Reading Manifest.db...")
            media_files = self.get_media_files_from_manifest()
            print(f"Found {len(media_files)} media files")
            
            # Show statistics
            stats = self.get_statistics(media_files)
            print(f"\nStatistics:")
            print(f"  Total files: {stats['total_count']}")
            print(f"  Total size: {stats['total_size']:,} bytes ({stats['total_size'] / 1024 / 1024:.2f} MB)")
            print(f"  By extension:")
            for ext, count in sorted(stats['by_extension'].items()):
                print(f"    {ext}: {count}")
            if stats['missing_files'] > 0:
                print(f"  Missing files: {stats['missing_files']}")
            print()
            
            # Step 2: Export files
            print("Step 2: Exporting files...")
            exported_files = self.export_files(media_files, dry_run, limit, verbose)
            print()
            
            # Step 3: Save to CSV
            print("Step 3: Saving file list...")
            self.save_to_csv(exported_files, dry_run)
            print()
            
            # Summary
            print("=" * 60)
            if dry_run:
                print("DRY RUN completed!")
            else:
                print("Export completed!")
            print(f"Files processed: {len(exported_files)}")
            if not dry_run:
                print(f"Export location: {self.export_dir}")
                print(f"File list: {self.csv_output}")
            print("=" * 60)
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
