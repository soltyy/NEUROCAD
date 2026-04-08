"""
Stub tests for context module.
"""

from neurocad.core.context import get_active_context


def test_get_active_context():
    # Should return None for now
    assert get_active_context() is None
