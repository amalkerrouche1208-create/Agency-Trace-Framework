from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence

from agencytrace.io import load_jsonl_events
from agencytrace.reconstruct import reconstruct_suggestion_episodes


ROOT = Path(__file__).resolve().parents[2]


AUDIT_SCRIPTS = {
    "text-deltas": "scripts/audit_text_deltas.py",
    "lifecycle": "scripts/audit_suggestion_episodes.py",
    "provenance": "scripts/audit_provenance.py",
    "metrics": "scripts/audit_metrics.py",
}

EXPORT_SCRIPTS = {
    "modern": "scripts/export_metrics.py",
    "target": "scripts/export_target_behavior.py",
}


def _package_version() -> str:
    try:
        return version("agencytrace")
    except PackageNotFoundError:
        return "0.1.1"


def _run(
    arguments: Sequence[str],
) -> int:
    command = [
        sys.executable,
        *arguments,
    ]

    print()
    print(
        "$",
        " ".join(command),
    )
    print()

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    return completed.returncode


def _require_success(
    arguments: Sequence[str],
) -> None:
    return_code = _run(
        arguments
    )

    if return_code != 0:
        raise SystemExit(
            return_code
        )


# =====================================================================
# Reconstruct
# =====================================================================


def _discover_input_files(
    path: Path,
    pattern: str,
) -> list[Path]:
    if path.is_file():
        return [path]

    if not path.exists():
        raise SystemExit(
            f"Input path does not exist: {path}"
        )

    if not path.is_dir():
        raise SystemExit(
            f"Input path is not a file or directory: {path}"
        )

    files = sorted(
        path.rglob(pattern)
    )

    if not files:
        raise SystemExit(
            f"No files matching {pattern!r} "
            f"found under {path}"
        )

    return files


def _command_reconstruct(
    args: argparse.Namespace,
) -> None:
    files = _discover_input_files(
        args.path,
        args.pattern,
    )

    total_events = 0
    total_requests = 0
    total_selects = 0
    total_dismissed = 0
    total_reopens = 0

    event_counts: Counter[str] = Counter()

    failures: list[
        tuple[Path, Exception]
    ] = []

    for index, path in enumerate(
        files,
        start=1,
    ):
        try:
            events = load_jsonl_events(
                path
            )

            episodes = (
                reconstruct_suggestion_episodes(
                    events
                )
            )

        except Exception as exc:
            failures.append(
                (
                    path,
                    exc,
                )
            )

            if not args.summary:
                print(
                    f"FAIL  {path}: {exc}"
                )

            continue

        counts = Counter(
            event.event_name
            for event in events
        )

        event_counts.update(
            counts
        )

        selections = counts[
            "suggestion-select"
        ]

        dismissed = sum(
            1
            for episode in episodes
            if getattr(
                episode,
                "was_dismissed",
                False,
            )
        )

        total_events += len(
            events
        )

        total_requests += len(
            episodes
        )

        total_selects += selections

        total_dismissed += dismissed

        total_reopens += counts[
            "suggestion-reopen"
        ]

        if not args.summary:
            print(
                f"{path} | "
                f"events={len(events)} "
                f"requests={len(episodes)} "
                f"selections={selections} "
                f"dismissed={dismissed}"
            )

        elif (
            index % 100 == 0
            or index == len(files)
        ):
            print(
                f"Processed "
                f"{index}/{len(files)} sessions..."
            )

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Reconstruction Summary"
    )
    print("=" * 78)

    print(
        f"Input files                    : "
        f"{len(files)}"
    )

    print(
        f"Successfully reconstructed     : "
        f"{len(files) - len(failures)}"
    )

    print(
        f"Failed                         : "
        f"{len(failures)}"
    )

    print()
    print(
        f"Events                         : "
        f"{total_events}"
    )

    print(
        f"Suggestion requests            : "
        f"{total_requests}"
    )

    print(
        f"Suggestion selections          : "
        f"{total_selects}"
    )

    print(
        f"Dismissed episodes             : "
        f"{total_dismissed}"
    )

    print(
        f"Reopen events                  : "
        f"{total_reopens}"
    )

    print()
    print(
        f"suggestion-get                 : "
        f"{event_counts['suggestion-get']}"
    )

    print(
        f"suggestion-open                : "
        f"{event_counts['suggestion-open']}"
    )

    print(
        f"suggestion-select              : "
        f"{event_counts['suggestion-select']}"
    )

    print(
        f"suggestion-close               : "
        f"{event_counts['suggestion-close']}"
    )

    print("=" * 78)

    if failures:
        print()
        print("Failed inputs:")

        for path, exc in failures:
            print(
                f"  {path}: {exc}"
            )

        raise SystemExit(1)


# =====================================================================
# Audit
# =====================================================================


def _command_audit(
    args: argparse.Namespace,
) -> None:
    targets = (
        tuple(AUDIT_SCRIPTS)
        if args.target == "all"
        else (
            args.target,
        )
    )

    for target in targets:
        _require_success(
            [
                AUDIT_SCRIPTS[
                    target
                ]
            ]
        )


# =====================================================================
# Export
# =====================================================================


