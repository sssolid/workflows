# ===== src/services/filemaker_service.py =====
import logging
from typing import Dict, Optional
from pathlib import Path

from ..config.settings import settings
from ..models.metadata_models import PartMetadata
from ..utils.error_handling import handle_processing_errors

logger = logging.getLogger(__name__)


class FileMakerService:
    """
    Service for FileMaker database integration.

    Handles:
    - Database connection management
    - Part metadata retrieval
    - Connection fallback strategies
    """

    def __init__(self):
        self.connection = None
        self.metadata_cache: Dict[str, PartMetadata] = {}
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize database connection with fallback strategies."""
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
                self.connection = None

    def _try_odbc_connection(self) -> None:
        """Try ODBC connection."""
        import pyodbc

        dsn_path = settings.database.filemaker_dsn_path
        if dsn_path.exists():
            with open(dsn_path, 'r') as f:
                dsn = f.read().strip()

            self.connection = pyodbc.connect(dsn, timeout=10)
            self.connection.setencoding(encoding="utf8")
            logger.info("FileMaker ODBC connection successful")
        else:
            raise Exception(f"DSN file not found: {dsn_path}")

    def _try_jdbc_connection(self) -> None:
        """Try JDBC connection as fallback."""
        import jpype
        import jaydebeapi

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
        part_key = part_number.upper()
        if part_key in self.metadata_cache:
            return self.metadata_cache[part_key]

        try:
            cursor = self.connection.cursor()

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
                return None

            # Build keywords
            keywords_parts = [
                row[5] or "",  # SDC_KeySearchWords
                row[6] or "",  # SDC_SlangDescription
                row[1] or ""  # PartBrand
            ]
            keywords = ", ".join(part for part in keywords_parts if part)

            metadata = PartMetadata(
                part_number=row[0],
                part_brand=row[1] or "Crown Automotive",
                title=row[2] or row[3] or "",
                description=row[4] or "",
                keywords=keywords
            )

            # Cache the result
            self.metadata_cache[part_key] = metadata

            logger.debug(f"Retrieved metadata for part: {part_number}")
            return metadata

        except Exception as e:
            logger.error(f"Error querying part metadata for {part_number}: {e}")
            return None
        finally:
            if 'cursor' in locals():
                cursor.close()

    def get_bulk_metadata(self) -> Dict[str, PartMetadata]:
        """
        Get metadata for all active parts (for bulk operations).

        Returns:
            Dictionary mapping part numbers to metadata
        """
        if not self.connection:
            logger.warning("No database connection available for bulk query")
            return {}

        try:
            cursor = self.connection.cursor()

            query = """
                    SELECT m.AS400_NumberStripped AS PartNumber,
                           m.PartBrand,
                           m.PartDescription,
                           m.SDC_DescriptionShort,
                           m.SDC_PartDescriptionExtended,
                           m.SDC_KeySearchWords,
                           m.SDC_SlangDescription
                    FROM Master AS m
                    WHERE m.ToggleActive = 'Yes' \
                    """

            cursor.execute(query)
            rows = cursor.fetchall()

            bulk_metadata = {}

            for row in rows:
                if not row[0]:  # Skip if no part number
                    continue

                part_number = row[0].upper()

                # Build keywords
                keywords_parts = [row[5] or "", row[6] or "", row[1] or ""]
                keywords = ", ".join(part for part in keywords_parts if part)

                metadata = PartMetadata(
                    part_number=part_number,
                    part_brand=row[1] or "Crown Automotive",
                    title=row[2] or row[3] or "",
                    description=row[4] or "",
                    keywords=keywords
                )

                bulk_metadata[part_number] = metadata

            # Update cache
            self.metadata_cache.update(bulk_metadata)

            logger.info(f"Loaded metadata for {len(bulk_metadata)} parts")
            return bulk_metadata

        except Exception as e:
            logger.error(f"Error in bulk metadata query: {e}")
            return {}
        finally:
            if 'cursor' in locals():
                cursor.close()

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