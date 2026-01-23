# /// script
# dependencies = [
#   "rich",
#   "ijson",
#   "typer-slim",
# ]
# ///

import json
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from typing import TypedDict

import typer
from rich.console import Console
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.table import Table

try:
    import ijson  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "ijson is required for migration transform. "
        "Install dependencies (e.g., `uv pip install ijson`).",
    ) from exc

app = typer.Typer(add_completion=False)
console = Console()


class FixtureObject(TypedDict):
    model: str
    pk: int
    fields: dict[str, Any]


TransformFn = Callable[[FixtureObject], FixtureObject]


def transform_documents_document(obj: FixtureObject) -> FixtureObject:
    fields: dict[str, Any] = obj["fields"]
    fields.pop("storage_type", None)
    content: Any = fields.get("content")
    fields["content_length"] = len(content) if isinstance(content, str) else 0
    return obj


TRANSFORMS: dict[str, TransformFn] = {
    "documents.document": transform_documents_document,
}


def validate_output(value: Path) -> Path:
    if value.exists():
        raise typer.BadParameter(f"Output file '{value}' already exists.")
    return value


@app.command()
def migrate(
    input_path: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        callback=validate_output,
    ),
) -> None:
    """
    Process JSON fixtures with detailed summary and timing.
    """
    if input_path.resolve() == output_path.resolve():
        console.print(
            "[bold red]Error:[/bold red] Input and output paths cannot be the same file.",
        )
        raise typer.Exit(code=1)

    stats: Counter[str] = Counter()
    total_processed: int = 0
    start_time: float = time.perf_counter()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:,} rows"),
        TimeElapsedColumn(),
        console=console,
    )

    with (
        progress,
        input_path.open("rb") as infile,
        output_path.open("w", encoding="utf-8") as outfile,
    ):
        task = progress.add_task("Processing fixture", start=True)
        outfile.write("[\n")
        first: bool = True

        for i, obj in enumerate(ijson.items(infile, "item")):
            fixture: FixtureObject = obj
            model: str = fixture["model"]
            total_processed += 1

            transform: TransformFn | None = TRANSFORMS.get(model)
            if transform:
                fixture = transform(fixture)
                stats[model] += 1

            if not first:
                outfile.write(",\n")
            first = False

            json.dump(fixture, outfile, ensure_ascii=False)
            progress.advance(task, 1)

        outfile.write("\n]\n")

    end_time: float = time.perf_counter()
    duration: float = end_time - start_time

    # Final Statistics Table
    console.print("\n[bold green]Processing Complete[/bold green]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total Time", f"{duration:.2f} seconds")
    table.add_row("Total Processed", f"{total_processed:,} rows")
    table.add_row(
        "Processing Speed",
        f"{total_processed / duration:.0f} rows/sec" if duration > 0 else "N/A",
    )

    for model, count in stats.items():
        table.add_row(f"Transformed: {model}", f"{count:,}")

    console.print(table)


if __name__ == "__main__":
    app()
