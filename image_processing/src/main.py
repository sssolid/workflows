# ===== src/main.py =====
"""
Crown Automotive Image Processing System
Main entry point and CLI interface
"""

import argparse
import logging
import sys
from pathlib import Path

from .config.settings import settings
from .utils.logging_config import setup_logging
from .services.file_monitor_service import FileMonitorService
from .workflows.file_monitoring import FileMonitoringWorkflow
from .web.app import run_web_server


def setup_directories():
    """Ensure all required directories exist."""
    directories = [
        settings.processing.input_dir,
        settings.processing.processing_dir,
        settings.processing.production_dir,
        settings.processing.rejected_dir,
        settings.processing.metadata_dir,
        settings.processing.logs_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def cmd_monitor(args):
    """Run file monitoring."""
    setup_directories()

    if args.workflow:
        # Run n8n workflow mode
        workflow = FileMonitoringWorkflow()

        if args.command == "scan":
            result = workflow.scan_for_new_files()
        elif args.command == "processable":
            result = workflow.get_files_needing_processing()
        else:
            result = {"error": f"Unknown command: {args.command}"}

        print(json.dumps(result, indent=2))
    else:
        # Run standalone monitoring
        monitor = FileMonitorService()

        if args.once:
            files = monitor.discover_new_files()
            print(f"Discovered {len(files)} new files")
            for file_obj in files:
                print(f"  - {file_obj.metadata.filename} ({file_obj.metadata.file_id})")
        else:
            print("Starting continuous file monitoring...")
            # Implement continuous monitoring here


def cmd_web(args):
    """Run web server."""
    setup_directories()
    run_web_server()


def cmd_status(args):
    """Show system status."""
    setup_directories()

    monitor = FileMonitorService()
    files_by_status = {}

    for status in FileStatus:
        files = monitor.get_files_by_status(status)
        files_by_status[status.value] = len(files)

    print("Crown Automotive Image Processing System Status")
    print("=" * 50)
    print(f"Configuration: {settings.environment}")
    print(f"Input Directory: {settings.processing.input_dir}")
    print(f"Production Directory: {settings.processing.production_dir}")
    print()
    print("File Status Summary:")
    for status, count in files_by_status.items():
        print(f"  {status.title()}: {count}")
    print()
    print(f"Total Tracked Files: {sum(files_by_status.values())}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Crown Automotive Image Processing System'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=settings.log_level,
        help='Set logging level'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='File monitoring')
    monitor_parser.add_argument('--once', action='store_true', help='Run once and exit')
    monitor_parser.add_argument('--workflow', action='store_true', help='Run in n8n workflow mode')
    monitor_parser.add_argument('command', nargs='?', choices=['scan', 'processable'], help='Workflow command')
    monitor_parser.set_defaults(func=cmd_monitor)

    # Web server command
    web_parser = subparsers.add_parser('web', help='Run web server')
    web_parser.set_defaults(func=cmd_web)

    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    if hasattr(args, 'func'):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\nShutdown requested by user")
            sys.exit(0)
        except Exception as e:
            logging.error(f"Command failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()