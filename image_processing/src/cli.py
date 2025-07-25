# ===== src/cli.py =====
"""
Command Line Interface for Crown Automotive Image Processing System
Provides CLI tools for system administration and maintenance
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from .config.settings import settings
from .services.file_monitor_service import FileMonitorService
from .services.background_removal_service import BackgroundRemovalService
from .services.image_processing_service import ImageProcessingService
from .services.filemaker_service import FileMakerService
from .models.file_models import FileStatus
from .models.processing_models import BackgroundRemovalRequest, ProcessingModel
from .utils.logging_config import setup_logging


def cmd_status(args) -> None:
    """Show system status."""
    setup_logging(args.log_level)

    print("Crown Automotive Image Processing System Status")
    print("=" * 50)

    # File monitor status
    monitor = FileMonitorService()
    files_by_status = {}

    for status in FileStatus:
        files = monitor.get_files_by_status(status)
        files_by_status[status.value] = len(files)

    print(f"Environment: {settings.environment}")
    print(f"Input Directory: {settings.processing.input_dir}")
    print(f"Production Directory: {settings.processing.production_dir}")
    print()
    print("File Status Summary:")
    for status, count in files_by_status.items():
        print(f"  {status.replace('_', ' ').title()}: {count}")
    print()
    print(f"Total Tracked Files: {sum(files_by_status.values())}")

    # Database status
    try:
        filemaker = FileMakerService()
        if filemaker.test_connection():
            print("✅ Database: Connected")
        else:
            print("❌ Database: Connection failed")
    except Exception as e:
        print(f"❌ Database: Error - {e}")


def cmd_scan(args) -> None:
    """Scan for new files."""
    setup_logging(args.log_level)

    monitor = FileMonitorService()

    if args.recover:
        print("🔄 Scanning for incomplete processing...")
        recovered = monitor.scan_and_recover_incomplete()
        print(f"Recovered {len(recovered)} incomplete files")

    if args.processable:
        print("🔍 Scanning for processable files...")
        processable = monitor.get_files_needing_processing()
        print(f"Found {len(processable)} files needing processing")

        for file_obj in processable[:10]:  # Show first 10
            print(f"  - {file_obj.metadata.filename} ({file_obj.metadata.status})")
    else:
        print("🔍 Scanning for new files...")
        new_files = monitor.discover_new_files()
        print(f"Discovered {len(new_files)} new files")

        for file_obj in new_files:
            print(f"  - {file_obj.metadata.filename} ({file_obj.metadata.size_mb} MB)")


def cmd_process(args) -> None:
    """Process a specific file."""
    setup_logging(args.log_level)

    monitor = FileMonitorService()
    file_obj = monitor.get_file_by_id(args.file_id)

    if not file_obj:
        print(f"❌ File not found: {args.file_id}")
        sys.exit(1)

    print(f"🎯 Processing file: {file_obj.metadata.filename}")

    if args.background_removal:
        bg_service = BackgroundRemovalService()
        request = BackgroundRemovalRequest(
            file_id=args.file_id,
            model=ProcessingModel(args.model),
            enhance_input=not args.no_enhance,
            post_process=not args.no_post_process
        )

        print(f"🤖 Using model: {args.model}")
        result = bg_service.remove_background(file_obj, request)

        if result.success:
            print(f"✅ Background removal completed in {result.processing_time_seconds:.1f}s")
            print(f"📊 Quality score: {result.quality_score}%")
            print(f"📁 Output: {result.output_path}")
        else:
            print(f"❌ Background removal failed: {result.error_message}")
            sys.exit(1)


def cmd_list(args) -> None:
    """List files by status."""
    setup_logging(args.log_level)

    monitor = FileMonitorService()

    if args.status:
        try:
            status = FileStatus(args.status)
            files = monitor.get_files_by_status(status)
            print(f"Files with status '{status.value}': {len(files)}")

            for file_obj in files[:args.limit]:
                print(f"  {file_obj.metadata.file_id}: {file_obj.metadata.filename}")

        except ValueError:
            print(f"❌ Invalid status: {args.status}")
            print(f"Valid statuses: {[s.value for s in FileStatus]}")
            sys.exit(1)
    else:
        # Show summary
        for status in FileStatus:
            files = monitor.get_files_by_status(status)
            print(f"{status.value.replace('_', ' ').title()}: {len(files)}")


def cmd_reset(args) -> None:
    """Reset system state."""
    setup_logging(args.log_level)

    if not args.confirm:
        print("⚠️  This will reset all file tracking state!")
        print("Use --confirm to proceed")
        sys.exit(1)

    monitor = FileMonitorService()

    # Clear tracked files
    monitor._tracked_files = {}

    # Remove state file
    if monitor.state_file.exists():
        monitor.state_file.unlink()

    print("✅ System state reset successfully")


def cmd_test(args) -> None:
    """Test system components."""
    setup_logging(args.log_level)

    print("🧪 Testing system components...")

    # Test database connection
    try:
        filemaker = FileMakerService()
        if filemaker.test_connection():
            print("✅ Database connection: OK")
        else:
            print("❌ Database connection: Failed")
    except Exception as e:
        print(f"❌ Database connection: Error - {e}")

    # Test file monitor
    try:
        monitor = FileMonitorService()
        print("✅ File monitor: OK")
    except Exception as e:
        print(f"❌ File monitor: Error - {e}")

    # Test background removal service
    try:
        bg_service = BackgroundRemovalService()
        print("✅ Background removal service: OK")
    except Exception as e:
        print(f"❌ Background removal service: Error - {e}")

    # Test image processing service
    try:
        img_service = ImageProcessingService()
        print("✅ Image processing service: OK")
    except Exception as e:
        print(f"❌ Image processing service: Error - {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Crown Automotive Image Processing System CLI'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    status_parser.set_defaults(func=cmd_status)

    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan for files')
    scan_parser.add_argument('--recover', action='store_true', help='Recover incomplete files')
    scan_parser.add_argument('--processable', action='store_true', help='Show processable files')
    scan_parser.set_defaults(func=cmd_scan)

    # Process command
    process_parser = subparsers.add_parser('process', help='Process a specific file')
    process_parser.add_argument('file_id', help='File ID to process')
    process_parser.add_argument('--background-removal', action='store_true', help='Perform background removal')
    process_parser.add_argument('--model', default='isnet-general-use', help='ML model to use')
    process_parser.add_argument('--no-enhance', action='store_true', help='Skip input enhancement')
    process_parser.add_argument('--no-post-process', action='store_true', help='Skip post-processing')
    process_parser.set_defaults(func=cmd_process)

    # List command
    list_parser = subparsers.add_parser('list', help='List files')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--limit', type=int, default=20, help='Limit number of results')
    list_parser.set_defaults(func=cmd_list)

    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset system state')
    reset_parser.add_argument('--confirm', action='store_true', help='Confirm reset operation')
    reset_parser.set_defaults(func=cmd_reset)

    # Test command
    test_parser = subparsers.add_parser('test', help='Test system components')
    test_parser.set_defaults(func=cmd_test)

    args = parser.parse_args()

    if hasattr(args, 'func'):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n⏹️ Operation cancelled by user")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Command failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()