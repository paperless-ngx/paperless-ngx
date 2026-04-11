"""
Workflow trigger matching profiling.

Run with:
    uv run pytest ../test_workflow_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Corpus: 500 documents + correspondents + tags + sets of WorkflowTrigger
        objects at 5 and 20 count to allow scaling comparisons.

Scenarios
---------
TestWorkflowMatchingProfile
  - test_existing_document_5_workflows    existing_document_matches_workflow x 5 triggers
  - test_existing_document_20_workflows   same x 20 triggers
  - test_workflow_prefilter               prefilter_documents_by_workflowtrigger on 500 docs
  - test_trigger_type_comparison          compare DOCUMENT_ADDED vs DOCUMENT_UPDATED overhead
"""

from __future__ import annotations

import random
import time

import pytest
from faker import Faker
from profiling import profile_block

from documents.matching import existing_document_matches_workflow
from documents.matching import prefilter_documents_by_workflowtrigger
from documents.models import Correspondent
from documents.models import Document
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger

pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

NUM_DOCS = 500
NUM_CORRESPONDENTS = 10
NUM_TAGS = 20
SEED = 42


# ---------------------------------------------------------------------------
# Module-scoped fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    """Unlock the DB for the whole module (module-scoped)."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def workflow_corpus(module_db):
    """
    500 documents + correspondents + tags + sets of workflow triggers
    at 5 and 20 count to allow scaling comparisons.
    """
    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)

    # ---- lookup objects ---------------------------------------------------
    print("\n[setup] Creating lookup objects...")  # noqa: T201
    correspondents = [
        Correspondent.objects.create(name=f"wfcorp-{i}-{fake.company()}"[:128])
        for i in range(NUM_CORRESPONDENTS)
    ]
    tags = [
        Tag.objects.create(name=f"wftag-{i}-{fake.word()}"[:100])
        for i in range(NUM_TAGS)
    ]

    # ---- documents --------------------------------------------------------
    print(f"[setup] Building {NUM_DOCS} documents...")  # noqa: T201
    raw_docs = []
    for i in range(NUM_DOCS):
        raw_docs.append(
            Document(
                title=fake.sentence(nb_words=4).rstrip("."),
                content=fake.paragraph(nb_sentences=3),
                checksum=f"WF{i:07d}",
                correspondent=rng.choice(correspondents + [None] * 3),
            ),
        )
    documents = Document.objects.bulk_create(raw_docs, batch_size=500)
    for doc in documents:
        k = rng.randint(0, 3)
        if k:
            doc.tags.add(*rng.sample(tags, k))

    sample_doc = documents[0]
    print(f"[setup] Sample doc pk={sample_doc.pk}")  # noqa: T201

    # ---- build triggers at scale 5 and 20 --------------------------------
    _wf_counter = [0]

    def _make_triggers(n: int, trigger_type: int) -> list[WorkflowTrigger]:
        triggers = []
        for i in range(n):
            # Alternate between no filter and a correspondent filter
            corr = correspondents[i % NUM_CORRESPONDENTS] if i % 3 == 0 else None
            trigger = WorkflowTrigger.objects.create(
                type=trigger_type,
                filter_has_correspondent=corr,
            )
            action = WorkflowAction.objects.create(
                type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
            )
            idx = _wf_counter[0]
            _wf_counter[0] += 1
            wf = Workflow.objects.create(name=f"wf-profile-{idx}")
            wf.triggers.add(trigger)
            wf.actions.add(action)
            triggers.append(trigger)
        return triggers

    print("[setup] Creating workflow triggers...")  # noqa: T201
    triggers_5 = _make_triggers(5, WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED)
    triggers_20 = _make_triggers(
        20,
        WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
    )
    triggers_added = _make_triggers(
        5,
        WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
    )

    yield {
        "doc": sample_doc,
        "triggers_5": triggers_5,
        "triggers_20": triggers_20,
        "triggers_added": triggers_added,
    }

    # Teardown
    print("\n[teardown] Removing workflow corpus...")  # noqa: T201
    Workflow.objects.all().delete()
    WorkflowTrigger.objects.all().delete()
    WorkflowAction.objects.all().delete()
    Document.objects.all().delete()
    Correspondent.objects.all().delete()
    Tag.objects.all().delete()


# ---------------------------------------------------------------------------
# TestWorkflowMatchingProfile
# ---------------------------------------------------------------------------


class TestWorkflowMatchingProfile:
    """Profile workflow trigger evaluation per document save."""

    @pytest.fixture(autouse=True)
    def _setup(self, workflow_corpus):
        self.doc = workflow_corpus["doc"]
        self.triggers_5 = workflow_corpus["triggers_5"]
        self.triggers_20 = workflow_corpus["triggers_20"]
        self.triggers_added = workflow_corpus["triggers_added"]

    def test_existing_document_5_workflows(self):
        """existing_document_matches_workflow x 5 DOCUMENT_UPDATED triggers."""
        doc = self.doc
        triggers = self.triggers_5

        with profile_block(
            f"existing_document_matches_workflow  [{len(triggers)} triggers]",
        ):
            for trigger in triggers:
                existing_document_matches_workflow(doc, trigger)

    def test_existing_document_20_workflows(self):
        """existing_document_matches_workflow x 20 triggers -- shows linear scaling."""
        doc = self.doc
        triggers = self.triggers_20

        with profile_block(
            f"existing_document_matches_workflow  [{len(triggers)} triggers]",
        ):
            for trigger in triggers:
                existing_document_matches_workflow(doc, trigger)

        # Also time each call individually to show per-trigger overhead
        timings = []
        for trigger in triggers:
            t0 = time.perf_counter()
            existing_document_matches_workflow(doc, trigger)
            timings.append((time.perf_counter() - t0) * 1_000_000)
        avg_us = sum(timings) / len(timings)
        print(f"\n  Per-trigger avg: {avg_us:.1f} us  (n={len(timings)})")  # noqa: T201

    def test_workflow_prefilter(self):
        """prefilter_documents_by_workflowtrigger on 500 docs -- tag + correspondent filters."""
        qs = Document.objects.all()
        print(f"\n  Corpus: {qs.count()} documents")  # noqa: T201

        for trigger in self.triggers_20[:3]:
            label = (
                f"prefilter_documents_by_workflowtrigger  "
                f"[corr={trigger.filter_has_correspondent_id}]"
            )
            with profile_block(label):
                result = prefilter_documents_by_workflowtrigger(qs, trigger)
                # Evaluate the queryset
                count = result.count()
            print(f"  -> {count} docs passed filter")  # noqa: T201

    def test_trigger_type_comparison(self):
        """Compare per-call overhead of DOCUMENT_UPDATED vs DOCUMENT_ADDED."""
        doc = self.doc
        runs = 200

        for label, triggers in [
            ("DOCUMENT_UPDATED", self.triggers_5),
            ("DOCUMENT_ADDED", self.triggers_added),
        ]:
            t0 = time.perf_counter()
            for _ in range(runs):
                for trigger in triggers:
                    existing_document_matches_workflow(doc, trigger)
            total_calls = runs * len(triggers)
            us_per_call = (time.perf_counter() - t0) / total_calls * 1_000_000
            print(  # noqa: T201
                f"  {label:<22s}  {us_per_call:.2f} us/call  "
                f"({total_calls} calls, {len(triggers)} triggers)",
            )
