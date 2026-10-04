from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import pytest

from agencytrace.cli import _build_parser, main


FIXTURES = Path("tests/fixtures")


def test_cli_parser_exposes_public_commands() -> None:
    parser = _build_parser()

    help_text = parser.format_help()

    for command in (
        "reconstruct",
        "audit",
        "export",
        "analyze",
        "figures",
        "reproduce",
        "validate",
    ):
        assert command in help_text


def test_cli_version_matches_installed_package(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--version",
            ]
        )

    assert exc_info.value.code == 0

    output = capsys.readouterr().out.strip()

    assert output == (
        f"agencytrace "
        f"{version('agencytrace')}"
    )


def test_cli_reconstructs_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = (
        FIXTURES
        / "minimal_session.jsonl"
    )

    assert fixture.is_file()

    return_code = main(
        [
            "reconstruct",
            str(fixture),
        ]
    )

    assert return_code == 0

    output = capsys.readouterr().out

    assert (
        "AgencyTrace — Reconstruction Summary"
        in output
    )

    assert (
        "Successfully reconstructed     : 1"
        in output
    )

    assert (
        "Failed                         : 0"
        in output
    )


def test_cli_rejects_missing_input() -> None:
    with pytest.raises(
        SystemExit,
        match="Input path does not exist",
    ):
        main(
            [
                "reconstruct",
                "does-not-exist.jsonl",
            ]
        )