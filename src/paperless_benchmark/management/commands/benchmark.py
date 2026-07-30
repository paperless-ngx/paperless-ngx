# src/paperless_benchmark/management/commands/benchmark.py
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = "Seed, run, and profile paperless-ngx performance benchmarks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "action",
            choices=["seed", "run", "profile", "list-scenarios"],
            help="Which benchmark action to perform.",
        )
        parser.add_argument(
            "scenario",
            nargs="?",
            default=None,
            help="Scenario name (required for `profile`; see `list-scenarios`).",
        )
        parser.add_argument(
            "--tier",
            choices=["home", "medium", "large"],
            default="medium",
            help="Dataset scale tier for `seed` and `profile` (default: medium).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="For `seed`: truncate existing benchmark data first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="RNG seed for reproducible datasets (default: 42).",
        )
        parser.add_argument(
            "--repeat",
            type=int,
            default=5,
            help="Number of timed repetitions for `run`/`profile` (default: 5).",
        )
        parser.add_argument(
            "--label",
            default="baseline",
            help="Free-text tag for a `run`, printed and recorded in history only.",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            default=False,
            help="For `profile`: also capture and print the query plan.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        action = options["action"]
        if action == "seed":
            self._handle_seed(options)
        elif action == "run":
            self._handle_run(options)
        elif action == "profile":
            self._handle_profile(options)
        else:
            self._handle_list_scenarios()

    def _handle_seed(self, options: dict[str, Any]) -> None:
        from paperless_benchmark.db import reset_benchmark_data
        from paperless_benchmark.seeding import seed_benchmark_dataset

        if options["reset"]:
            self.stdout.write("Resetting existing benchmark data...")
            reset_benchmark_data()

        data = seed_benchmark_dataset(options["tier"], seed=options["seed"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded tier={options['tier']!r}: {len(data.documents)} documents, "
                f"{len(data.users)} users, {len(data.groups)} groups.",
            ),
        )

    def _handle_run(self, options: dict[str, Any]) -> None:
        from django.contrib.auth import get_user_model

        from paperless_benchmark.endpoints import run_endpoint_benchmarks
        from paperless_benchmark.results import append_history

        user_model = get_user_model()
        try:
            perf_target = user_model.objects.get(username="perf_target")
            perf_admin = user_model.objects.get(username="perf_admin")
        except user_model.DoesNotExist as e:
            raise CommandError(
                "No benchmark dataset found. Run `manage.py benchmark seed` first.",
            ) from e

        results = run_endpoint_benchmarks(
            perf_target=perf_target,
            perf_admin=perf_admin,
            repeat=options["repeat"],
        )

        self.stdout.write(f"# label={options['label']} repeat={options['repeat']}")
        self.stdout.write(
            f"{'user':7s} {'endpoint':20s} {'queries':>8s} "
            f"{'min_ms':>9s} {'median_ms':>10s} {'max_ms':>9s}",
        )
        for r in results:
            self.stdout.write(
                f"{r.user_label:7s} {r.endpoint_name:20s} {r.query_count:8d} "
                f"{r.min_ms:9.1f} {r.median_ms:10.1f} {r.max_ms:9.1f}",
            )
            append_history(
                {
                    "mode": "run",
                    "label": options["label"],
                    "user": r.user_label,
                    "endpoint": r.endpoint_name,
                    "query_count": r.query_count,
                    "min_ms": r.min_ms,
                    "median_ms": r.median_ms,
                    "max_ms": r.max_ms,
                },
            )

    def _handle_profile(self, options: dict[str, Any]) -> None:
        from paperless_benchmark.db import capture_explain
        from paperless_benchmark.harness import run_profile
        from paperless_benchmark.results import append_history
        from paperless_benchmark.scenarios import get as get_scenario
        from paperless_benchmark.seeding import seed_benchmark_dataset

        if not options["scenario"]:
            raise CommandError(
                "`profile` requires a scenario name; see `list-scenarios`.",
            )

        scenario = get_scenario(options["scenario"])
        data = seed_benchmark_dataset(options["tier"], seed=options["seed"])

        profile = run_profile(lambda: scenario.run(data), repeat=options["repeat"])
        self.stdout.write(
            f"{scenario.name}: best={profile.best_seconds:.4f}s "
            f"queries={profile.query_count} (tier={options['tier']})",
        )

        if options["explain"] and scenario.queryset_for_explain is not None:
            plan = capture_explain(scenario.queryset_for_explain(data))
            self.stdout.write(plan)

        append_history(
            {
                "mode": "profile",
                "scenario": scenario.name,
                "tier": options["tier"],
                "best_seconds": profile.best_seconds,
                "query_count": profile.query_count,
            },
        )

    def _handle_list_scenarios(self) -> None:
        from paperless_benchmark.scenarios import all_scenarios

        for scenario in all_scenarios():
            self.stdout.write(f"{scenario.name}: {scenario.describe}")
