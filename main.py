#!/usr/bin/env python3
"""
iCloud Backup Extractor - CLI Entry Point
"""

import sys
import argparse
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent / "src"))

from icloud_backup.config import Config
from icloud_backup.extractor import BackupExtractor


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Extract photos and videos from iTunes/iCloud backup with metadata"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without copying files"
    )

    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Limit extraction to first N files (for testing)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress for each file"
    )

    parser.add_argument(
        "--env",
        type=str,
        metavar="PATH",
        help="Path to .env file (default: search in project root)"
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = Config(env_path=args.env)
        is_valid, error_msg = config.validate()

        if not is_valid:
            print(f"Configuration error: {error_msg}")
            sys.exit(1)

        # Create extractor and run
        extractor = BackupExtractor(config)
        extractor.run(
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose
        )

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
