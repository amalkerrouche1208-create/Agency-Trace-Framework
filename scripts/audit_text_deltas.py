from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agencytrace.io import load_jsonl_events


RAW_DIR = Path("data/raw")


def value_type(value: Any) -> str:
    if value is None:
        return "None"
    return type(value).__name__


def safe_preview(value: Any, limit: int = 120) -> str:
    """
    Produce a bounded diagnostic representation.

    Large strings and embedded objects are never printed in full.
    """
    if isinstance(value, str):
        escaped = value.replace("\n", "\\n")

        if len(escaped) > limit:
            return (
                repr(escaped[:limit])
                + f"... <{len(value)} chars>"
            )

        return repr(escaped)

    if isinstance(value, dict):
        return (
            f"<dict keys={sorted(value.keys())} "
            f"size={len(value)}>"
        )

    if isinstance(value, list):
        return f"<list size={len(value)}>"

    return repr(value)


def op_signature(op: Any) -> str:
    if not isinstance(op, dict):
        return f"<{type(op).__name__}>"

    parts: list[str] = []

    if "retain" in op:
        parts.append("R")

    if "insert" in op:
        parts.append("I")

    if "delete" in op:
        parts.append("D")

    if "attributes" in op:
        parts.append("A")

    known = {
        "retain",
        "insert",
        "delete",
        "attributes",
    }

    if any(key not in known for key in op):
        parts.append("O")

    return "".join(parts) or "?"


def delta_signature(
    delta: object,
) -> tuple[str, ...]:
    if not isinstance(delta, dict):
        return ()

    ops = delta.get("ops")

    if not isinstance(ops, list):
        return ()

    return tuple(
        op_signature(op)
        for op in ops
    )


