#!/usr/bin/env python3
import argparse
import json
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple


Cells = List[List[str]]
LimitMap = Dict[int, int]
OutputFormat = str


def _stringify(value: Any) -> str:
    """Return a stable single-cell string for scalar or nested values."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _normalize_rows(headers: Sequence[Any], rows: Sequence[Any]) -> Tuple[List[str], Cells]:
    """Normalize row sequences to string cells."""
    header_names = [_stringify(header) for header in headers]
    normalized_rows: Cells = []

    for row in rows:
        row_values = list(row) if isinstance(row, (list, tuple)) else [row]
        cells = [_stringify(value) for value in row_values]
        if len(cells) < len(header_names):
            cells.extend([""] * (len(header_names) - len(cells)))
        normalized_rows.append(cells[:len(header_names)])

    return header_names, normalized_rows


def _is_table_matrix(data: Any) -> bool:
    """Return true when data is a table matrix with a header row first."""
    return (
        isinstance(data, list)
        and bool(data)
        and isinstance(data[0], list)
        and bool(data[0])
    )


def _table_from_matrix(data: Any) -> Tuple[List[str], Cells]:
    """Convert the strict table matrix format to headers and rows."""
    if not _is_table_matrix(data):
        raise ValueError("Table input must be a JSON list whose first row is the headers")
    return _normalize_rows(data[0], data[1:])


def _named_table_items(data: Any) -> List[Tuple[str, Any]]:
    """Return named table items, ignoring underscore metadata keys."""
    if not isinstance(data, dict):
        return []
    return [
        (_stringify(name), table_data)
        for name, table_data in data.items()
        if not _stringify(name).startswith("_")
    ]


def _load_json_file(filepath: str) -> Any:
    """Load raw JSON data from a file."""
    with open(filepath, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def parse_json_file(filepath: str) -> Any:
    return _load_json_file(filepath)


def parse_json_text(raw_text: str) -> Any:
    return json.loads(raw_text)


def select_json_path(data: Any, path: Optional[str], output_format: OutputFormat) -> Any:
    """Select one JSON path when requested."""
    if path is None:
        return data
    if not isinstance(data, dict):
        raise ValueError("--path requires object input")

    if path in data:
        selected = data[path]
        return selected if output_format == "one-liner" else {path: selected}

    selected = data
    for part in path.split("."):
        if not isinstance(selected, dict) or part not in selected:
            raise ValueError(f"JSON path not found: {path}")
        selected = selected[part]
    return selected if output_format == "one-liner" else {path.split(".")[-1]: selected}


class TextTable:
    def __init__(self, headers: Sequence[Any], rows: Sequence[Sequence[Any]]) -> None:
        self.headers = [_stringify(header) for header in headers]
        self.rows = [[_stringify(cell) for cell in row] for row in rows]

    def apply_cell_wrap(self, limit: Optional[int]) -> None:
        if not limit or limit <= 0:
            return
        for row_idx, col_idx, value in self._iter_cells():
            if self._longest_line_len(value) > limit:
                self._set_cell(row_idx, col_idx, self._wrap_text(value, limit))

    def apply_column_wrap(self, limits: LimitMap) -> None:
        for col_idx, limit in limits.items():
            if limit <= 0:
                continue
            for row_idx, _, value in self._iter_cells_for_column(col_idx):
                if self._longest_line_len(value) > limit:
                    self._set_cell(row_idx, col_idx, self._wrap_text(value, limit))

    def apply_row_wrap(self, limit: Optional[int]) -> None:
        if not limit or limit <= 0:
            return

        previous_target: Optional[Tuple[int, int, int]] = None
        max_iterations = 1000
        for _ in range(max_iterations):
            if self._max_rendered_line_len(limit) <= limit:
                return

            row_idx, col_idx, value, value_len = self._longest_cell()
            if value_len <= 1:
                return

            next_width = max(1, value_len // 2)
            target = (row_idx, col_idx, next_width)
            if target == previous_target:
                return

            self._set_cell(row_idx, col_idx, self._wrap_text(value, next_width))
            previous_target = target

    def apply_wrapping(
        self,
        cell_wrapped_limit: Optional[int],
        col_wrapped_limits: LimitMap,
        row_wrapped_limit: Optional[int],
    ) -> None:
        self.apply_cell_wrap(cell_wrapped_limit)
        self.apply_column_wrap(col_wrapped_limits)
        self.apply_row_wrap(row_wrapped_limit)

    def render(self, no_border: bool = False, row_wrapped_limit: Optional[int] = None) -> str:
        if no_border:
            return _render_plain_table(self.headers, self.rows)
        return create_details_table_from_data(self.headers, self.rows, row_wrapped_limit=row_wrapped_limit)

    def _iter_cells(self) -> List[Tuple[int, int, str]]:
        cells: List[Tuple[int, int, str]] = []
        for col_idx, value in enumerate(self.headers):
            cells.append((-1, col_idx, value))
        for row_idx, row in enumerate(self.rows):
            for col_idx, value in enumerate(row):
                cells.append((row_idx, col_idx, value))
        return cells

    def _iter_cells_for_column(self, col_idx: int) -> List[Tuple[int, int, str]]:
        cells = [(-1, col_idx, self.headers[col_idx])]
        for row_idx, row in enumerate(self.rows):
            cells.append((row_idx, col_idx, row[col_idx]))
        return cells

    def _set_cell(self, row_idx: int, col_idx: int, value: str) -> None:
        if row_idx < 0:
            self.headers[col_idx] = value
            return
        self.rows[row_idx][col_idx] = value

    def _longest_cell(self) -> Tuple[int, int, str, int]:
        longest = (-1, 0, "", 0)
        for row_idx, col_idx, value in self._iter_cells():
            value_len = self._longest_line_len(value)
            if value_len > longest[3]:
                longest = (row_idx, col_idx, value, value_len)
        return longest

    def _max_rendered_line_len(self, row_wrapped_limit: Optional[int]) -> int:
        return max((len(line) for line in self.render(row_wrapped_limit=row_wrapped_limit).splitlines()), default=0)

    @staticmethod
    def _longest_line_len(value: str) -> int:
        return max((len(line) for line in value.splitlines()), default=0)

    @staticmethod
    def _wrap_text(value: str, limit: int) -> str:
        wrapped_lines: List[str] = []
        for line in value.splitlines() or [""]:
            if len(line) <= limit:
                wrapped_lines.append(line)
                continue
            wrapped_lines.extend(textwrap.wrap(
                line,
                width=limit,
                break_long_words=True,
                break_on_hyphens=False,
            ))
        return "\n".join(wrapped_lines)


def _parse_column_limits(raw_limits: Sequence[str], headers: Sequence[str]) -> LimitMap:
    limits: LimitMap = {}
    if not raw_limits:
        return limits

    for raw_limit in raw_limits:
        for part in raw_limit.split(","):
            stripped = part.strip()
            if not stripped:
                continue
            if re.fullmatch(r"\d+", stripped):
                for col_idx in range(len(headers)):
                    limits[col_idx] = int(stripped)
                continue
            match = re.fullmatch(r"([^=:]+)\s*[=:]\s*(\d+)", stripped)
            if not match:
                raise ValueError(f"Invalid column limit: {stripped!r}")
            key, limit_text = match.groups()
            col_idx = _resolve_column(key.strip(), headers)
            limits[col_idx] = int(limit_text)
    return limits


def _resolve_column(key: str, headers: Sequence[str]) -> int:
    if re.fullmatch(r"\d+", key):
        col_idx = int(key)
        if 0 <= col_idx < len(headers):
            return col_idx
        raise ValueError(f"Column index out of range: {key}")
    if key in headers:
        return list(headers).index(key)
    raise ValueError(f"Unknown column name: {key}")


def create_table_from_data(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    row_wrapped_limit: Optional[int] = 250,
    cell_wrapped_limit: Optional[int] = None,
    col_wrapped_limits: Optional[LimitMap] = None,
    no_border: bool = False,
) -> str:
    """Create a formatted table from headers and rows."""
    table = TextTable(headers, rows)
    table.apply_wrapping(cell_wrapped_limit, col_wrapped_limits or {}, row_wrapped_limit)
    return create_details_table_from_data(
        table.headers,
        table.rows,
        row_wrapped_limit=row_wrapped_limit,
        no_border=no_border,
    )


def _wrap_detail_text(value: str, width: int) -> List[str]:
    if not value:
        return [""]
    if len(value) <= width:
        return [value]

    if value.startswith("TAGS:"):
        parts = value.split(",")
        lines: List[str] = []
        current = parts[0]
        for part in parts[1:]:
            candidate = f"{current},{part}"
            if len(candidate) <= width:
                current = candidate
                continue
            lines.append(f"{current},")
            current = part
        lines.append(current)
        return lines

    wrapped = textwrap.wrap(
        value,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return [""]
    if max(len(line) for line in wrapped) <= width:
        return wrapped
    return textwrap.wrap(value, width=width, break_long_words=True, break_on_hyphens=False)


def _detail_lines(headers: Sequence[str], row: Sequence[str], width: int) -> List[str]:
    lines: List[str] = []
    for header, value in zip(headers[1:], row[1:]):
        prefix = f"{header}: "
        text_width = max(20, width - len(prefix))
        wrapped = _wrap_detail_text(value, text_width)
        lines.append(f"{prefix}{wrapped[0]}")
        lines.extend(f"{' ' * len(prefix)}{part}" for part in wrapped[1:])
    return lines or [""]


def create_details_table_from_data(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    row_wrapped_limit: Optional[int] = 160,
    no_border: bool = False,
) -> str:
    """Create a compact two-column details table from headers and rows."""
    header_names, normalized_rows = _normalize_rows(headers, rows)
    if not header_names:
        return ""

    target_width = row_wrapped_limit if row_wrapped_limit and row_wrapped_limit > 0 else 160
    max_title = max([len(header_names[0])] + [len(row[0]) for row in normalized_rows if row])
    title_width = max(max_title, 24)
    detail_width = max(20, target_width - title_width - 7)
    if no_border:
        return _render_details_no_border(header_names, normalized_rows, title_width, detail_width)

    separator = f"+-{'-' * title_width}-+-{'-' * detail_width}-+"
    lines = [
        separator,
        f"| {header_names[0]:<{title_width}} | {'Details':<{detail_width}} |",
        separator,
    ]

    for row in normalized_rows:
        title_lines = _wrap_detail_text(row[0] if row else "", title_width)
        details = _detail_lines(header_names, row, detail_width)
        row_height = max(len(title_lines), len(details))
        for idx in range(row_height):
            title = title_lines[idx] if idx < len(title_lines) else ""
            detail = details[idx] if idx < len(details) else ""
            lines.append(f"| {title:<{title_width}} | {detail:<{detail_width}} |")
        lines.append(separator)

    return "\n".join(lines)


def _render_details_no_border(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    title_width: int,
    detail_width: int,
) -> str:
    lines = [f"{headers[0]:<{title_width}}  {'Details':<{detail_width}}"]
    for row in rows:
        title_lines = _wrap_detail_text(row[0] if row else "", title_width)
        details = _detail_lines([_stringify(header) for header in headers], row, detail_width)
        row_height = max(len(title_lines), len(details))
        for idx in range(row_height):
            title = title_lines[idx] if idx < len(title_lines) else ""
            detail = details[idx] if idx < len(details) else ""
            lines.append(f"{title:<{title_width}}  {detail:<{detail_width}}")
    return "\n".join(line.rstrip() for line in lines)


def _render_plain_table(headers: Sequence[Any], rows: Sequence[Sequence[Any]]) -> str:
    header_names, normalized_rows = _normalize_rows(headers, rows)
    widths = [
        max([len(header)] + [len(row[idx]) for row in normalized_rows])
        for idx, header in enumerate(header_names)
    ]
    lines = ["  ".join(header.ljust(widths[idx]) for idx, header in enumerate(header_names))]
    lines.extend(
        "  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))
        for row in normalized_rows
    )
    return "\n".join(line.rstrip() for line in lines)


def _render_matrix_table(headers: Sequence[Any], rows: Sequence[Sequence[Any]]) -> str:
    """Render a bordered table that preserves every input column."""
    header_names, normalized_rows = _normalize_rows(headers, rows)
    all_rows = [header_names, *normalized_rows]
    widths = [
        max(
            len(line)
            for row in all_rows
            for line in (row[column].splitlines() or [""])
        )
        for column in range(len(header_names))
    ]
    separator = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def render_row(row: Sequence[str]) -> List[str]:
        cell_lines = [cell.splitlines() or [""] for cell in row]
        height = max(len(lines) for lines in cell_lines)
        rendered = []
        for line_index in range(height):
            cells = [
                lines[line_index] if line_index < len(lines) else ""
                for lines in cell_lines
            ]
            rendered.append(
                "| "
                + " | ".join(
                    cell.ljust(widths[index])
                    for index, cell in enumerate(cells)
                )
                + " |"
            )
        return rendered

    lines = [separator, *render_row(header_names), separator]
    for row in normalized_rows:
        lines.extend(render_row(row))
        lines.append(separator)
    return "\n".join(lines)


def create_matrix_table_from_data(
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    cell_wrapped_limit: Optional[int] = None,
    col_wrapped_limits: Optional[LimitMap] = None,
) -> str:
    """Create a bordered multi-column table with explicit wrapping."""
    table = TextTable(headers, rows)
    table.apply_cell_wrap(cell_wrapped_limit)
    table.apply_column_wrap(col_wrapped_limits or {})
    return _render_matrix_table(table.headers, table.rows)


def create_named_tables_from_data(
    data: Any,
    row_wrapped_limit: Optional[int] = 250,
    cell_wrapped_limit: Optional[int] = None,
    raw_col_wrapped_limits: Optional[Sequence[str]] = None,
    no_border: bool = False,
) -> str:
    """Create output from a dict of table-name to table-matrix entries."""
    table_items = _named_table_items(data)
    if not table_items:
        raise ValueError("Named table input must contain at least one table")

    lines: List[str] = []
    for table_name, table_data in table_items:
        headers, rows = _table_from_matrix(table_data)
        if not headers:
            raise ValueError(f"Table {table_name!r} has no headers")

        if lines:
            lines.append("")
        lines.extend([f"### {table_name}", ""])
        col_limits = _parse_column_limits(raw_col_wrapped_limits or [], headers)
        lines.extend([
            create_table_from_data(
                headers,
                rows,
                row_wrapped_limit=row_wrapped_limit,
                cell_wrapped_limit=cell_wrapped_limit,
                col_wrapped_limits=col_limits,
                no_border=no_border,
            ),
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def create_output_from_data(
    data: Any,
    row_wrapped_limit: Optional[int] = 250,
    cell_wrapped_limit: Optional[int] = None,
    raw_col_wrapped_limits: Optional[Sequence[str]] = None,
    no_border: bool = False,
) -> str:
    """Create output from one table matrix or a named-table object."""
    if isinstance(data, dict):
        return create_named_tables_from_data(
            data,
            row_wrapped_limit=row_wrapped_limit,
            cell_wrapped_limit=cell_wrapped_limit,
            raw_col_wrapped_limits=raw_col_wrapped_limits,
            no_border=no_border,
        )

    headers, rows = _table_from_matrix(data)
    if not headers or not rows:
        raise ValueError("No data to display")

    col_limits = _parse_column_limits(raw_col_wrapped_limits or [], headers)
    return create_table_from_data(
        headers,
        rows,
        row_wrapped_limit=row_wrapped_limit,
        cell_wrapped_limit=cell_wrapped_limit,
        col_wrapped_limits=col_limits,
        no_border=no_border,
    )


def create_one_liner_output(data: Any, row_wrapped_limit: Optional[int] = 250) -> str:
    """Create plain text output from one selected string value."""
    if not isinstance(data, str):
        raise ValueError("--format one-liner requires --path to select exactly one string value")
    if not row_wrapped_limit or row_wrapped_limit <= 0:
        return data.rstrip() + "\n"

    lines: List[str] = []
    for line in data.splitlines() or [""]:
        if len(line) <= row_wrapped_limit:
            lines.append(line)
            continue
        wrapped = textwrap.wrap(
            line,
            width=row_wrapped_limit,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate formatted plain-text tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file", dest="json_file", help="JSON file path")
    input_group.add_argument("--json-string", dest="json_text", help="Raw JSON string")

    parser.add_argument("--path", default=None,
                        help="Render one value from a JSON path")
    parser.add_argument("--format", choices=["matrix", "no-border", "one-liner"],
                        default=None, help="Output format; omitted renders the default bordered table")
    parser.add_argument("--row-wrapped-limit", type=int,
                        default=250, help="Max rendered line length; 0 disables row wrapping")
    parser.add_argument("--cell-wrapped-limit", type=int,
                        default=None, help="Max line length for every cell before row wrapping")
    parser.add_argument("--col-wrapped-limit", action="append",
                        default=[], help="Column wrap limit: 40, Name=40, 0=40, or comma list")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        if args.json_file:
            data = parse_json_file(args.json_file)
        else:
            data = parse_json_text(args.json_text)
        data = select_json_path(data, args.path, args.format)

        if args.format == "one-liner":
            output = create_one_liner_output(data, row_wrapped_limit=args.row_wrapped_limit)
        elif args.format == "matrix":
            headers, rows = _table_from_matrix(data)
            output = create_matrix_table_from_data(
                headers,
                rows,
                cell_wrapped_limit=args.cell_wrapped_limit,
                col_wrapped_limits=_parse_column_limits(args.col_wrapped_limit, headers),
            )
        else:
            output = create_output_from_data(
                data,
                row_wrapped_limit=args.row_wrapped_limit,
                cell_wrapped_limit=args.cell_wrapped_limit,
                raw_col_wrapped_limits=args.col_wrapped_limit,
                no_border=args.format == "no-border",
            )
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
