"""Test conversation history."""

from neurocad.core.history import History, Role


def test_add_and_items():
    """Adding messages should store them in order."""
    h = History()
    h.add(Role.USER, "Hello")
    h.add(Role.ASSISTANT, "Hi there")
    assert len(h.items) == 2
    assert h.items[0]["role"] == Role.USER
    assert h.items[0]["content"] == "Hello"
    assert h.items[1]["role"] == Role.ASSISTANT
    assert h.items[1]["content"] == "Hi there"


def test_to_llm_messages():
    """Conversion to LLM messages maps FEEDBACK to user."""
    h = History()
    h.add(Role.USER, "Hello")
    h.add(Role.FEEDBACK, "That's wrong")
    h.add(Role.ASSISTANT, "Fixed")
    msgs = h.to_llm_messages()
    assert len(msgs) == 3
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello"
    assert msgs[1]["role"] == "user"  # FEEDBACK mapped
    assert msgs[1]["content"] == "That's wrong"
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["content"] == "Fixed"


def test_clear():
    """Clearing removes all items."""
    h = History()
    h.add(Role.USER, "test")
    assert len(h.items) == 1
    h.clear()
    assert len(h.items) == 0


def test_role_enum():
    """Role enum should have expected values."""
    assert Role.USER == "user"
    assert Role.ASSISTANT == "assistant"
    assert Role.FEEDBACK == "feedback"


def test_history_empty():
    """Empty history returns empty list."""
    h = History()
    assert h.items == []
    assert h.to_llm_messages() == []
