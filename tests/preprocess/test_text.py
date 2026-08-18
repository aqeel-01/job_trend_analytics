"""Tests for job description preprocessing."""

from pipeline.preprocess.text import preprocess_description


def test_preprocess_html_content() -> None:
    raw = (
        "<p>Preiswecker is a price comparison portal.</p>"
        "<h2>Responsibilities</h2>"
        "<ul><li>Design and build features</li><li>Write clean code</li></ul>"
        "<p>Contact us at <a href=\"mailto:jobs@example.com\">jobs@example.com</a>.</p>"
    )

    result = preprocess_description(raw)

    assert "<" not in result
    assert ">" not in result
    assert "Preiswecker is a price comparison portal." in result
    assert "Design and build features" in result
    assert "Write clean code" in result
    assert "jobs@example.com" in result


def test_preprocess_html_entities() -> None:
    raw = "<p>Salary:&nbsp;&pound;50k &amp; benefits</p>"

    result = preprocess_description(raw)

    assert result == "Salary: £50k & benefits"


def test_preprocess_excessive_whitespace() -> None:
    raw = "  Hello    world\n\n\n\t test   "

    result = preprocess_description(raw)

    assert result == "Hello world test"


def test_preprocess_empty_text() -> None:
    assert preprocess_description("") == ""
    assert preprocess_description("   ") == ""
    assert preprocess_description("\n\t  \r") == ""


def test_preprocess_null_values() -> None:
    assert preprocess_description(None) == ""


def test_preprocess_non_string_input() -> None:
    assert preprocess_description(12345) == "12345"


def test_preprocess_normal_description() -> None:
    raw = "We are looking for a Software Engineer with Python experience."

    result = preprocess_description(raw)

    assert result == raw


def test_preprocess_is_deterministic() -> None:
    raw = "<p>  Python   &amp;   Docker  </p>"

    first = preprocess_description(raw)
    second = preprocess_description(raw)

    assert first == second
    assert first == "Python & Docker"
