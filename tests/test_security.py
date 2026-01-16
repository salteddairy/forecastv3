"""
Unit tests for Security Utilities
Tests input sanitization and validation functions
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    sanitize_string,
    validate_path_safe,
    sanitize_dataframe,
    validate_numeric_range,
    safe_filename
)


class TestSanitizeString:
    """Test string sanitization"""

    def test_basic_string(self):
        """Test basic string passes through"""
        result = sanitize_string("Hello World")
        assert result == "Hello World"

    def test_sql_injection_prevention(self):
        """Test SQL injection patterns are neutralized"""
        # SQL comment patterns - comments should be removed
        result = sanitize_string("test--comment")
        assert "--" not in result

        # SQL keywords should be removed
        result = sanitize_string("SELECT * FROM users")
        # The sanitization removes dangerous SQL keywords
        assert "SELECT" not in result or "select" not in result.lower()

    def test_xss_prevention(self):
        """Test XSS patterns are neutralized"""
        result = sanitize_string("<script>alert('xss')</script>")
        # Script tags should be removed
        assert "<script>" not in result
        assert "</script>" not in result

    def test_max_length_truncation(self):
        """Test string is truncated to max length"""
        long_string = "a" * 2000
        result = sanitize_string(long_string, max_length=100)
        assert len(result) == 100

    def test_special_char_removal(self):
        """Test special characters are removed by default"""
        result = sanitize_string("test@#$%^&*()file")
        assert "@" not in result
        assert "#" not in result

    def test_special_chars_allowed(self):
        """Test special characters are kept when allowed"""
        result = sanitize_string("test@#$%^&*()file", allow_special_chars=True)
        assert "@" in result

    def test_none_input(self):
        """Test None input returns empty string"""
        result = sanitize_string(None)
        assert result == ""

    def test_numeric_input(self):
        """Test numeric input is converted to string"""
        result = sanitize_string(12345)
        assert result == "12345"

    def test_whitespace_trimming(self):
        """Test leading/trailing whitespace is removed"""
        result = sanitize_string("  test  ")
        assert result == "test"


class TestValidatePathSafe:
    """Test path validation"""

    def test_safe_path_within_allowed(self, tmp_path):
        """Test path within allowed directory passes"""
        allowed_dir = tmp_path / "data"
        allowed_dir.mkdir()

        test_file = allowed_dir / "test.txt"
        test_file.touch()

        result = validate_path_safe(test_file, allowed_dir)
        assert result == test_file.resolve()

    def test_path_escaping_allowed_directory(self, tmp_path):
        """Test path escaping allowed directory raises error"""
        allowed_dir = tmp_path / "data"
        allowed_dir.mkdir()

        other_dir = tmp_path / "other"
        other_dir.mkdir()
        test_file = other_dir / "test.txt"
        test_file.touch()

        with pytest.raises(ValueError, match="Path outside allowed directory"):
            validate_path_safe(test_file, allowed_dir)

    def test_path_traversal_prevention(self, tmp_path):
        """Test path traversal is prevented"""
        allowed_dir = tmp_path / "data"
        allowed_dir.mkdir()

        # Try to escape using ../
        test_file = allowed_dir / ".." / "sensitive.txt"

        with pytest.raises(ValueError, match="Path outside allowed directory"):
            validate_path_safe(test_file, allowed_dir)


class TestSanitizeDataFrame:
    """Test DataFrame sanitization"""

    def test_sanitizes_string_columns(self):
        """Test string columns are sanitized"""
        df = pd.DataFrame({
            'safe_col': ['item1', 'item2', 'item3'],
            'unsafe_col': ['test<script>', 'test--comment', 'test; DROP']
        })

        result = sanitize_dataframe(df)

        # Unsafe patterns should be neutralized (tags/comments removed)
        assert "<script>" not in result.iloc[0]['unsafe_col']
        assert "--" not in result.iloc[1]['unsafe_col']
        # DROP keyword should be removed
        assert "DROP" not in result.iloc[2]['unsafe_col'] or "drop" not in result.iloc[2]['unsafe_col'].lower()

    def test_preserves_numeric_columns(self):
        """Test numeric columns are unchanged"""
        df = pd.DataFrame({
            'numbers': [1, 2, 3],
            'floats': [1.1, 2.2, 3.3]
        })

        result = sanitize_dataframe(df)

        pd.testing.assert_frame_equal(result, df)

    def test_handles_nan_values(self):
        """Test NaN values are preserved"""
        df = pd.DataFrame({
            'col_with_nan': ['test', None, np.nan]
        })

        result = sanitize_dataframe(df)

        assert pd.isna(result.iloc[1]['col_with_nan'])
        assert pd.isna(result.iloc[2]['col_with_nan'])


class TestValidateNumericRange:
    """Test numeric range validation"""

    def test_within_range(self):
        """Test value within range passes"""
        result = validate_numeric_range(50, "test", min_value=0, max_value=100)
        assert result == 50.0

    def test_below_minimum(self):
        """Test value below minimum raises error"""
        with pytest.raises(ValueError, match="must be >="):
            validate_numeric_range(-10, "test", min_value=0)

    def test_above_maximum(self):
        """Test value above maximum raises error"""
        with pytest.raises(ValueError, match="must be <="):
            validate_numeric_range(150, "test", max_value=100)

    def test_only_minimum(self):
        """Test validation with only minimum"""
        result = validate_numeric_range(100, "test", min_value=50)
        assert result == 100.0

    def test_only_maximum(self):
        """Test validation with only maximum"""
        result = validate_numeric_range(50, "test", max_value=100)
        assert result == 50.0

    def test_string_to_numeric(self):
        """Test string is converted to number"""
        result = validate_numeric_range("50.5", "test")
        assert result == 50.5

    def test_invalid_numeric(self):
        """Test invalid numeric raises error"""
        with pytest.raises(ValueError, match="must be a number"):
            validate_numeric_range("not_a_number", "test")


class TestSafeFilename:
    """Test safe filename generation"""

    def test_basic_filename(self):
        """Test basic filename passes through"""
        result = safe_filename("document.txt")
        assert result == "document.txt"

    def test_removes_path_components(self):
        """Test path components are removed"""
        result = safe_filename("/etc/passwd")
        assert result == "passwd"

    def test_replaces_dangerous_chars(self):
        """Test dangerous characters are replaced"""
        result = safe_filename("file<>name|?.txt")
        assert ">" not in result
        assert "<" not in result
        assert "|" not in result
        assert "?" not in result

    def test_max_length(self):
        """Test filename is truncated"""
        long_name = "a" * 300
        result = safe_filename(long_name, max_length=100)
        assert len(result) == 100

    def test_removes_leading_dots(self):
        """Test leading dots are removed"""
        result = safe_filename("...hiddenfile")
        assert not result.startswith(".")

    def test_empty_filename(self):
        """Test empty filename returns 'unnamed'"""
        result = safe_filename("...")
        assert result == "unnamed"

    def test_preserves_safe_special_chars(self):
        """Test safe special characters are preserved"""
        result = safe_filename("my-file_v1.0.txt")
        assert result == "my-file_v1.0.txt"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
