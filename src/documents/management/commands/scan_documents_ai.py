"""
Management command to apply AI scanner to existing documents.

This command allows batch processing of documents through the AI scanner,
enabling metadata suggestions for documents that were added before the
AI scanner was implemented or to re-scan documents with updated AI models.
"""

import logging
from datetime import datetime
from typing import Any

import tqdm
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from documents.ai_scanner import AIScanResult
from documents.ai_scanner import get_ai_scanner
from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag

logger = logging.getLogger("paperless.management.scan_documents_ai")


class Command(ProgressBarMixin, BaseCommand):
    """
    Management command to apply AI scanner to existing documents.

    This command processes existing documents through the comprehensive AI scanner
    to generate metadata suggestions (tags, correspondents, document types, etc.).
    """

    help = (
        "Apply AI scanner to existing documents to generate metadata suggestions. "
        "Supports filtering by document type, date range, and auto-apply for high "
        "confidence suggestions. Use --dry-run to preview suggestions without applying."
    )

    def add_arguments(self, parser):
        """Add command line arguments."""
        # Filtering options
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Scan all documents in the system",
        )

        parser.add_argument(
            "--filter-by-type",
            type=int,
            nargs="+",
            metavar="TYPE_ID",
            help="Filter documents by document type ID(s). Can specify multiple IDs.",
        )

        parser.add_argument(
            "--date-range",
            nargs=2,
            metavar=("START_DATE", "END_DATE"),
            help=(
                "Filter documents by creation date range. "
                "Format: YYYY-MM-DD YYYY-MM-DD. Example: 2024-01-01 2024-12-31"
            ),
        )

        parser.add_argument(
            "--id-range",
            nargs=2,
            type=int,
            metavar=("START_ID", "END_ID"),
            help="Filter documents by ID range. Example: 1 100",
        )

        # Processing options
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview suggestions without applying any changes",
        )

        parser.add_argument(
            "--auto-apply-high-confidence",
            action="store_true",
            default=False,
            help=(
                "Automatically apply suggestions with high confidence (>=80%%). "
                "Lower confidence suggestions will still be shown for review."
            ),
        )

        parser.add_argument(
            "--confidence-threshold",
            type=float,
            default=0.60,
            help=(
                "Minimum confidence threshold for showing suggestions (0.0-1.0). "
                "Default: 0.60 (60%%)"
            ),
        )

        # Progress bar
        self.add_argument_progress_bar_mixin(parser)

        # Batch size for processing
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of documents to process in memory at once. Default: 100",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        self.handle_progress_bar_mixin(**options)

        # Validate arguments
        self._validate_arguments(options)

        # Get queryset based on filters
        queryset = self._build_queryset(options)
        document_count = queryset.count()

        if document_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No documents found matching the specified filters."
                ),
            )
            return

        # Initialize AI scanner
        try:
            scanner = get_ai_scanner()
        except Exception as e:
            raise CommandError(f"Failed to initialize AI scanner: {e}")

        # Display operation summary
        self._display_operation_summary(options, document_count)

        # Process documents
        results = self._process_documents(
            queryset=queryset,
            scanner=scanner,
            options=options,
        )

        # Display final summary
        self._display_final_summary(results, options)

    def _validate_arguments(self, options):
        """Validate command line arguments."""
        # At least one filter must be specified
        if not any(
            [
                options["all"],
                options["filter_by_type"],
                options["date_range"],
                options["id_range"],
            ]
        ):
            raise CommandError(
                "You must specify at least one filter: "
                "--all, --filter-by-type, --date-range, or --id-range",
            )

        # Validate confidence threshold
        if not 0.0 <= options["confidence_threshold"] <= 1.0:
            raise CommandError("Confidence threshold must be between 0.0 and 1.0")

        # Validate date range format
        if options["date_range"]:
            try:
                start_str, end_str = options["date_range"]
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")

                if start_date > end_date:
                    raise CommandError("Start date must be before end date")

                # Store parsed dates for later use
                options["_parsed_start_date"] = timezone.make_aware(start_date)
                options["_parsed_end_date"] = timezone.make_aware(
                    end_date.replace(hour=23, minute=59, second=59),
                )
            except ValueError as e:
                raise CommandError(
                    f"Invalid date format. Use YYYY-MM-DD. Error: {e}",
                )

        # Validate document types exist
        if options["filter_by_type"]:
            for type_id in options["filter_by_type"]:
                if not DocumentType.objects.filter(pk=type_id).exists():
                    raise CommandError(
                        f"Document type with ID {type_id} does not exist",
                    )

    def _build_queryset(self, options):
        """Build document queryset based on filters."""
        queryset = Document.objects.all()

        # Filter by document type
        if options["filter_by_type"]:
            queryset = queryset.filter(document_type__id__in=options["filter_by_type"])

        # Filter by date range
        if options["date_range"]:
            queryset = queryset.filter(
                created__gte=options["_parsed_start_date"],
                created__lte=options["_parsed_end_date"],
            )

        # Filter by ID range
        if options["id_range"]:
            start_id, end_id = options["id_range"]
            queryset = queryset.filter(id__gte=start_id, id__lte=end_id)

        # Order by ID for consistent processing
        return queryset.order_by("id")

    def _display_operation_summary(self, options, document_count):
        """Display summary of the operation before starting."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("AI Document Scanner - Batch Processing"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        # Display filters
        self.stdout.write("Filters applied:")
        if options["all"]:
            self.stdout.write("  • Processing ALL documents")
        if options["filter_by_type"]:
            type_ids = ", ".join(str(tid) for tid in options["filter_by_type"])
            self.stdout.write(f"  • Document types: {type_ids}")
        if options["date_range"]:
            start, end = options["date_range"]
            self.stdout.write(f"  • Date range: {start} to {end}")
        if options["id_range"]:
            start, end = options["id_range"]
            self.stdout.write(f"  • ID range: {start} to {end}")

        # Display processing mode
        self.stdout.write("\nProcessing mode:")
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("  • DRY RUN - No changes will be applied")
            )
        elif options["auto_apply_high_confidence"]:
            self.stdout.write("  • Auto-apply high confidence suggestions (≥80%)")
        else:
            self.stdout.write("  • Preview mode - No changes will be applied")

        self.stdout.write(
            f"  • Confidence threshold: {options['confidence_threshold']:.0%}",
        )

        # Display document count
        self.stdout.write(
            f"\n{self.style.SUCCESS('Documents to process:')} {document_count}",
        )
        self.stdout.write("\n" + "=" * 70 + "\n")

    def _process_documents(
        self,
        queryset,
        scanner,
        options,
    ) -> dict[str, Any]:
        """
        Process documents through the AI scanner.

        Returns:
            Dictionary with processing results and statistics
        """
        results = {
            "processed": 0,
            "errors": 0,
            "suggestions_generated": 0,
            "auto_applied": 0,
            "documents_with_suggestions": [],
            "error_documents": [],
        }

        batch_size = options["batch_size"]
        confidence_threshold = options["confidence_threshold"]
        auto_apply = options["auto_apply_high_confidence"] and not options["dry_run"]

        # Process in batches
        total_docs = queryset.count()

        for i in tqdm.tqdm(
            range(0, total_docs, batch_size),
            disable=self.no_progress_bar,
            desc="Processing batches",
        ):
            batch = queryset[i : i + batch_size]

            for document in batch:
                try:
                    # Get document text
                    document_text = document.content or ""

                    if not document_text:
                        logger.warning(
                            f"Document {document.id} has no text content, skipping",
                        )
                        continue

                    # Scan document
                    scan_result = scanner.scan_document(
                        document=document,
                        document_text=document_text,
                    )

                    # Filter results by confidence threshold
                    filtered_result = self._filter_by_confidence(
                        scan_result,
                        confidence_threshold,
                    )

                    # Count suggestions
                    suggestion_count = self._count_suggestions(filtered_result)

                    if suggestion_count > 0:
                        results["suggestions_generated"] += suggestion_count

                        # Apply or store suggestions
                        if auto_apply:
                            applied = scanner.apply_scan_results(
                                document=document,
                                scan_result=filtered_result,
                                auto_apply=True,
                            )
                            results["auto_applied"] += len(
                                applied.get("applied", {}).get("tags", []),
                            )

                        # Store for summary
                        results["documents_with_suggestions"].append(
                            {
                                "id": document.id,
                                "title": document.title,
                                "suggestions": filtered_result.to_dict(),
                                "applied": applied if auto_apply else None,
                            }
                        )

                    results["processed"] += 1

                except Exception as e:
                    logger.exception(
                        f"Error processing document {document.id}: {e}",
                    )
                    results["errors"] += 1
                    results["error_documents"].append(
                        {
                            "id": document.id,
                            "title": document.title,
                            "error": str(e),
                        }
                    )

        return results

    def _filter_by_confidence(
        self,
        scan_result: AIScanResult,
        threshold: float,
    ) -> AIScanResult:
        """Filter scan results by confidence threshold."""
        filtered = AIScanResult()

        # Filter tags
        filtered.tags = [
            (tag_id, conf) for tag_id, conf in scan_result.tags if conf >= threshold
        ]

        # Filter correspondent
        if scan_result.correspondent:
            _corr_id, conf = scan_result.correspondent
            if conf >= threshold:
                filtered.correspondent = scan_result.correspondent

        # Filter document type
        if scan_result.document_type:
            _type_id, conf = scan_result.document_type
            if conf >= threshold:
                filtered.document_type = scan_result.document_type

        # Filter storage path
        if scan_result.storage_path:
            _path_id, conf = scan_result.storage_path
            if conf >= threshold:
                filtered.storage_path = scan_result.storage_path

        # Filter custom fields
        for field_id, (value, conf) in scan_result.custom_fields.items():
            if conf >= threshold:
                filtered.custom_fields[field_id] = (value, conf)

        # Filter workflows
        filtered.workflows = [
            (wf_id, conf) for wf_id, conf in scan_result.workflows if conf >= threshold
        ]

        # Copy other fields as-is
        filtered.extracted_entities = scan_result.extracted_entities
        filtered.title_suggestion = scan_result.title_suggestion
        filtered.metadata = scan_result.metadata

        return filtered

    def _count_suggestions(self, scan_result: AIScanResult) -> int:
        """Count total number of suggestions in scan result."""
        count = 0
        count += len(scan_result.tags)
        count += 1 if scan_result.correspondent else 0
        count += 1 if scan_result.document_type else 0
        count += 1 if scan_result.storage_path else 0
        count += len(scan_result.custom_fields)
        count += len(scan_result.workflows)
        count += 1 if scan_result.title_suggestion else 0
        return count

    def _display_final_summary(self, results: dict[str, Any], options):
        """Display final summary of processing results."""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Processing Complete - Summary"))
        self.stdout.write("=" * 70 + "\n")

        # Display statistics
        self.stdout.write("Statistics:")
        self.stdout.write(f"  • Documents processed: {results['processed']}")
        self.stdout.write(
            f"  • Documents with suggestions: {len(results['documents_with_suggestions'])}"
        )
        self.stdout.write(
            f"  • Total suggestions generated: {results['suggestions_generated']}"
        )

        if options["auto_apply_high_confidence"] and not options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  • Suggestions auto-applied: {results['auto_applied']}"
                ),
            )

        if results["errors"] > 0:
            self.stdout.write(
                self.style.ERROR(f"  • Errors encountered: {results['errors']}"),
            )

        # Display sample suggestions
        if results["documents_with_suggestions"]:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("Sample Suggestions (first 5 documents):\n")

            for doc_info in results["documents_with_suggestions"][:5]:
                self._display_document_suggestions(doc_info, options)

        # Display errors
        if results["error_documents"]:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write(self.style.ERROR("Errors:\n"))

            for error_info in results["error_documents"][:10]:
                self.stdout.write(
                    f"  • Document {error_info['id']}: {error_info['title']}",
                )
                self.stdout.write(f"    Error: {error_info['error']}")

        # Final message
        self.stdout.write("\n" + "=" * 70)
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN completed - No changes were applied to documents.",
                ),
            )
        elif options["auto_apply_high_confidence"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processing complete - {results['auto_applied']} high confidence "
                    "suggestions were automatically applied.",
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Processing complete - Suggestions generated. Use "
                    "--auto-apply-high-confidence to apply them automatically.",
                ),
            )
        self.stdout.write("=" * 70 + "\n")

    def _display_document_suggestions(self, doc_info: dict[str, Any], options):
        """Display suggestions for a single document."""
        from documents.models import Correspondent
        from documents.models import DocumentType
        from documents.models import StoragePath

        self.stdout.write(
            f"\n  Document #{doc_info['id']}: {doc_info['title']}",
        )

        suggestions = doc_info["suggestions"]

        # Tags
        if suggestions.get("tags"):
            self.stdout.write("    Tags:")
            for tag_id, conf in suggestions["tags"][:3]:  # Show first 3
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    self.stdout.write(
                        f"      • {tag.name} (confidence: {conf:.0%})",
                    )
                except Tag.DoesNotExist:
                    pass

        # Correspondent
        if suggestions.get("correspondent"):
            corr_id, conf = suggestions["correspondent"]
            try:
                correspondent = Correspondent.objects.get(pk=corr_id)
                self.stdout.write(
                    f"    Correspondent: {correspondent.name} (confidence: {conf:.0%})",
                )
            except Correspondent.DoesNotExist:
                pass

        # Document Type
        if suggestions.get("document_type"):
            type_id, conf = suggestions["document_type"]
            try:
                doc_type = DocumentType.objects.get(pk=type_id)
                self.stdout.write(
                    f"    Document Type: {doc_type.name} (confidence: {conf:.0%})",
                )
            except DocumentType.DoesNotExist:
                pass

        # Storage Path
        if suggestions.get("storage_path"):
            path_id, conf = suggestions["storage_path"]
            try:
                storage_path = StoragePath.objects.get(pk=path_id)
                self.stdout.write(
                    f"    Storage Path: {storage_path.name} (confidence: {conf:.0%})",
                )
            except StoragePath.DoesNotExist:
                pass

        # Title suggestion
        if suggestions.get("title_suggestion"):
            self.stdout.write(
                f"    Title: {suggestions['title_suggestion']}",
            )

        # Applied changes (if auto-apply was enabled)
        if doc_info.get("applied"):
            applied = doc_info["applied"].get("applied", {})
            if any(applied.values()):
                self.stdout.write(
                    self.style.SUCCESS("    ✓ Applied changes:"),
                )
                if applied.get("tags"):
                    tag_names = [t["name"] for t in applied["tags"]]
                    self.stdout.write(
                        f"      • Tags: {', '.join(tag_names)}",
                    )
                if applied.get("correspondent"):
                    self.stdout.write(
                        f"      • Correspondent: {applied['correspondent']['name']}",
                    )
                if applied.get("document_type"):
                    self.stdout.write(
                        f"      • Type: {applied['document_type']['name']}",
                    )
                if applied.get("storage_path"):
                    self.stdout.write(
                        f"      • Path: {applied['storage_path']['name']}",
                    )
