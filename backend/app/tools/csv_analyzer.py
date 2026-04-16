import csv
from pathlib import Path
from typing import Any, Dict, List

from .base import Tool, ToolContext


class CsvAnalyzerTool(Tool):
    name = "csv_analyzer"
    description = (
        "Analyze a CSV file. Returns per-column statistics including top values, "
        "min/max/avg for numeric columns, and simple trend direction."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the CSV file to analyze.",
            },
            "top_n": {
                "type": "integer",
                "description": "Number of top values to return per column.",
                "default": 5,
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum rows to read (for large files).",
                "default": 5000,
            },
        },
        "required": ["path"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = Path(params["path"]).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        top_n = int(params.get("top_n", 5))
        max_rows = int(params.get("max_rows", 5000))

        counts: Dict[str, Dict[str, int]] = {}
        numeric_values: Dict[str, List[float]] = {}
        ordered_numeric: Dict[str, List[float]] = {}  # preserves row order for trend
        rows = 0

        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row.")
            for row in reader:
                rows += 1
                for col in reader.fieldnames:
                    value = (row.get(col) or "").strip()
                    if value == "":
                        continue
                    counts.setdefault(col, {})
                    counts[col][value] = counts[col].get(value, 0) + 1
                    try:
                        num = float(value)
                        numeric_values.setdefault(col, [])
                        numeric_values[col].append(num)
                        ordered_numeric.setdefault(col, [])
                        ordered_numeric[col].append(num)
                    except ValueError:
                        pass
                if rows >= max_rows:
                    break

        columns: Dict[str, Dict[str, Any]] = {}
        for col, value_counts in counts.items():
            top_values = sorted(
                value_counts.items(), key=lambda item: item[1], reverse=True
            )[:top_n]
            stats: Dict[str, Any] = {
                "top_values": [
                    {"value": value, "count": count} for value, count in top_values
                ]
            }
            numbers = numeric_values.get(col, [])
            if numbers:
                avg = sum(numbers) / len(numbers)
                stats.update(
                    {
                        "min": round(min(numbers), 2),
                        "max": round(max(numbers), 2),
                        "avg": round(avg, 2),
                        "sum": round(sum(numbers), 2),
                    }
                )
                # Simple trend: compare first-half average vs second-half average
                ordered = ordered_numeric.get(col, [])
                if len(ordered) >= 4:
                    mid = len(ordered) // 2
                    first_avg = sum(ordered[:mid]) / mid
                    second_avg = sum(ordered[mid:]) / (len(ordered) - mid)
                    if second_avg > first_avg * 1.02:
                        stats["trend"] = "increasing"
                    elif second_avg < first_avg * 0.98:
                        stats["trend"] = "decreasing"
                    else:
                        stats["trend"] = "stable"
            columns[col] = stats

        return {
            "path": str(path),
            "rows_analyzed": rows,
            "column_count": len(columns),
            "columns": columns,
        }
