"""Exercise native queued Apply AI Suggestions in the fixed synthetic lab."""

import time

from mock_suggestions import PROPOSAL
from smoke import api
from smoke import fixture_document
from smoke import get_or_create
from smoke import provider_state


def main():
    document_id = fixture_document()
    path = f"/api/documents/{document_id}/"
    original = api(path)
    gate = get_or_create("tags", "Synthetic Inbox")
    workflow = None
    try:
        assert not api("/api/workflows/")["results"], "Unexpected lab workflows"
        api(
            path,
            {
                "title": "Upstream fixture",
                "tags": sorted(set(original["tags"]) | {gate}),
            },
            method="PATCH",
        )
        before = api(path)
        baseline = provider_state()
        workflow = api(
            "/api/workflows/",
            {
                "name": "Synthetic provider acceptance",
                "order": 1,
                "enabled": True,
                "triggers": [{"type": 3, "filter_has_tags": [gate]}],
                "actions": [
                    {
                        "type": 8,  # WorkflowActionType.APPLY_AI_SUGGESTIONS
                        "ai_suggestion_fields": ["title"],
                        "ai_create_missing": False,
                        "ai_overwrite_existing": True,
                    },
                ],
            },
        )
        api(path, {"title": "Upstream fixture"}, method="PATCH")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            current = api(path)
            state = provider_state()
            events = [
                event
                for key, event in state["applied"].items()
                if key not in baseline["applied"]
            ]
            if current["title"] == PROPOSAL["title"] and events:
                break
            time.sleep(1)
        else:
            raise RuntimeError(
                "Native apply or provider completion notification did not finish",
            )
        assert state["provider_requests"] == baseline["provider_requests"] + 1
        assert state["native_requests"] == baseline["native_requests"]
        assert len(events) == 1 and events[0]["document_id"] == document_id
        assert events[0]["changed_fields"] == ["title"]
        for field in (
            "tags",
            "storage_path",
            "correspondent",
            "document_type",
            "content",
            "custom_fields",
        ):
            assert current[field] == before[field], f"Unexpected change to {field}"
        assert gate in current["tags"]
        print(  # noqa: T201
            "PASS: queued native Apply AI Suggestions, retained Inbox and unselected fields, provider notification",
        )
    finally:
        if workflow is not None:
            api(f"/api/workflows/{workflow['id']}/", method="DELETE")
        api(
            path,
            {"title": original["title"], "tags": original["tags"]},
            method="PATCH",
        )


if __name__ == "__main__":
    main()
