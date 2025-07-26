# ===== src/services/filemaker_service.py =====
import logging
import sqlite3
import socket
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..config.settings import settings
from ..models.metadata_models import PartMetadata
from ..utils.error_handling import handle_processing_errors

logger = logging.getLogger(__name__)


class FileMakerService:
    """
    Service for FileMaker database integration with development mock support.

    Handles:
    - Database connection management (production FileMaker or development SQLite)
    - Part metadata retrieval
    - Interchange table queries
    - Connection fallback strategies (ODBC -> JDBC -> Mock)
    """

    def __init__(self):
        self.connection = None
        self.metadata_cache: Dict[str, PartMetadata] = {}
        self.is_mock_mode = settings.environment == "development"
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize database connection with fallback strategies."""
        if self.is_mock_mode:
            try:
                self._try_mock_connection()
                return
            except Exception as e:
                logger.warning(f"Mock connection failed: {e}")

        # Production mode fallbacks
        try:
            # Try ODBC first
            self._try_odbc_connection()
        except Exception as e:
            logger.warning(f"ODBC connection failed: {e}")
            try:
                # Fallback to JDBC
                self._try_jdbc_connection()
            except Exception as e2:
                logger.error(f"All database connections failed. JDBC: {e2}")
                if self.is_mock_mode:
                    logger.info("Falling back to mock database for development")
                    self._try_mock_connection()
                else:
                    self.connection = None

    def _try_mock_connection(self) -> None:
        """Try mock database connection for development."""
        mock_db_path = "/app/data/mock_crown.db"

        # If running in container, check if mock database exists
        if Path(mock_db_path).exists():
            self.connection = sqlite3.connect(mock_db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Allow column access by name
            logger.info("Connected to mock SQLite database for development")
        else:
            # Create in-memory database with sample data
            self.connection = sqlite3.connect(":memory:", check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self._create_mock_tables()
            logger.info("Created in-memory mock database for development")

    def _create_mock_tables(self) -> None:
        """Create mock tables with sample data."""
        cursor = self.connection.cursor()

        # Create Master table
        cursor.execute('''
                       CREATE TABLE Master
                       (
                           AS400_NumberStripped        TEXT PRIMARY KEY,
                           PartBrand                   TEXT,
                           PartDescription             TEXT,
                           SDC_DescriptionShort        TEXT,
                           SDC_PartDescriptionExtended TEXT,
                           SDC_KeySearchWords          TEXT,
                           SDC_SlangDescription        TEXT,
                           ToggleActive                TEXT DEFAULT 'Yes'
                       )
                       ''')

        # Create interchange table
        cursor.execute('''
                       CREATE TABLE as400_ininter
                       (
                           ICPCD TEXT,
                           ICPNO TEXT,
                           IPTNO TEXT
                       )
                       ''')

        # Insert sample data
        sample_parts = [
            ('J1234567', 'Crown Automotive', 'Fuel Tank Skid Plate', 'Skid Plate - Fuel Tank',
             'Heavy duty steel construction fuel tank protection skid plate',
             'fuel tank, skid plate, protection, steel', 'tank guard'),
            ('A5551234', 'Crown Automotive', 'Air Filter', 'Air Filter Element',
             'High flow air filter element for improved performance',
             'air filter, element, performance', 'air cleaner'),
            ('12345', 'Crown Automotive', 'Oil Pan', 'Engine Oil Pan',
             'Cast aluminum oil pan with drain plug',
             'oil pan, engine, aluminum, drain', 'oil sump'),
            ('67890', 'Crown Automotive', 'Water Pump', 'Water Pump Assembly',
             'Complete water pump assembly with gasket',
             'water pump, cooling, gasket', 'coolant pump'),
            ('J9876543', 'Crown Automotive', 'Transmission Mount', 'Transmission Mount Bracket',
             'Heavy duty transmission mount with rubber isolator',
             'transmission, mount, bracket, rubber', 'trans mount'),
            ('A1111111', 'Crown Automotive', 'Brake Pad Set', 'Front Brake Pad Set',
             'Ceramic brake pads for front axle',
             'brake pads, ceramic, front', 'brake shoes'),
            ('B2222222', 'Crown Automotive', 'Shock Absorber', 'Rear Shock Absorber',
             'Gas charged rear shock absorber',
             'shock absorber, rear, gas', 'damper'),
            ('C3333333', 'Crown Automotive', 'CV Joint', 'Constant Velocity Joint',
             'Rebuilt CV joint with boot and grease',
             'cv joint, constant velocity, boot', 'drive joint'),
        ]

        cursor.executemany('''
                           INSERT INTO Master
                           (AS400_NumberStripped, PartBrand, PartDescription, SDC_DescriptionShort,
                            SDC_PartDescriptionExtended, SDC_KeySearchWords, SDC_SlangDescription)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ''', sample_parts)

        # Insert interchange data
        sample_interchanges = [
            ('IC', 'OLD12345', '12345'),
            ('IC', 'LEGACY67890', '67890'),
            ('IC', 'J1234567A', 'J1234567'),
            ('IC', '12345_OLD', '12345'),
            ('IC', 'A555OLD', 'A5551234'),
        ]

        cursor.executemany('''
                           INSERT INTO as400_ininter (ICPCD, ICPNO, IPTNO)
                           VALUES (?, ?, ?)
                           ''', sample_interchanges)

        self.connection.commit()

    def _try_odbc_connection(self) -> None:
        """Try ODBC connection."""
        try:
            import pyodbc
        except ImportError:
            raise Exception("pyodbc not available")

        dsn_path = settings.database.filemaker_dsn_path
        if not dsn_path.exists():
            raise Exception(f"DSN file not found: {dsn_path}")

        with open(dsn_path, 'r') as f:
            dsn = f.read().strip()

        self.connection = pyodbc.connect(dsn, timeout=10)
        self.connection.setencoding(encoding="utf8")
        logger.info("FileMaker ODBC connection successful")

    def _try_jdbc_connection(self) -> None:
        """Try JDBC connection as fallback."""
        try:
            import jpype
            import jaydebeapi
        except ImportError:
            raise Exception("JDBC dependencies not available")

        # Construct JDBC URL
        jdbc_url = (
            f"jdbc:filemaker://{settings.database.filemaker_server}:"
            f"{settings.database.filemaker_port}/{settings.database.filemaker_database}"
        )

        # Find JDBC driver
        jar_path = self._find_jdbc_driver()

        # Start JVM if needed
        if not jpype.isJVMStarted():
            jvm_path = jpype.getDefaultJVMPath()
            jpype.startJVM(jvm_path, f"-Djava.class.path={jar_path}")

        # Create connection
        self.connection = jaydebeapi.connect(
            "com.filemaker.jdbc.Driver",
            jdbc_url,
            [settings.database.filemaker_username, settings.database.filemaker_password]
        )

        self.connection.jconn.setReadOnly(True)
        logger.info("FileMaker JDBC connection successful")

    def _find_jdbc_driver(self) -> str:
        """Find the FileMaker JDBC driver JAR file."""
        jar_locations = [
            Path("/config/fmjdbc.jar"),
            Path("/assets/fmjdbc.jar"),
            Path(__file__).parent.parent / "config" / "fmjdbc.jar"
        ]

        for jar_path in jar_locations:
            if jar_path.exists():
                return str(jar_path.resolve())

        raise Exception("fmjdbc.jar not found. Please place it in the config directory.")

    @handle_processing_errors("database_query")
    def get_part_metadata(self, part_number: str) -> Optional[PartMetadata]:
        """
        Get metadata for a specific part number.

        Args:
            part_number: Part number to look up

        Returns:
            PartMetadata if found, None otherwise
        """
        if not self.connection:
            logger.warning("No database connection available")
            return None

        # Check cache first
        part_key = part_number.upper().strip()
        if part_key in self.metadata_cache:
            return self.metadata_cache[part_key]

        try:
            cursor = self.connection.cursor()

            if self.is_mock_mode and hasattr(self.connection, 'row_factory'):
                # SQLite query
                query = """
                        SELECT AS400_NumberStripped, \
                               PartBrand, \
                               PartDescription,
                               SDC_DescriptionShort, \
                               SDC_PartDescriptionExtended,
                               SDC_KeySearchWords, \
                               SDC_SlangDescription
                        FROM Master
                        WHERE AS400_NumberStripped = ? \
                          AND ToggleActive = 'Yes' \
                        """
            else:
                # FileMaker query
                query = """
                        SELECT m.AS400_NumberStripped AS PartNumber,
                               m.PartBrand,
                               m.PartDescription,
                               m.SDC_DescriptionShort,
                               m.SDC_PartDescriptionExtended,
                               m.SDC_KeySearchWords,
                               m.SDC_SlangDescription
                        FROM Master AS m
                        WHERE m.AS400_NumberStripped = ?
                          AND m.ToggleActive = 'Yes' \
                        """

            cursor.execute(query, (part_key,))
            row = cursor.fetchone()

            if not row:
                logger.debug(f"No metadata found for part: {part_number}")
                cursor.close()
                return None

            # Handle both SQLite Row and regular tuple results
            if hasattr(row, '_asdict'):
                # SQLite Row object
                row_dict = dict(row)
                part_num = row_dict.get('AS400_NumberStripped')
                brand = row_dict.get('PartBrand')
                desc = row_dict.get('PartDescription')
                short_desc = row_dict.get('SDC_DescriptionShort')
                ext_desc = row_dict.get('SDC_PartDescriptionExtended')
                keywords = row_dict.get('SDC_KeySearchWords')
                slang = row_dict.get('SDC_SlangDescription')
            else:
                # Regular tuple
                part_num = row[0]
                brand = row[1] if len(row) > 1 else None
                desc = row[2] if len(row) > 2 else None
                short_desc = row[3] if len(row) > 3 else None
                ext_desc = row[4] if len(row) > 4 else None
                keywords = row[5] if len(row) > 5 else None
                slang = row[6] if len(row) > 6 else None

            # Build keywords
            keywords_parts = [
                keywords or "",
                slang or "",
                brand or ""
            ]
            combined_keywords = ", ".join(part for part in keywords_parts if part)

            metadata = PartMetadata(
                part_number=part_num,
                part_brand=brand or "Crown Automotive",
                title=desc or short_desc or "",
                description=ext_desc or "",
                keywords=combined_keywords
            )

            # Cache the result
            self.metadata_cache[part_key] = metadata
            cursor.close()

            logger.debug(f"Retrieved metadata for part: {part_number}")
            return metadata

        except Exception as e:
            logger.error(f"Error querying part metadata for {part_number}: {e}")
            return None

    @handle_processing_errors("interchange_query")
    def get_interchange_mappings(self) -> List[Tuple[str, str, str]]:
        """
        Get all interchange mappings from the database.

        Returns:
            List of tuples (interchange_code, old_part, new_part)
        """
        if not self.connection:
            logger.warning("No database connection available for interchange query")
            return []

        try:
            cursor = self.connection.cursor()

            if self.is_mock_mode and hasattr(self.connection, 'row_factory'):
                # SQLite query
                query = '''
                        SELECT ICPCD, ICPNO, IPTNO
                        FROM as400_ininter
                        ORDER BY IPTNO, ICPCD \
                        '''
            else:
                # FileMaker query
                query = '''
                        SELECT "i"."ICPCD", "i"."ICPNO", "i"."IPTNO"
                        FROM "as400_ininter" AS "i"
                        ORDER BY "i"."IPTNO", "i"."ICPCD" \
                        '''

            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()

            mappings = []
            for row in rows:
                if len(row) >= 3 and row[1] and row[2]:  # ICPNO and IPTNO not null
                    code = str(row[0]).strip() if row[0] else ""
                    old_part = str(row[1]).strip().upper()
                    new_part = str(row[2]).strip().upper()
                    mappings.append((code, old_part, new_part))

            logger.info(f"Retrieved {len(mappings)} interchange mappings")
            return mappings

        except Exception as e:
            logger.error(f"Error querying interchange mappings: {e}")
            return []

    @handle_processing_errors("database_search")
    def search_parts(self, search_term: str, limit: int = 10) -> List[PartMetadata]:
        """
        Search for parts by partial match.

        Args:
            search_term: Term to search for
            limit: Maximum number of results

        Returns:
            List of matching PartMetadata
        """
        if not self.connection or len(search_term) < 2:
            return []

        try:
            cursor = self.connection.cursor()
            search_pattern = f"{search_term.upper()}%"

            if self.is_mock_mode and hasattr(self.connection, 'row_factory'):
                # SQLite query
                query = """
                        SELECT AS400_NumberStripped, \
                               PartBrand, \
                               PartDescription,
                               SDC_DescriptionShort, \
                               SDC_PartDescriptionExtended,
                               SDC_KeySearchWords, \
                               SDC_SlangDescription
                        FROM Master
                        WHERE AS400_NumberStripped LIKE ? \
                          AND ToggleActive = 'Yes'
                        ORDER BY AS400_NumberStripped LIMIT ? \
                        """
            else:
                # FileMaker query
                query = """
                        SELECT m.AS400_NumberStripped AS PartNumber,
                               m.PartBrand, \
                               m.PartDescription,
                               m.SDC_DescriptionShort, \
                               m.SDC_PartDescriptionExtended,
                               m.SDC_KeySearchWords, \
                               m.SDC_SlangDescription
                        FROM Master AS m
                        WHERE m.AS400_NumberStripped LIKE ?
                          AND m.ToggleActive = 'Yes'
                        ORDER BY m.AS400_NumberStripped LIMIT ? \
                        """

            cursor.execute(query, (search_pattern, limit))
            rows = cursor.fetchall()
            cursor.close()

            results = []
            for row in rows:
                if row[0]:  # Part number not null
                    keywords_parts = [row[5] or "", row[6] or "", row[1] or ""]
                    keywords = ", ".join(part for part in keywords_parts if part)

                    metadata = PartMetadata(
                        part_number=row[0],
                        part_brand=row[1] or "Crown Automotive",
                        title=row[2] or row[3] or "",
                        description=row[4] or "",
                        keywords=keywords
                    )
                    results.append(metadata)

            return results

        except Exception as e:
            logger.error(f"Error searching parts for '{search_term}': {e}")
            return []

    def validate_part_number(self, part_number: str) -> bool:
        """
        Validate that a part number exists and is active.

        Args:
            part_number: Part number to validate

        Returns:
            True if part exists and is active
        """
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()

            if self.is_mock_mode and hasattr(self.connection, 'row_factory'):
                query = '''
                        SELECT COUNT(*) \
                        FROM Master
                        WHERE AS400_NumberStripped = ? \
                          AND ToggleActive = 'Yes' \
                        '''
            else:
                query = '''
                        SELECT COUNT(*) \
                        FROM Master
                        WHERE AS400_NumberStripped = ? \
                          AND ToggleActive = 'Yes' \
                        '''

            cursor.execute(query, (part_number.upper().strip(),))
            result = cursor.fetchone()
            cursor.close()

            return result and result[0] > 0

        except Exception as e:
            logger.error(f"Error validating part number {part_number}: {e}")
            return False

    def test_connection(self) -> bool:
        """Test if database connection is working."""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM Master WHERE ToggleActive = 'Yes'")
            result = cursor.fetchone()
            cursor.close()

            return result and result[0] > 0
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def close_connection(self) -> None:
        """Close database connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self.connection = None