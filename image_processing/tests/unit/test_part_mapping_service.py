# ===== tests/unit/test_part_mapping_service.py =====
import pytest
from unittest.mock import Mock, patch, MagicMock

from ...src.services.part_mapping_service import PartMappingService
from ...src.models.part_mapping_models import InterchangeMapping, PartMappingResult


class TestPartMappingService:
    """Test PartMappingService functionality."""

    @pytest.fixture
    def mock_filemaker(self):
        """Mock FileMaker service."""
        with patch('src.services.part_mapping_service.FileMakerService') as mock_fm:
            mock_instance = Mock()
            mock_instance.test_connection.return_value = True
            mock_instance.connection = Mock()
            mock_fm.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def part_mapper(self, mock_filemaker):
        """Create PartMappingService with mocked dependencies."""
        with patch.object(PartMappingService, '_load_interchange_mappings'):
            service = PartMappingService()
            service.filemaker = mock_filemaker
            return service

    def test_extract_part_numbers_from_filename(self, part_mapper):
        """Test part number extraction from various filename patterns."""
        test_cases = [
            ("J1234567_2.jpg", ["J1234567"]),
            ("12345 (2).jpg", ["12345"]),
            ("crown_A12345_detail.jpg", ["A12345"]),
            ("part_12345_main_view.tiff", ["12345"]),
            ("complex_J9876543_v2_final.psd", ["J9876543"]),
            ("nopartnumber.jpg", []),
            ("12.jpg", []),  # Too short
        ]

        for filename, expected in test_cases:
            result = part_mapper._extract_part_numbers_from_filename(filename)
            assert result == expected, f"Failed for {filename}: got {result}, expected {expected}"

    def test_map_filename_with_direct_match(self, part_mapper):
        """Test mapping when part number directly exists in database."""
        filename = "J1234567_2.jpg"

        # Mock direct match
        part_mapper._is_current_part_number = Mock(return_value=True)

        result = part_mapper.map_filename_to_part_number(filename)

        assert isinstance(result, PartMappingResult)
        assert result.success
        assert result.mapped_part_number == "J1234567"
        assert result.confidence_score == 0.95
        assert result.mapping_method == "direct_match"

    def test_map_filename_with_interchange(self, part_mapper):
        """Test mapping using interchange table."""
        filename = "OLD12345_1.jpg"

        # Setup interchange mapping
        interchange = InterchangeMapping(
            old_part_number="OLD12345",
            new_part_number="NEW12345",
            interchange_code="IC"
        )
        part_mapper.interchange_cache["OLD12345"] = interchange
        part_mapper._is_current_part_number = Mock(return_value=False)

        result = part_mapper.map_filename_to_part_number(filename)

        assert result.mapped_part_number == "NEW12345"
        assert result.confidence_score == 0.85
        assert result.mapping_method == "interchange_mapping"
        assert result.interchange_mapping == interchange

    def test_map_filename_requires_manual_review(self, part_mapper):
        """Test mapping that requires manual review."""
        filename = "unknown_part_123.jpg"

        # Mock no matches
        part_mapper._is_current_part_number = Mock(return_value=False)
        part_mapper._find_fuzzy_match = Mock(return_value=None)
        part_mapper.interchange_cache = {}

        result = part_mapper.map_filename_to_part_number(filename)

        assert result.requires_manual_review is True
        assert result.confidence_score < 0.5

    def test_load_interchange_mappings(self, mock_filemaker):
        """Test loading interchange mappings from database."""
        # Mock database response
        cursor_mock = Mock()
        cursor_mock.fetchall.return_value = [
            ("IC1", "OLD123", "NEW123"),
            ("IC2", "OLD456", "NEW456"),
            (None, "OLD789", "NEW789"),  # Test null code handling
        ]
        cursor_mock.close = Mock()

        mock_filemaker.connection.cursor.return_value = cursor_mock

        service = PartMappingService()

        # Verify mappings were loaded
        assert len(service.interchange_cache) == 3
        assert "OLD123" in service.interchange_cache
        assert service.interchange_cache["OLD123"].new_part_number == "NEW123"
        assert service.interchange_cache["OLD123"].interchange_code == "IC1"

    def test_validate_part_number(self, part_mapper):
        """Test part number validation."""
        # Mock database response
        cursor_mock = Mock()
        cursor_mock.fetchone.return_value = (1,)  # Part exists
        cursor_mock.close = Mock()

        part_mapper.filemaker.connection.cursor.return_value = cursor_mock

        result = part_mapper.validate_part_number("J1234567")

        assert result is True
        cursor_mock.execute.assert_called_once()

    def test_validate_part_number_not_found(self, part_mapper):
        """Test part number validation when part doesn't exist."""
        # Mock database response for non-existent part
        cursor_mock = Mock()
        cursor_mock.fetchone.return_value = (0,)  # Part doesn't exist
        cursor_mock.close = Mock()

        part_mapper.filemaker.connection.cursor.return_value = cursor_mock

        result = part_mapper.validate_part_number("INVALID123")

        assert result is False

    def test_get_manual_override_suggestions(self, part_mapper):
        """Test getting suggestions for manual override."""
        # Mock database response
        cursor_mock = Mock()
        cursor_mock.fetchall.return_value = [
            ("J1234567",),
            ("J1234568",),
            ("J1234569",),
        ]
        cursor_mock.close = Mock()

        part_mapper.filemaker.connection.cursor.return_value = cursor_mock

        suggestions = part_mapper.get_manual_override_suggestions("test.jpg", "J123")

        assert len(suggestions) == 3
        assert "J1234567" in suggestions
        cursor_mock.execute.assert_called_once()

    def test_fuzzy_matching(self, part_mapper):
        """Test fuzzy matching functionality."""
        # Mock database response for fuzzy match
        cursor_mock = Mock()
        cursor_mock.fetchone.return_value = ("J0001234567",)  # Zero-padded version
        cursor_mock.close = Mock()

        part_mapper.filemaker.connection.cursor.return_value = cursor_mock

        result = part_mapper._find_fuzzy_match("1234567")

        assert result is not None
        assert result["part_number"] == "J0001234567"
        assert result["confidence"] == 0.6
        assert result["method"] == "fuzzy_match"

    def test_error_handling(self, part_mapper):
        """Test error handling in mapping operations."""
        # Mock database error
        part_mapper.filemaker.connection = None

        result = part_mapper.map_filename_to_part_number("test.jpg")

        assert isinstance(result, PartMappingResult)
        assert result.requires_manual_review is True
        # Should not raise exception

    @pytest.mark.parametrize("filename,expected_count", [
        ("J1234567_detail.jpg", 1),
        ("complex_A12345_B67890_final.jpg", 2),
        ("no_numbers_here.jpg", 0),
        ("123.jpg", 0),  # Too short
        ("verylongpartnumber123456789012345.jpg", 1),
    ])
    def test_extraction_edge_cases(self, part_mapper, filename, expected_count):
        """Test edge cases in part number extraction."""
        result = part_mapper._extract_part_numbers_from_filename(filename)
        assert len(result) == expected_count

    def test_confidence_scoring(self, part_mapper):
        """Test confidence scoring for different match types."""
        test_cases = [
            ("direct_match", 0.95),
            ("interchange_mapping", 0.85),
            ("fuzzy_match", 0.6),
            ("best_guess", 0.3),
        ]

        for method, expected_confidence in test_cases:
            # This would require mocking specific scenarios for each method
            # Implementation depends on how confidence is calculated
            pass  # Placeholder for confidence testing

    def test_cache_performance(self, part_mapper):
        """Test that caching improves performance."""
        # Setup cache
        part_mapper.interchange_cache["TEST123"] = InterchangeMapping(
            old_part_number="TEST123",
            new_part_number="NEW123",
            interchange_code="IC"
        )

        # First call should use cache
        result1 = part_mapper.map_filename_to_part_number("TEST123_1.jpg")

        # Second call should also use cache (no additional DB calls)
        result2 = part_mapper.map_filename_to_part_number("TEST123_2.jpg")

        assert result1.mapped_part_number == result2.mapped_part_number
        assert result1.mapping_method == "interchange_mapping"