def _command_export(
    args: argparse.Namespace,
) -> None:
    targets = (
        ("modern", "target")
        if args.target == "all"
        else (
            args.target,
        )
    )

    for target in targets:
        _require_success(
            [
                EXPORT_SCRIPTS[
                    target
                ]
            ]
        )


# =====================================================================
# Analyze
# =====================================================================


def _command_analyze(
    args: argparse.Namespace,
) -> None:
    del args

    _require_success(
        [
            "-m",
            "agencytrace.analysis",
        ]
    )


# =====================================================================
# Figures
# =====================================================================


def _command_figures(
    args: argparse.Namespace,
) -> None:
    command = [
        "-m",
        "agencytrace.figures",
        "--analysis-dir",
        str(
            args.analysis_dir
        ),
        "--out",
        str(
            args.out
        ),
    ]

    _require_success(
        command
    )


# =====================================================================
# Reproduce
# =====================================================================


def _command_reproduce(
    args: argparse.Namespace,
) -> None:
    command = [
        "scripts/reproduce_all.py",
    ]

    if args.skip_audits:
        command.append(
            "--skip-audits"
        )

    _require_success(
        command
    )


# =====================================================================
# Validate
# =====================================================================


def _command_validate(
    args: argparse.Namespace,
) -> None:
    del args

    _require_success(
        [
            "scripts/validate_release.py",
        ]
    )


# =====================================================================
# Parser
# =====================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agencytrace",
        description=(
            "AgencyTrace research-software CLI for "
            "CoAuthor trace reconstruction, behavioral "
            "analysis, figure generation, and reproducibility."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"%(prog)s "
            f"{_package_version()}"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
    )

    # reconstruct ------------------------------------------------------

    reconstruct_parser = (
        subparsers.add_parser(
            "reconstruct",
            help=(
                "Reconstruct suggestion episodes "
                "from CoAuthor event traces."
            ),
        )
    )

    reconstruct_parser.add_argument(
        "path",
        type=Path,
        help=(
            "JSONL session file or directory "
            "containing session files."
        ),
    )

    reconstruct_parser.add_argument(
        "--pattern",
        default="*.jsonl",
        help=(
            "Recursive file pattern for directory "
            "inputs (default: *.jsonl)."
        ),
    )

    reconstruct_parser.add_argument(
        "--summary",
        action="store_true",
        help=(
            "Print aggregate corpus statistics "
            "instead of one line per session."
        ),
    )

    reconstruct_parser.set_defaults(
        handler=_command_reconstruct
    )

    # audit ------------------------------------------------------------

    audit_parser = (
        subparsers.add_parser(
            "audit",
            help=(
                "Run corpus integrity and "
                "reconstruction audits."
            ),
        )
    )

    audit_parser.add_argument(
        "target",
        nargs="?",
        choices=(
            "all",
            "text-deltas",
            "lifecycle",
            "provenance",
            "metrics",
        ),
        default="all",
        help=(
            "Audit to run "
            "(default: all)."
        ),
    )

    audit_parser.set_defaults(
        handler=_command_audit
    )

    # export -----------------------------------------------------------

    export_parser = (
        subparsers.add_parser(
            "export",
            help=(
                "Export validated session, selection, "
                "and historical target metrics."
            ),
        )
    )

    export_parser.add_argument(
        "target",
        nargs="?",
        choices=(
            "all",
            "modern",
            "target",
        ),
        default="all",
        help=(
            "Metric layer to export "
            "(default: all)."
        ),
    )

    export_parser.set_defaults(
        handler=_command_export
    )

    # analyze ----------------------------------------------------------

    analyze_parser = (
        subparsers.add_parser(
            "analyze",
            help=(
                "Generate validated target "
                "analysis tables."
            ),
        )
    )

    analyze_parser.set_defaults(
        handler=_command_analyze
    )

    # figures ----------------------------------------------------------

    figures_parser = (
        subparsers.add_parser(
            "figures",
            help=(
                "Generate validated PNG/PDF "
                "target figures."
            ),
        )
    )

    figures_parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=Path(
            "data/analysis"
        ),
        help=(
            "Directory containing analysis CSVs."
        ),
    )

    figures_parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "figures"
        ),
        help=(
            "Output directory for figures."
        ),
    )

    figures_parser.set_defaults(
        handler=_command_figures
    )

    # reproduce --------------------------------------------------------

    reproduce_parser = (
        subparsers.add_parser(
            "reproduce",
            help=(
                "Run the complete AgencyTrace "
                "reproduction pipeline."
            ),
        )
    )

    reproduce_parser.add_argument(
        "--skip-audits",
        action="store_true",
        help=(
            "Skip the expensive corpus audit stages."
        ),
    )

    reproduce_parser.set_defaults(
        handler=_command_reproduce
    )

    # validate ---------------------------------------------------------

    validate_parser = (
        subparsers.add_parser(
            "validate",
            help=(
                "Validate frozen corpus invariants, "
                "analysis outputs, and figures."
            ),
        )
    )

    validate_parser.set_defaults(
        handler=_command_validate
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _build_parser()

    args = parser.parse_args(
        argv
    )

    handler = getattr(
        args,
        "handler",
        None,
    )

    if handler is None:
        parser.print_help()
        return 0

    handler(
        args
    )

    return 0