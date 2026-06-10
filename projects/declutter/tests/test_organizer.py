"""
Tests for DeClutter file organization and deduplication engine.
Run: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from organizer import FileMetadata, FileAnalyzer, DeduplicationEngine
from datetime import datetime


class TestFileMetadata:
    """Test file metadata object."""

    def test_metadata_creation(self, tmp_path):
        # Create a real temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")

        stat = test_file.stat()
        metadata = FileMetadata(
            path=test_file,
            size=stat.st_size,
            modified_date=datetime.fromtimestamp(stat.st_mtime),
            mime_type="text/plain",
            extension=".txt"
        )

        assert metadata.size > 0
        assert metadata.extension == ".txt"
        assert metadata.is_duplicate is False
        assert metadata.duplicate_of is None

    def test_duplicate_flagging(self):
        metadata = FileMetadata(
            path=Path("/fake/path/copy.txt"),
            size=1024,
            modified_date=datetime.now(),
            mime_type="text/plain",
            extension=".txt",
            is_duplicate=True,
            duplicate_of=Path("/fake/path/original.txt")
        )

        assert metadata.is_duplicate is True
        assert metadata.duplicate_of == Path("/fake/path/original.txt")


class TestFileAnalyzer:
    """Test file categorization logic."""

    def setup_method(self):
        self.analyzer = FileAnalyzer(Path("/tmp"))

    def test_categorize_document(self):
        metadata = FileMetadata(
            path=Path("/tmp/report.pdf"),
            size=100,
            modified_date=datetime.now(),
            mime_type="application/pdf",
            extension=".pdf"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "documents"

    def test_categorize_spreadsheet(self):
        metadata = FileMetadata(
            path=Path("/tmp/budget.xlsx"),
            size=100,
            modified_date=datetime.now(),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            extension=".xlsx"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "spreadsheets"

    def test_categorize_image(self):
        metadata = FileMetadata(
            path=Path("/tmp/photo.jpg"),
            size=100,
            modified_date=datetime.now(),
            mime_type="image/jpeg",
            extension=".jpg"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "images"

    def test_categorize_code(self):
        metadata = FileMetadata(
            path=Path("/tmp/script.py"),
            size=100,
            modified_date=datetime.now(),
            mime_type="text/x-python",
            extension=".py"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "code"

    def test_categorize_archive(self):
        metadata = FileMetadata(
            path=Path("/tmp/backup.zip"),
            size=100,
            modified_date=datetime.now(),
            mime_type="application/zip",
            extension=".zip"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "archives"

    def test_categorize_unknown(self):
        metadata = FileMetadata(
            path=Path("/tmp/random.xyz"),
            size=100,
            modified_date=datetime.now(),
            mime_type="application/octet-stream",
            extension=".xyz"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "other"

    def test_categorize_by_pattern_in_name(self):
        metadata = FileMetadata(
            path=Path("/tmp/invoice_summary.txt"),
            size=100,
            modified_date=datetime.now(),
            mime_type="text/plain",
            extension=".txt"
        )
        category = self.analyzer.categorize_file(metadata)
        assert category == "documents"  # "invoice" pattern matches documents


class TestDeduplicationEngine:
    """Test deduplication logic."""

    def setup_method(self):
        self.engine = DeduplicationEngine(safe_mode=True)

    def test_safe_mode_enabled(self):
        assert self.engine.safe_mode is True

    def test_partial_hash_same_content(self, tmp_path):
        # Create two files with identical content
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "Hello World " * 1000

        file1.write_text(content)
        file2.write_text(content)

        hash1 = self.engine._partial_file_hash(file1)
        hash2 = self.engine._partial_file_hash(file2)

        assert hash1 is not None
        assert hash2 is not None
        assert hash1 == hash2

    def test_partial_hash_different_content(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("AAAA " * 1000)
        file2.write_text("BBBB " * 1000)

        hash1 = self.engine._partial_file_hash(file1)
        hash2 = self.engine._partial_file_hash(file2)

        assert hash1 is not None
        assert hash2 is not None
        assert hash1 != hash2

    def test_full_hash_same_content(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "Identical content for hashing"

        file1.write_text(content)
        file2.write_text(content)

        hash1 = self.engine._full_file_hash(file1)
        hash2 = self.engine._full_file_hash(file2)

        assert hash1 == hash2

    def test_full_hash_different_content(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        hash1 = self.engine._full_file_hash(file1)
        hash2 = self.engine._full_file_hash(file2)

        assert hash1 != hash2

    def test_empty_file_handling(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        result = self.engine._partial_file_hash(empty_file)
        assert result == "empty_file"

    def test_find_duplicates_exact(self, tmp_path):
        # Create test files
        file1 = tmp_path / "original.txt"
        file2 = tmp_path / "copy.txt"
        file3 = tmp_path / "different.txt"

        file1.write_text("Duplicate content")
        file2.write_text("Duplicate content")
        file3.write_text("Different content")

        metadata_list = []
        for f in [file1, file2, file3]:
            stat = f.stat()
            metadata_list.append(FileMetadata(
                path=f,
                size=stat.st_size,
                modified_date=datetime.fromtimestamp(stat.st_mtime),
                mime_type="text/plain",
                extension=".txt"
            ))

        duplicates = self.engine.find_duplicates_exact(metadata_list)

        # Should find one duplicate group with 2 files
        assert len(duplicates) == 1
        for hash_key, files in duplicates.items():
            assert len(files) == 2

    def test_calculate_savings(self, tmp_path):
        file1 = tmp_path / "original.txt"
        file2 = tmp_path / "copy.txt"
        content = "X" * 1000  # 1000 bytes

        file1.write_text(content)
        file2.write_text(content)

        metadata_list = []
        for f in [file1, file2]:
            stat = f.stat()
            metadata_list.append(FileMetadata(
                path=f,
                size=stat.st_size,
                modified_date=datetime.fromtimestamp(stat.st_mtime),
                mime_type="text/plain",
                extension=".txt"
            ))

        duplicates = self.engine.find_duplicates_exact(metadata_list)
        savings = self.engine.calculate_savings(duplicates)

        # Savings should be size of one duplicate file (one kept, one removed)
        assert savings == 1000

    def test_no_duplicates_returns_zero_savings(self, tmp_path):
        file1 = tmp_path / "unique1.txt"
        file2 = tmp_path / "unique2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        metadata_list = []
        for f in [file1, file2]:
            stat = f.stat()
            metadata_list.append(FileMetadata(
                path=f,
                size=stat.st_size,
                modified_date=datetime.fromtimestamp(stat.st_mtime),
                mime_type="text/plain",
                extension=".txt"
            ))

        duplicates = self.engine.find_duplicates_exact(metadata_list)
        savings = self.engine.calculate_savings(duplicates)

        assert savings == 0


class TestHumanReadableSize:
    """Test size formatting utility."""

    def test_bytes(self):
        from organizer import FileOrganizer
        org = FileOrganizer("/tmp")
        assert "B" in org._human_readable_size(500)

    def test_kilobytes(self):
        from organizer import FileOrganizer
        org = FileOrganizer("/tmp")
        result = org._human_readable_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        from organizer import FileOrganizer
        org = FileOrganizer("/tmp")
        result = org._human_readable_size(5_000_000)
        assert "MB" in result

    def test_gigabytes(self):
        from organizer import FileOrganizer
        org = FileOrganizer("/tmp")
        result = org._human_readable_size(5_000_000_000)
        assert "GB" in result