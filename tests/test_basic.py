#!/usr/bin/env python3
"""
Basic test suite for vscode-ark signal classification algorithms.
Run with: python -m pytest tests/ -v
"""

import pytest
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_signal_patterns_import():
    """Test that signal patterns can be imported from extract.py"""
    try:
        from cda.pipeline.extract import SIGNAL_PATTERNS
        assert isinstance(SIGNAL_PATTERNS, list)
        assert len(SIGNAL_PATTERNS) > 0
        # Check structure of first pattern
        pattern = SIGNAL_PATTERNS[0]
        assert len(pattern) == 3  # (signal_type, keywords, description)
        assert isinstance(pattern[0], str)  # signal_type
        assert isinstance(pattern[1], list)  # keywords
        assert isinstance(pattern[2], str)  # description
    except ImportError:
        pytest.skip("extract.py dependencies not available")


def test_heat_weights():
    """Test heat weight constants"""
    try:
        from cda.pipeline.extract import HEAT_WEIGHT
        assert isinstance(HEAT_WEIGHT, dict)
        assert 'correction' in HEAT_WEIGHT
        assert 'frustration' in HEAT_WEIGHT
        assert HEAT_WEIGHT['correction'] == 3
        assert HEAT_WEIGHT['frustration'] == 5
    except ImportError:
        pytest.skip("extract.py dependencies not available")


def test_extract_code_symbols():
    from cda.pipeline.extract import extract_code_symbols

    py_source = """
class Foo:
    def bar(self):
        pass


def baz(x):
    return x
"""
    py_symbols = extract_code_symbols("test.py", py_source)
    py_names = {s['symbol_name'] for s in py_symbols}
    assert 'Foo' in py_names
    assert 'Foo.bar' in py_names
    assert 'baz' in py_names

    js_source = """
export function foo() {
}
const bar = () => {
}
class Baz {}
"""
    js_symbols = extract_code_symbols("test.js", js_source)
    js_names = {s['symbol_name'] for s in js_symbols}
    assert 'foo' in js_names
    assert 'bar' in js_names
    assert 'Baz' in js_names


def test_basic_file_operations():
    """Test basic file reading functions"""
    from cda.pipeline.ingest import read_json, read_bytes

    # Test with non-existent file
    assert read_json("/nonexistent/file.json") is None
    assert read_bytes("/nonexistent/file.bin") is None

    # Test with valid JSON
    import tempfile
    import json

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"test": "data"}, f)
        temp_path = f.name

    try:
        result = read_json(temp_path)
        assert result == {"test": "data"}
    finally:
        os.unlink(temp_path)


def test_compress_decompress():
    """Test compression functions"""
    from cda.pipeline.ingest import compress
    from cda.pipeline.reconstruct import decompress_vfs

    test_data = b"Hello, World! This is test data for compression." * 100  # Make it larger
    compressed = compress(test_data)
    assert len(compressed) < len(test_data)  # Should be smaller

    # Test decompression
    decompressed = decompress_vfs(compressed)
    assert decompressed == test_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