def main() -> None:
    paths = sorted(
        RAW_DIR.rglob("*.jsonl")
    )

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/"
        )

    # --------------------------------------------------------------
    # Event counts
    # --------------------------------------------------------------

    text_insert_events = 0
    text_delete_events = 0

    api_text_insert_events = 0
    user_text_insert_events = 0

    events_with_delta = 0
    events_without_delta = 0

    # --------------------------------------------------------------
    # Delta structure
    # --------------------------------------------------------------

    signature_counts: Counter[
        tuple[str, ...]
    ] = Counter()

    event_signature_counts: Counter[
        tuple[str, tuple[str, ...]]
    ] = Counter()

    op_key_counts: Counter[str] = Counter()

    retain_type_counts: Counter[str] = Counter()
    insert_type_counts: Counter[str] = Counter()
    delete_type_counts: Counter[str] = Counter()

    # --------------------------------------------------------------
    # Operation counts
    # --------------------------------------------------------------

    retain_ops = 0
    insert_ops = 0
    delete_ops = 0
    attributes_ops = 0

    multi_op_deltas = 0
    max_ops = 0

    # --------------------------------------------------------------
    # Non-text / unusual cases
    # --------------------------------------------------------------

    non_string_insert_count = 0
    non_int_retain_count = 0
    non_int_delete_count = 0

    unknown_op_key_count = 0

    unusual_examples: list[
        tuple[
            Path,
            int,
            str,
            str,
            str,
        ]
    ] = []

    signature_examples: dict[
        tuple[str, ...],
        tuple[
            Path,
            int,
            str,
            str,
        ],
    ] = {}

    # --------------------------------------------------------------
    # Scan corpus
    # --------------------------------------------------------------

    for session_index, path in enumerate(
        paths,
        start=1,
    ):
        events = load_jsonl_events(path)

        for event in events:
            if event.event_name not in {
                "text-insert",
                "text-delete",
            }:
                continue

            if event.event_name == "text-insert":
                text_insert_events += 1

                if event.source.value == "api":
                    api_text_insert_events += 1

                elif event.source.value == "user":
                    user_text_insert_events += 1

            else:
                text_delete_events += 1

            delta = event.text_delta

            if delta is None:
                events_without_delta += 1
                continue

            events_with_delta += 1

            if not isinstance(delta, dict):
                unusual_examples.append(
                    (
                        path,
                        event.event_num,
                        event.event_name,
                        "delta-not-dict",
                        safe_preview(delta),
                    )
                )
                continue

            ops = delta.get("ops")

            if not isinstance(ops, list):
                unusual_examples.append(
                    (
                        path,
                        event.event_num,
                        event.event_name,
                        "ops-not-list",
                        safe_preview(delta),
                    )
                )
                continue

            signature = delta_signature(
                delta
            )

            signature_counts[
                signature
            ] += 1

            event_signature_counts[
                (
                    event.event_name,
                    signature,
                )
            ] += 1

            signature_examples.setdefault(
                signature,
                (
                    path,
                    event.event_num,
                    event.event_name,
                    safe_preview(delta),
                ),
            )

            max_ops = max(
                max_ops,
                len(ops),
            )

            if len(ops) > 1:
                multi_op_deltas += 1

            for op in ops:
                if not isinstance(op, dict):
                    unusual_examples.append(
                        (
                            path,
                            event.event_num,
                            event.event_name,
                            "op-not-dict",
                            safe_preview(op),
                        )
                    )
                    continue

                for key in op:
                    op_key_counts[key] += 1

                known_keys = {
                    "retain",
                    "insert",
                    "delete",
                    "attributes",
                }

                unknown_keys = sorted(
                    key
                    for key in op
                    if key not in known_keys
                )

                if unknown_keys:
                    unknown_op_key_count += 1

                    unusual_examples.append(
                        (
                            path,
                            event.event_num,
                            event.event_name,
                            (
                                "unknown-op-keys:"
                                + ",".join(
                                    unknown_keys
                                )
                            ),
                            safe_preview(op),
                        )
                    )

                # --------------------------------------------------
                # retain
                # --------------------------------------------------

                if "retain" in op:
                    retain_ops += 1

                    retain_value = op["retain"]

                    retain_type_counts[
                        value_type(
                            retain_value
                        )
                    ] += 1

                    if not isinstance(
                        retain_value,
                        int,
                    ):
                        non_int_retain_count += 1

                        unusual_examples.append(
                            (
                                path,
                                event.event_num,
                                event.event_name,
                                "non-int-retain",
                                safe_preview(op),
                            )
                        )

                # --------------------------------------------------
                # insert
                # --------------------------------------------------

                if "insert" in op:
                    insert_ops += 1

                    insert_value = op["insert"]

                    insert_type_counts[
                        value_type(
                            insert_value
                        )
                    ] += 1

                    if not isinstance(
                        insert_value,
                        str,
                    ):
                        non_string_insert_count += 1

                        unusual_examples.append(
                            (
                                path,
                                event.event_num,
                                event.event_name,
                                "non-string-insert",
                                safe_preview(
                                    insert_value
                                ),
                            )
                        )

                # --------------------------------------------------
                # delete
                # --------------------------------------------------

                if "delete" in op:
                    delete_ops += 1

                    delete_value = op["delete"]

                    delete_type_counts[
                        value_type(
                            delete_value
                        )
                    ] += 1

                    if not isinstance(
                        delete_value,
                        int,
                    ):
                        non_int_delete_count += 1

                        unusual_examples.append(
                            (
                                path,
                                event.event_num,
                                event.event_name,
                                "non-int-delete",
                                safe_preview(op),
                            )
                        )

                if "attributes" in op:
                    attributes_ops += 1

        if session_index % 100 == 0:
            print(
                f"Processed "
                f"{session_index}/{len(paths)} "
                f"sessions..."
            )

    # --------------------------------------------------------------
    # Report
    # --------------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "AgencyTrace — CoAuthor Text Delta Audit"
    )
    print("=" * 78)

    print(
        f"Sessions                       : "
        f"{len(paths)}"
    )

    print()
    print("-" * 78)
    print("TEXT EVENTS")
    print("-" * 78)

    print(
        f"text-insert events              : "
        f"{text_insert_events}"
    )

    print(
        f"  API text-insert              : "
        f"{api_text_insert_events}"
    )

    print(
        f"  USER text-insert             : "
        f"{user_text_insert_events}"
    )

    print(
        f"text-delete events              : "
        f"{text_delete_events}"
    )

    print(
        f"Events with textDelta          : "
        f"{events_with_delta}"
    )

    print(
        f"Events without textDelta       : "
        f"{events_without_delta}"
    )

    print()

    print("-" * 78)
    print("DELTA OPERATIONS")
    print("-" * 78)

    print(
        f"retain operations              : "
        f"{retain_ops}"
    )

    print(
        f"insert operations              : "
        f"{insert_ops}"
    )

    print(
        f"delete operations              : "
        f"{delete_ops}"
    )

    print(
        f"attributes operations          : "
        f"{attributes_ops}"
    )

    print(
        f"Multi-op deltas                : "
        f"{multi_op_deltas}"
    )

    print(
        f"Maximum ops in one delta       : "
        f"{max_ops}"
    )

    print()

    print("-" * 78)
    print("VALUE TYPES")
    print("-" * 78)

    print("retain:")
    for name, count in (
        retain_type_counts.most_common()
    ):
        print(
            f"  {name:<20} {count}"
        )

    print()

    print("insert:")
    for name, count in (
        insert_type_counts.most_common()
    ):
        print(
            f"  {name:<20} {count}"
        )

    print()

    print("delete:")
    for name, count in (
        delete_type_counts.most_common()
    ):
        print(
            f"  {name:<20} {count}"
        )

    print()

    print("-" * 78)
    print("STRUCTURAL EDGE CASES")
    print("-" * 78)

    print(
        f"Non-string inserts             : "
        f"{non_string_insert_count}"
    )

    print(
        f"Non-integer retains            : "
        f"{non_int_retain_count}"
    )

    print(
        f"Non-integer deletes            : "
        f"{non_int_delete_count}"
    )

    print(
        f"Ops with unknown keys          : "
        f"{unknown_op_key_count}"
    )

    print()

    print("-" * 78)
    print("OP KEYS")
    print("-" * 78)

    for key, count in (
        op_key_counts.most_common()
    ):
        print(
            f"{key:<30} {count}"
        )

    print()

    print("-" * 78)
    print("MOST COMMON DELTA SIGNATURES")
    print("-" * 78)

    for signature, count in (
        signature_counts.most_common(20)
    ):
        label = (
            " → ".join(signature)
            if signature
            else "<empty>"
        )

        print(
            f"{label:<35} {count}"
        )

    print()

    print("-" * 78)
    print("SIGNATURES BY EVENT TYPE")
    print("-" * 78)

    for (
        event_name,
        signature,
    ), count in (
        event_signature_counts.most_common(
            30
        )
    ):
        label = (
            " → ".join(signature)
            if signature
            else "<empty>"
        )

        print(
            f"{event_name:<15} "
            f"{label:<30} "
            f"{count}"
        )

    print()

    print("-" * 78)
    print("SAFE SIGNATURE EXAMPLES")
    print("-" * 78)

    for signature, count in (
        signature_counts.most_common(15)
    ):
        (
            path,
            event_num,
            event_name,
            preview,
        ) = signature_examples[signature]

        label = (
            " → ".join(signature)
            if signature
            else "<empty>"
        )

        print()
        print(
            f"{label} (n={count})"
        )

        print(
            f"  file   : {path}"
        )

        print(
            f"  event  : "
            f"{event_num} "
            f"{event_name}"
        )

        print(
            f"  preview: {preview}"
        )

    print()

    print("-" * 78)
    print("UNUSUAL DELTAS — SAFE PREVIEW")
    print("-" * 78)

    print(
        f"Unusual cases detected         : "
        f"{len(unusual_examples)}"
    )

    for (
        path,
        event_num,
        event_name,
        reason,
        preview,
    ) in unusual_examples[:30]:
        print()
        print(path)

        print(
            f"  event   : "
            f"{event_num} "
            f"{event_name}"
        )

        print(
            f"  reason  : {reason}"
        )

        print(
            f"  preview : {preview}"
        )

    print()
    print("=" * 78)
    print(
        "Text delta audit completed."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()