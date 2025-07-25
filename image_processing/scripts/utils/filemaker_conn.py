#!/usr/bin/env python3
"""
FileMaker Database Connection Utility for Crown Automotive
Updated to match existing Filemaker class implementation
"""

import os
import sys
import csv
import datetime
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

import jpype
import jaydebeapi
import pyodbc

logger = logging.getLogger(__name__)


class Filemaker:
    """FileMaker database connection class matching existing implementation"""

    def __init__(self, dsn: Optional[str] = None):
        """
        Initialize FileMaker connection

        Args:
            dsn: DSN string for pyodbc connection (fallback to JDBC if fails)
        """
        self.dsn = dsn or self._load_dsn()
        self.connection = None
        self.cursor = None

        # JDBC connection parameters (fallback)
        self.jdbc_server = os.getenv('FILEMAKER_SERVER', None)
        self.jdbc_port = int(os.getenv('FILEMAKER_PORT', 2399))
        self.jdbc_database = os.getenv('FILEMAKER_DATABASE', 'CrownMasterDatabase')
        self.jdbc_username = os.getenv('FILEMAKER_USERNAME', None)
        self.jdbc_password = os.getenv('FILEMAKER_PASSWORD', None)

    def _load_dsn(self) -> str:
        """Load DSN string from file"""
        try:
            dsn_path = os.getenv('FILEMAKER_DSN_PATH', '/config/filemaker.dsn')
            if os.path.exists(dsn_path):
                with open(dsn_path, 'r') as f:
                    return f.read().strip()
            else:
                logger.warning(f"DSN file not found: {dsn_path}")
                return ""
        except Exception as e:
            logger.error(f"Error loading DSN file: {e}")
            return ""

    def __enter__(self):
        """Context manager entry"""
        self.cursor = self.get_cursor()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def get_cursor(self):
        """Get database cursor with fallback connection methods"""
        # First try ODBC connection
        if self.dsn:
            try:
                logger.info("Attempting ODBC connection to FileMaker...")
                self.connection = pyodbc.connect(self.dsn, timeout=10)
                self.connection.setencoding(encoding="utf8")
                self.cursor = self.connection.cursor()
                logger.info("ODBC connection successful")
                return self.cursor
            except Exception as e:
                logger.warning(f"FileMaker ODBC connection failed: {e}")

        # Fallback to JDBC connection
        try:
            logger.info("Attempting JDBC connection to FileMaker...")

            # Construct JDBC URL
            jdbc_url = f"jdbc:filemaker://{self.jdbc_server}:{self.jdbc_port}/{self.jdbc_database}"

            # Get JAR file path
            jar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fmjdbc.jar"))
            if not os.path.exists(jar_path):
                # Try alternative locations
                jar_locations = [
                    "/config/fmjdbc.jar",
                    "/assets/fmjdbc.jar",
                    os.path.join(os.path.dirname(__file__), "..", "config", "fmjdbc.jar")
                ]
                for location in jar_locations:
                    if os.path.exists(location):
                        jar_path = os.path.abspath(location)
                        break
                else:
                    raise FileNotFoundError("fmjdbc.jar not found. Please place it in the config directory.")

            # Start JVM if not already started
            if not jpype.isJVMStarted():
                jvm_path = jpype.getDefaultJVMPath()
                jpype.startJVM(jvm_path, f"-Djava.class.path={jar_path}")
                logger.debug("JVM started for FileMaker JDBC connection")

            # Create JDBC connection
            self.connection = jaydebeapi.connect(
                "com.filemaker.jdbc.Driver",
                jdbc_url,
                [self.jdbc_username, self.jdbc_password]
            )

            # Set connection to read-only
            self.connection.jconn.setReadOnly(True)
            self.cursor = self.connection.cursor()

            logger.info("JDBC connection successful")
            return self.cursor

        except Exception as e:
            logger.error(f"FileMaker JDBC connection failed: {e}")
            raise

    def fetch(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute query and return results as list of dictionaries

        Args:
            query: SQL query to execute

        Returns:
            List of dictionaries with column names as keys
        """
        try:
            if not self.cursor:
                raise RuntimeError("No active database connection")

            self.cursor.execute(query)

            # Get headers from cursor description
            headers = [h[0] for h in self.cursor.description]

            # Fetch all rows
            rows = self.cursor.fetchall()

            # Clean up rows (remove null characters)
            cleaned_rows = [
                [r.replace("\x00", "") if isinstance(r, str) else r for r in row]
                for row in rows
            ]

            # Convert to list of dictionaries
            result = [dict(zip(headers, row)) for row in cleaned_rows]

            logger.debug(f"Query executed successfully, returned {len(result)} rows")
            return result

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query}")
            raise

    def get_product_numbers(self, active: bool = True) -> List[str]:
        """
        Get product numbers from Master table

        Args:
            active: If True, only return active products

        Returns:
            List of product numbers
        """
        try:
            if active:
                query = "SELECT AS400_NumberStripped AS number FROM Master WHERE ToggleActive = 'Yes'"
            else:
                query = "SELECT AS400_NumberStripped AS number FROM Master"

            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            # Extract and clean product numbers
            product_numbers = []
            for row in rows:
                if row[0]:  # Check if not None/empty
                    product_numbers.append(row[0].strip())

            logger.info(f"Retrieved {len(product_numbers)} product numbers (active={active})")
            return product_numbers

        except Exception as e:
            logger.error(f"Error getting product numbers: {e}")
            raise

    def get_part_metadata_bulk(self) -> Dict[str, Dict[str, str]]:
        """
        Get metadata for all active parts (optimized for image processing system)

        Returns:
            Dictionary with part numbers as keys and metadata as values
        """
        try:
            query = """
                    SELECT m.AS400_NumberStripped AS PartNumber, \
                           m.PartBrand, \
                           m.PartDescription, \
                           m.SDC_DescriptionShort, \
                           m.SDC_PartDescriptionExtended, \
                           m.SDC_KeySearchWords, \
                           m.SDC_SlangDescription
                    FROM Master AS m
                    WHERE m.ToggleActive = 'Yes' \
                    """

            results = self.fetch(query)

            metadata_lookup = {}
            for row in results:
                part_number = str(row['PartNumber']).upper() if row['PartNumber'] else ""

                if part_number:
                    # Build keywords from available fields
                    keywords_parts = [
                        row.get('SDC_KeySearchWords', ''),
                        row.get('SDC_SlangDescription', ''),
                        row.get('PartBrand', '')
                    ]
                    keywords = ", ".join(str(part) for part in keywords_parts if part)

                    metadata_lookup[part_number] = {
                        "PartNumber": part_number,
                        "PartBrand": str(row.get('PartBrand', '')),
                        "Title": str(row.get('PartDescription', '') or row.get('SDC_DescriptionShort', '')),
                        "Description": str(row.get('SDC_PartDescriptionExtended', '')),
                        "Keywords": keywords,
                        "Author": "Crown Automotive Sales Co., Inc.",
                        "Credit": "Crown Automotive Sales Co., Inc.",
                        "Copyright": "(c) Crown Automotive Sales Co., Inc.",
                    }

            logger.info(f"Loaded metadata for {len(metadata_lookup)} parts")
            return metadata_lookup

        except Exception as e:
            logger.error(f"Error getting bulk part metadata: {e}")
            raise

    def get_part_metadata(self, part_number: str) -> Optional[Dict[str, str]]:
        """
        Get metadata for a specific part number

        Args:
            part_number: The part number to look up

        Returns:
            Dictionary with part metadata or None if not found
        """
        try:
            query = """
                    SELECT m.AS400_NumberStripped AS PartNumber, \
                           m.PartBrand, \
                           m.PartDescription, \
                           m.SDC_DescriptionShort, \
                           m.SDC_PartDescriptionExtended, \
                           m.SDC_KeySearchWords, \
                           m.SDC_SlangDescription
                    FROM Master AS m
                    WHERE m.AS400_NumberStripped = ? \
                      AND m.ToggleActive = 'Yes' \
                    """

            self.cursor.execute(query, (part_number.upper(),))
            rows = self.cursor.fetchall()

            if not rows:
                logger.warning(f"No metadata found for part number: {part_number}")
                return None

            row = rows[0]

            # Build keywords
            keywords_parts = [
                row[5] if row[5] else "",  # SDC_KeySearchWords
                row[6] if row[6] else "",  # SDC_SlangDescription
                row[1] if row[1] else ""  # PartBrand
            ]
            keywords = ", ".join(str(part) for part in keywords_parts if part)

            metadata = {
                "PartNumber": str(row[0]),
                "PartBrand": str(row[1]) if row[1] else "",
                "Title": str(row[2]) or str(row[3]) or "",
                "Description": str(row[4]) or "",
                "Keywords": keywords,
                "Author": "Crown Automotive Sales Co., Inc.",
                "Credit": "Crown Automotive Sales Co., Inc.",
                "Copyright": "(c) Crown Automotive Sales Co., Inc.",
            }

            logger.debug(f"Retrieved metadata for part: {part_number}")
            return metadata

        except Exception as e:
            logger.error(f"Error getting part metadata for {part_number}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test the database connection

        Returns:
            True if connection is working, False otherwise
        """
        try:
            if not self.cursor:
                return False

            # Test with a simple query
            test_query = "SELECT COUNT(*) FROM Master WHERE ToggleActive = 'Yes'"
            self.cursor.execute(test_query)
            result = self.cursor.fetchone()

            if result and result[0] > 0:
                logger.info(f"Database connection test successful. {result[0]} active parts found.")
                return True
            else:
                logger.warning("Database connection test failed - no active parts found")
                return False

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Legacy compatibility class name
class FileMakerConnection(Filemaker):
    """Legacy compatibility wrapper for FileMakerConnection"""
    pass


@contextmanager
def get_filemaker_connection(dsn: Optional[str] = None):
    """
    Context manager for FileMaker connections

    Args:
        dsn: Optional DSN string

    Yields:
        Filemaker instance
    """
    connection = Filemaker(dsn)
    try:
        connection.get_cursor()
        yield connection
    finally:
        if connection.cursor:
            connection.cursor.close()
        if connection.connection:
            connection.connection.close()


def create_sample_dsn_file(dsn_path: str) -> None:
    """
    Create a sample DSN file for configuration

    Args:
        dsn_path: Path where to create the sample DSN file
    """
    sample_dsn = """DRIVER={FileMaker ODBC};
SERVER=192.168.10.216;
DATABASE=CrownMasterDatabase;
UID=dataportal;
PWD=9ee7381fd5;
PORT=2399;"""

    try:
        with open(dsn_path, 'w') as f:
            f.write(sample_dsn)

        logger.info(f"DSN file created at: {dsn_path}")

    except Exception as e:
        logger.error(f"Error creating DSN file: {e}")
        raise


def main():
    """Test the FileMaker connection"""
    import argparse

    parser = argparse.ArgumentParser(description='Test FileMaker database connection')
    parser.add_argument('--dsn', help='DSN string for connection')
    parser.add_argument('--create-dsn', help='Create DSN file at specified path')
    parser.add_argument('--test-part', help='Test retrieving metadata for a specific part number')
    parser.add_argument('--list-products', action='store_true', help='List first 10 product numbers')

    args = parser.parse_args()

    if args.create_dsn:
        create_sample_dsn_file(args.create_dsn)
        return

    try:
        with Filemaker(args.dsn) as fm:
            # Test basic connection
            if fm.test_connection():
                print("✅ FileMaker connection successful")

                # List some products if requested
                if args.list_products:
                    products = fm.get_product_numbers(active=True)
                    print(f"✅ Found {len(products)} active products")
                    print("First 10 products:")
                    for i, product in enumerate(products[:10], 1):
                        print(f"  {i}. {product}")

                # Test part lookup if specified
                if args.test_part:
                    metadata = fm.get_part_metadata(args.test_part)
                    if metadata:
                        print(f"✅ Part metadata retrieved for {args.test_part}:")
                        for key, value in metadata.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"❌ No metadata found for part {args.test_part}")

            else:
                print("❌ FileMaker connection test failed")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()