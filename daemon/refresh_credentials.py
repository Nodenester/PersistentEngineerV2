#!/usr/bin/env python3
"""
Credential Refresh Helper for Persistent Engineer

This script syncs Claude Code credentials from the mounted parent directory
to the container's ~/.claude directory. It's called automatically when
OAuth tokens expire, but can also be run manually.

Usage:
    python refresh_credentials.py [--force]
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CredentialRefresh')

# Source directories (where fresh credentials might be mounted)
SOURCE_DIRS = [
    Path('/claude-credentials'),
    Path('/host-claude'),
]

# Target directory (where Claude Code looks for credentials)
TARGET_DIR = Path('/home/agent/.claude')

# Files to preserve (container-specific, shouldn't be overwritten)
PRESERVE_FILES = ['settings.json']

# Files that indicate valid credentials
CREDENTIAL_FILES = ['credentials.json', '.credentials.json', 'auth.json']


def check_source_credentials(source_dir: Path) -> dict:
    """Check if source directory has valid credentials and get their info."""
    if not source_dir.exists() or not source_dir.is_dir():
        return {'valid': False, 'reason': 'Directory does not exist'}

    # Look for credential files
    for cred_file in CREDENTIAL_FILES:
        cred_path = source_dir / cred_file
        if cred_path.exists():
            try:
                stat = cred_path.stat()
                return {
                    'valid': True,
                    'file': cred_file,
                    'path': str(cred_path),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size
                }
            except Exception as e:
                logger.warning(f"Error checking {cred_path}: {e}")

    # Check for any files at all
    files = list(source_dir.iterdir())
    if not files:
        return {'valid': False, 'reason': 'Directory is empty'}

    return {
        'valid': True,
        'file': 'unknown',
        'files': [f.name for f in files[:10]],  # List first 10 files
        'reason': 'No standard credential file found, but directory has content'
    }


def get_target_credential_info() -> dict:
    """Get info about current target credentials."""
    if not TARGET_DIR.exists():
        return {'valid': False, 'reason': 'Target directory does not exist'}

    for cred_file in CREDENTIAL_FILES:
        cred_path = TARGET_DIR / cred_file
        if cred_path.exists():
            try:
                stat = cred_path.stat()
                return {
                    'valid': True,
                    'file': cred_file,
                    'path': str(cred_path),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size
                }
            except Exception as e:
                logger.warning(f"Error checking target {cred_path}: {e}")

    return {'valid': False, 'reason': 'No credential file found in target'}


def sync_credentials(source_dir: Path, force: bool = False) -> bool:
    """
    Sync credentials from source to target directory.

    Args:
        source_dir: Source directory with fresh credentials
        force: If True, always sync. If False, only sync if source is newer.

    Returns:
        True if sync was successful, False otherwise
    """
    logger.info(f"Syncing credentials from {source_dir} to {TARGET_DIR}")

    # Create target if it doesn't exist
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Create backup
    backup_dir = Path('/workspace/.state/claude_backup')
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        # Backup current credentials
        if TARGET_DIR.exists():
            for item in TARGET_DIR.iterdir():
                if item.name not in PRESERVE_FILES:
                    backup_path = backup_dir / f"{item.name}.{backup_time}.bak"
                    if item.is_dir():
                        shutil.copytree(item, backup_path)
                    else:
                        shutil.copy2(item, backup_path)
            logger.info(f"Created backup at {backup_dir}")

        # Copy fresh credentials
        copied_count = 0
        for item in source_dir.iterdir():
            if item.name in PRESERVE_FILES:
                logger.debug(f"Skipping preserved file: {item.name}")
                continue

            dest = TARGET_DIR / item.name
            try:
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
                copied_count += 1
                logger.debug(f"Copied: {item.name}")
            except Exception as e:
                logger.warning(f"Failed to copy {item.name}: {e}")

        # Fix permissions
        try:
            subprocess.run(
                ['chown', '-R', 'agent:agent', str(TARGET_DIR)],
                capture_output=True,
                check=False
            )
        except Exception as e:
            logger.warning(f"Failed to fix permissions: {e}")

        logger.info(f"Successfully synced {copied_count} items from {source_dir}")
        return True

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False


def refresh_credentials(force: bool = False) -> dict:
    """
    Main function to refresh credentials.

    Returns:
        dict with status and details
    """
    result = {
        'success': False,
        'source': None,
        'message': '',
        'target_info': get_target_credential_info()
    }

    # Try each source directory
    for source_dir in SOURCE_DIRS:
        source_info = check_source_credentials(source_dir)
        logger.info(f"Checking {source_dir}: {source_info}")

        if source_info.get('valid'):
            result['source'] = str(source_dir)
            result['source_info'] = source_info

            # Check if source is newer than target (unless force)
            if not force and result['target_info'].get('valid'):
                source_time = source_info.get('modified', '')
                target_time = result['target_info'].get('modified', '')
                if source_time and target_time and source_time <= target_time:
                    result['message'] = f"Target credentials are already up to date (source: {source_time}, target: {target_time})"
                    result['success'] = True
                    logger.info(result['message'])
                    return result

            # Perform sync
            if sync_credentials(source_dir, force):
                result['success'] = True
                result['message'] = f"Credentials refreshed from {source_dir}"
                result['target_info'] = get_target_credential_info()  # Update target info
                return result
            else:
                result['message'] = f"Sync from {source_dir} failed"

    if not result['source']:
        result['message'] = "No valid credential source found"

    return result


def main():
    parser = argparse.ArgumentParser(description='Refresh Claude Code credentials')
    parser.add_argument('--force', action='store_true', help='Force refresh even if target is newer')
    parser.add_argument('--check', action='store_true', help='Only check status, do not sync')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    if args.check:
        # Just check and report status
        status = {
            'sources': {},
            'target': get_target_credential_info()
        }
        for source_dir in SOURCE_DIRS:
            status['sources'][str(source_dir)] = check_source_credentials(source_dir)

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("Credential Status:")
            print(f"  Target ({TARGET_DIR}): {status['target']}")
            for source, info in status['sources'].items():
                print(f"  Source ({source}): {info}")
        return 0

    # Perform refresh
    result = refresh_credentials(force=args.force)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result['message']}")

    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
