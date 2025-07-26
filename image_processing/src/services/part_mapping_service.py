# ===== src/services/part_mapping_service.py =====
"""
Part Number Mapping Service - Clean Architecture Implementation
Handles mapping image filenames to correct Crown part numbers using interchange tables
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..config.settings import settings
from ..models.part_mapping_models import InterchangeMapping, PartMappingResult
from ..services.filemaker_service import FileMakerService
from ..utils.error_handling import handle_processing_errors, ProcessingError

logger = logging.getLogger(__name__)


class PartMappingService:
    """
    Service for mapping image filenames to correct part numbers.

    This service handles:
    - Parsing image filenames to extract potential part numbers
    - Looking up interchange mappings in FileMaker database
    - Resolving old part numbers to current part numbers
    - Caching mappings for performance
    """

    def __init__(self):
        self.filemaker = FileMakerService()
        self.interchange_cache: Dict[str, InterchangeMapping] = {}
        self.part_cache: Dict[str, str] = {}
        self._load_interchange_mappings()

    def _load_interchange_mappings(self) -> None:
        """Load interchange mappings from database and cache them."""
        try:
            if not self.filemaker.test_connection():
                logger.warning("No database connection - part mapping will be limited")
                return

            cursor = self.filemaker.connection.cursor()

            # Query to get interchange mappings
            query = '''
                    SELECT "i"."ICPCD", \
                           "i"."ICPNO", \
                           "i"."IPTNO"
                    FROM "as400_ininter" AS "i"
                    ORDER BY "i"."IPTNO", "i"."ICPCD" \
                    '''

            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                if row[1] and row[2]:  # ICPNO and IPTNO not null
                    old_number = str(row[1]).strip().upper()
                    new_number = str(row[2]).strip().upper()
                    code = str(row[0]).strip() if row[0] else ""

                    # Create mapping
                    mapping = InterchangeMapping(
                        old_part_number=old_number,
                        new_part_number=new_number,
                        interchange_code=code
                    )

                    self.interchange_cache[old_number] = mapping

            cursor.close()
            logger.info(f"Loaded {len(self.interchange_cache)} interchange mappings")

        except Exception as e:
            logger.error(f"Error loading interchange mappings: {e}")

    @handle_processing_errors("part_mapping")
    def map_filename_to_part_number(self, filename: str) -> PartMappingResult:
        """
        Map an image filename to the correct part number.

        Args:
            filename: Original filename (e.g., "12345_2.jpg", "12345 (2).jpg")

        Returns:
            PartMappingResult with mapping information
        """
        try:
            # Extract potential part numbers from filename
            extracted_numbers = self._extract_part_numbers_from_filename(filename)

            if not extracted_numbers:
                return PartMappingResult(
                    original_filename=filename,
                    extracted_numbers=[],
                    mapped_part_number=None,
                    confidence_score=0.0,
                    mapping_method="no_extraction",
                    requires_manual_review=True
                )

            # Try to find best match
            best_match = self._find_best_part_match(extracted_numbers)

            if best_match:
                return PartMappingResult(
                    original_filename=filename,
                    extracted_numbers=extracted_numbers,
                    mapped_part_number=best_match["part_number"],
                    confidence_score=best_match["confidence"],
                    mapping_method=best_match["method"],
                    interchange_mapping=best_match.get("interchange"),
                    requires_manual_review=best_match["confidence"] < 0.8
                )
            else:
                # No match found - suggest manual review
                return PartMappingResult(
                    original_filename=filename,
                    extracted_numbers=extracted_numbers,
                    mapped_part_number=extracted_numbers[0] if extracted_numbers else None,
                    confidence_score=0.3,
                    mapping_method="best_guess",
                    requires_manual_review=True
                )

        except Exception as e:
            logger.error(f"Error mapping filename {filename}: {e}")
            return PartMappingResult(
                original_filename=filename,
                extracted_numbers=[],
                mapped_part_number=None,
                confidence_score=0.0,
                mapping_method="error",
                error_message=str(e),
                requires_manual_review=True
            )

    def _extract_part_numbers_from_filename(self, filename: str) -> List[str]:
        """
        Extract potential part numbers from filename.

        Handles patterns like:
        - "12345_2.jpg" -> "12345"
        - "12345 (2).jpg" -> "12345"
        - "J1234567_detail.jpg" -> "J1234567"
        - "crown_12345_v2.jpg" -> "12345"
        """
        # Remove file extension
        name_without_ext = Path(filename).stem

        # Common patterns to try
        patterns = [
            # Standard Crown part numbers (letters + numbers)
            r'^([A-Z]{0,2}\d{4,8})',
            # Remove trailing _number or (number)
            r'^(.+?)_\d+$',
            r'^(.+?)\s*\(\d+\)$',
            # Remove common suffixes
            r'^(.+?)(?:_detail|_main|_front|_back|_top|_bottom)$',
            # Extract part-like sequences
            r'([A-Z]{0,2}\d{4,8})',
            # Any sequence of letters and numbers
            r'^([A-Z0-9]{4,12})',
        ]

        extracted = []

        for pattern in patterns:
            matches = re.findall(pattern, name_without_ext.upper())
            for match in matches:
                clean_match = match.strip()
                if len(clean_match) >= 4 and clean_match not in extracted:
                    extracted.append(clean_match)

        # If no pattern matches, try the whole filename cleaned up
        if not extracted:
            clean_name = re.sub(r'[^A-Z0-9]', '', name_without_ext.upper())
            if len(clean_name) >= 4:
                extracted.append(clean_name)

        return extracted[:3]  # Return top 3 candidates

    def _find_best_part_match(self, extracted_numbers: List[str]) -> Optional[Dict]:
        """Find the best matching part number from extracted candidates."""
        best_match = None

        for part_number in extracted_numbers:
            # Check if this is a current part number
            if self._is_current_part_number(part_number):
                return {
                    "part_number": part_number,
                    "confidence": 0.95,
                    "method": "direct_match"
                }

            # Check interchange mappings
            if part_number in self.interchange_cache:
                mapping = self.interchange_cache[part_number]
                return {
                    "part_number": mapping.new_part_number,
                    "confidence": 0.85,
                    "method": "interchange_mapping",
                    "interchange": mapping
                }

            # Fuzzy matching for similar part numbers
            fuzzy_match = self._find_fuzzy_match(part_number)
            if fuzzy_match and (not best_match or fuzzy_match["confidence"] > best_match["confidence"]):
                best_match = fuzzy_match

        return best_match

    def _is_current_part_number(self, part_number: str) -> bool:
        """Check if part number exists in current master database."""
        try:
            if not self.filemaker.connection:
                return False

            cursor = self.filemaker.connection.cursor()
            query = '''
                    SELECT COUNT(*)
                    FROM Master
                    WHERE AS400_NumberStripped = ?
                      AND ToggleActive = 'Yes' \
                    '''
            cursor.execute(query, (part_number,))
            result = cursor.fetchone()
            cursor.close()

            return result and result[0] > 0

        except Exception as e:
            logger.error(f"Error checking current part number {part_number}: {e}")
            return False

    def _find_fuzzy_match(self, part_number: str) -> Optional[Dict]:
        """Find fuzzy matches for part numbers."""
        try:
            if not self.filemaker.connection:
                return None

            cursor = self.filemaker.connection.cursor()

            # Try variations: with/without leading zeros, letter prefixes
            variations = [
                part_number,
                part_number.lstrip('0'),
                part_number.zfill(8),
                f"J{part_number}",
                f"A{part_number}",
            ]

            for variation in variations:
                if variation != part_number:  # Don't re-check exact match
                    query = '''
                            SELECT AS400_NumberStripped
                            FROM Master
                            WHERE AS400_NumberStripped LIKE ?
                              AND ToggleActive = 'Yes' LIMIT 1 \
                            '''
                    cursor.execute(query, (f"%{variation}%",))
                    result = cursor.fetchone()

                    if result:
                        cursor.close()
                        return {
                            "part_number": result[0],
                            "confidence": 0.6,
                            "method": "fuzzy_match"
                        }

            cursor.close()
            return None

        except Exception as e:
            logger.error(f"Error in fuzzy matching for {part_number}: {e}")
            return None

    def get_manual_override_suggestions(self, filename: str, user_input: str) -> List[str]:
        """
        Get suggestions for manual part number override.

        Args:
            filename: Original filename
            user_input: Partial user input

        Returns:
            List of suggested part numbers
        """
        try:
            if not self.filemaker.connection or len(user_input) < 2:
                return []

            cursor = self.filemaker.connection.cursor()
            query = '''
                    SELECT DISTINCT AS400_NumberStripped
                    FROM Master
                    WHERE AS400_NumberStripped LIKE ?
                      AND ToggleActive = 'Yes'
                    ORDER BY AS400_NumberStripped LIMIT 10 \
                    '''
            cursor.execute(query, (f"{user_input.upper()}%",))
            results = cursor.fetchall()
            cursor.close()

            return [row[0] for row in results if row[0]]

        except Exception as e:
            logger.error(f"Error getting override suggestions: {e}")
            return []

    def validate_part_number(self, part_number: str) -> bool:
        """Validate that a part number exists and is active."""
        return self._is_current_part_number(part_number.upper().strip())

    def refresh_interchange_cache(self) -> None:
        """Refresh the interchange mapping cache from database."""
        self.interchange_cache.clear()
        self._load_interchange_mappings()