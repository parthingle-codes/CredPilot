"""Parser and line-metadata tests."""

from __future__ import annotations

from app.analysis.models import SourceFile
from app.analysis.parsers import parse_file
from app.analysis.parsers.detect import detect_format, normalize_path
from app.analysis.parsers.lines import find_line, line_at, meta_line
from app.analysis.parsers.yaml_loader import load_yaml_with_lines


def test_detect_format_by_filename() -> None:
    assert detect_format("render.yaml", "") == "render"
    assert detect_format("render.yml", "") == "render"
    assert detect_format("docker-compose.yml", "") == "compose"
    assert detect_format("compose.yaml", "") == "compose"
    assert detect_format("docker-compose.prod.yaml", "") == "compose"
    assert detect_format(".env", "") == "dotenv"
    assert detect_format(".env.local", "") == "dotenv"
    assert detect_format("production.env", "") == "dotenv"
    assert detect_format("notes.md", "hello") == "unknown"


def test_detect_format_by_structure() -> None:
    render = "services:\n  - type: web\n    name: demo\n"
    compose = "services:\n  api:\n    image: nginx:1.27\n"
    dotenv = "DEBUG=false\nCORS_ORIGINS=https://example.com\n"

    assert detect_format("unknown.yaml", render) == "render"
    assert detect_format("unknown.yaml", compose) == "compose"
    assert detect_format("config.txt", dotenv) == "dotenv"


def test_normalize_path() -> None:
    assert normalize_path(".\\config\\render.yaml") == "config/render.yaml"
    assert normalize_path("./render.yaml") == "render.yaml"
    assert normalize_path("a//b///c.yaml") == "a/b/c.yaml"
    assert normalize_path("  .env  ") == ".env"


def test_yaml_line_metadata() -> None:
    data = load_yaml_with_lines(
        "services:\n  - type: web\n    name: demo\n    plan: free\n"
    )
    service = data["services"][0]

    assert data["__line__"] == 1
    assert service["__line__"] == 2
    assert meta_line(service) == 2
    assert meta_line(service, "name") == 3
    assert meta_line(service, "plan") == 4
    assert meta_line(data, "services") == 1


def test_line_helpers() -> None:
    lines = ["# comment", "plan: free", "name: demo"]
    assert find_line(lines, r"plan:\s*free") == 2
    assert find_line(lines, r"# comment") is None  # comments skipped by default
    assert find_line(lines, r"# comment", skip_comments=False) == 1
    assert line_at(lines, 2) == "plan: free"
    assert line_at(lines, 0) == ""
    assert line_at(lines, 99) == ""


def test_dotenv_parsing_quotes_and_comments() -> None:
    content = (
        "# comment\n"
        'QUOTED="hello world"\n'
        "SINGLE='single value'\n"
        "INLINE=value # trailing comment\n"
        "HASH=value#kept\n"
        "EMPTY=\n"
        "not a valid line\n"
    )
    doc = parse_file(SourceFile(".env", content))
    entries = {entry.key: entry for entry in doc.env_entries}

    assert entries["QUOTED"].value == "hello world"
    assert entries["SINGLE"].value == "single value"
    assert entries["INLINE"].value == "value"
    assert entries["HASH"].value == "value#kept"
    assert entries["EMPTY"].value == ""
    assert "not a valid line" not in entries
    assert entries["QUOTED"].line == 2
    assert doc.format == "dotenv"
    assert "Parsed 5 environment variable(s)" in doc.note


def test_malformed_render_yaml_reports_error_and_line() -> None:
    doc = parse_file(
        SourceFile("render.yaml", "services:\n  - type: web\n    name: [unclosed\n")
    )

    assert doc.error is not None
    assert doc.error_line is not None
    assert doc.error_line >= 1
    assert doc.format == "render"


def test_render_shape_error_is_reported() -> None:
    doc = parse_file(SourceFile("render.yaml", "services:\n  name: demo\n"))

    assert doc.error == "`services` must be a list."
    assert doc.error_line == 1


def test_compose_requires_services_mapping() -> None:
    doc = parse_file(SourceFile("docker-compose.yml", "version: '3'\n"))
    assert doc.error is not None
    assert "services" in doc.error


def test_compose_rejects_empty_services() -> None:
    doc = parse_file(SourceFile("docker-compose.yml", "services: {}\n"))
    assert doc.error is not None
    assert "empty" in doc.error


def test_parse_render_note_counts_resources() -> None:
    doc = parse_file(
        SourceFile(
            "render.yaml",
            "services:\n"
            "  - type: web\n"
            "    name: demo\n"
            "databases:\n"
            "  - name: db\n",
        )
    )
    assert doc.error is None
    assert "1 service(s)" in doc.note
    assert "1 database(s)" in doc.note


def test_unknown_format_note_lists_supported_inputs() -> None:
    doc = parse_file(SourceFile("README.md", "# docs"))
    assert doc.format == "unknown"
    assert "Unrecognized format" in doc.note
    assert "Render Blueprint" in doc.note
    assert "Docker Compose" in doc.note
    assert ".env" in doc.note
