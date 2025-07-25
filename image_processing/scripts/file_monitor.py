#!/usr/bin/env python3
"""
File Monitor Script for n8n Image Processing Workflow
Watches the input directory for new image files and reports changes
"""

import os
import json
import time
import argparse
import logging
from pathlib import Path
from typing import Set, List, Dict, Any
import hashlib
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/file_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WATCH_DIR = '/data/input'
STATE_FILE = '/data/metadata/file_monitor_state.json'
SUPPORTED_EXTENSIONS = {'.psd', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}
MIN_FILE_SIZE = 1024  # 1KB minimum file size
SCAN_INTERVAL = 30  # seconds


class FileMonitor:
    def __init__(self, watch_dir: str, state_file: str):
        self.watch_dir = Path(watch_dir)
        self.state_file = Path(state_file)
        self.previous_files: Set[str] = set()

        # Ensure directories exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load previous state
        self.load_state()

    def load_state(self) -> None:
        """Load the previous file state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.previous_files = set(data.get('files', []))
                    logger.info(f"Loaded {len(self.previous_files)} files from previous state")
            else:
                logger.info("No previous state found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading state file: {e}")
            self.previous_files = set()

    def save_state(self, current_files: Set[str]) -> None:
        """Save the current file state to disk"""
        try:
            state_data = {
                'files': list(current_files),
                'last_scan': datetime.now().isoformat(),
                'scan_count': getattr(self, 'scan_count', 0) + 1
            }

            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)

            self.previous_files = current_files.copy()

        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get detailed information about a file"""
        try:
            stat = file_path.stat()

            # Calculate file hash for duplicate detection
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            return {
                'path': str(file_path),
                'name': file_path.name,
                'stem': file_path.stem,
                'suffix': file_path.suffix.lower(),
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'hash': file_hash,
                'is_psd': file_path.suffix.lower() == '.psd'
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None

    def is_valid_image_file(self, file_path: Path) -> bool:
        """Check if a file is a valid image file for processing"""
        try:
            # Check extension
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                return False

            # FIXED: Ignore processed files to prevent loops
            if '_bg_removed' in file_path.name:
                logger.debug(f"Ignoring processed file: {file_path.name}")
                return False

            # Ignore thumbnail or temp files
            if file_path.name.startswith('.') or file_path.name.startswith('tmp'):
                return False

            # Check if file is complete (not being written)
            initial_size = file_path.stat().st_size
            time.sleep(1)
            if file_path.stat().st_size != initial_size:
                logger.info(f"File {file_path.name} still being written, skipping")
                return False

            # Check minimum file size
            if initial_size < MIN_FILE_SIZE:
                logger.warning(f"File {file_path.name} too small ({initial_size} bytes)")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}")
            return False

    def scan_for_new_files(self) -> List[Dict[str, Any]]:
        """Scan directory for new image files"""
        try:
            current_files = set()
            new_file_info = []

            # Scan directory
            for file_path in self.watch_dir.iterdir():
                if file_path.is_file() and self.is_valid_image_file(file_path):
                    file_key = f"{file_path.name}_{file_path.stat().st_size}"
                    current_files.add(file_key)

                    # Check if this is a new file
                    if file_key not in self.previous_files:
                        file_info = self.get_file_info(file_path)
                        if file_info:
                            new_file_info.append(file_info)
                            logger.info(f"New file detected: {file_path.name} ({file_info['size_mb']} MB)")

            # Save current state
            self.save_state(current_files)

            return new_file_info

        except Exception as e:
            logger.error(f"Error scanning directory: {e}")
            return []

    def run_single_scan(self) -> Dict[str, Any]:
        """Run a single scan and return results for n8n"""
        new_files = self.scan_for_new_files()

        result = {
            'timestamp': datetime.now().isoformat(),
            'scan_directory': str(self.watch_dir),
            'new_files_count': len(new_files),
            'new_files': new_files,
            'total_monitored': len(self.previous_files)
        }

        return result

    def scan_for_processable_files(self) -> List[Dict[str, Any]]:
        """Scan for files that need processing (not just new files)"""
        try:
            processable_files = []

            # Scan input directory
            for file_path in self.watch_dir.iterdir():
                if file_path.is_file() and self.is_valid_image_file(file_path):

                    # Check if file needs processing
                    if self.needs_processing(file_path):
                        file_info = self.get_file_info(file_path)
                        if file_info:
                            processable_files.append(file_info)
                            logger.info(f"File needs processing: {file_path.name}")

            return processable_files

        except Exception as e:
            logger.error(f"Error scanning for processable files: {e}")
            return []

    def needs_processing(self, file_path: Path) -> bool:
        """Check if a file needs processing based on its current state"""
        try:
            base_name = file_path.stem

            # Check if already fully processed (has production files)
            production_indicator = Path(f"/data/production/1000x1000_72dpi_jpeg/{base_name}.jpg")
            if production_indicator.exists():
                logger.debug(f"File {file_path.name} already fully processed")
                return False

            # Check if it's a PSD that needs processing
            if file_path.suffix.lower() == '.psd':
                return True

            # Check if it needs background removal
            bg_removed_file = Path(f"/data/processing/bg_removed/{base_name}_bg_removed.png")
            if not bg_removed_file.exists():
                return True

            # Check if background removal is done but needs approval
            # (file exists in bg_removed but no decision made yet)
            decision_files = list(Path("/data/decisions").glob(f"{file_path.name}_*.json"))
            if not decision_files:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking if {file_path} needs processing: {e}")
            return True  # Default to needs processing if unsure

    def run_smart_scan(self) -> Dict[str, Any]:
        """Run a smart scan that finds files needing processing"""
        processable_files = self.scan_for_processable_files()

        result = {
            'timestamp': datetime.now().isoformat(),
            'scan_directory': str(self.watch_dir),
            'processable_files_count': len(processable_files),
            'new_files': processable_files,  # Use same format for compatibility
            'total_monitored': len(processable_files),
            'scan_type': 'smart_scan'
        }

        return result

    def run_daemon(self) -> None:
        """Run as a daemon, continuously monitoring for new files"""
        logger.info(f"Starting file monitor daemon, watching: {self.watch_dir}")
        logger.info(f"Scan interval: {SCAN_INTERVAL} seconds")

        scan_count = 0

        try:
            while True:
                scan_count += 1
                logger.debug(f"Scan #{scan_count}")

                new_files = self.scan_for_new_files()

                if new_files:
                    logger.info(f"Found {len(new_files)} new files")

                    # Here you could trigger n8n webhook or write to a trigger file
                    # For now, we'll just log the detection

                else:
                    logger.debug("No new files detected")

                time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            logger.info("File monitor daemon stopped by user")
        except Exception as e:
            logger.error(f"File monitor daemon error: {e}")
            raise


def main():
    global SCAN_INTERVAL

    """Main entry point"""
    parser = argparse.ArgumentParser(description='File Monitor for Image Processing')
    parser.add_argument('--daemon', action='store_true',
                        help='Run as daemon (continuous monitoring)')
    parser.add_argument('--watch-dir', default=WATCH_DIR,
                        help='Directory to watch for new files')
    parser.add_argument('--state-file', default=STATE_FILE,
                        help='File to store monitoring state')
    parser.add_argument('--scan-interval', type=int, default=SCAN_INTERVAL,
                        help='Scan interval in seconds (daemon mode)')

    args = parser.parse_args()

    # Update globals with command line args
    SCAN_INTERVAL = args.scan_interval

    monitor = FileMonitor(args.watch_dir, args.state_file)

    if args.daemon:
        monitor.run_daemon()
    else:
        # Single scan mode (for n8n)
        result = monitor.run_smart_scan()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()