from typing import Any

from rest_framework import serializers

from documents.models import DocumentReview

REVIEW_ACTIONS = ["submit", "approve", "reject", "reopen"]
REVIEW_EVENT_ACTIONS = [*REVIEW_ACTIONS, "invalidate"]


class ReviewEventSerializer(serializers.Serializer[dict[str, Any]]):
    action = serializers.ChoiceField(
        choices=REVIEW_EVENT_ACTIONS,
    )
    actor = serializers.IntegerField(allow_null=True)
    revision = serializers.IntegerField(min_value=1)
    at = serializers.DateTimeField()
    request_id = serializers.UUIDField(allow_null=True)
    comment = serializers.CharField(allow_blank=True)


class DocumentReviewSerializer(serializers.Serializer[dict[str, Any]]):
    document = serializers.IntegerField()
    state = serializers.ChoiceField(choices=DocumentReview.State.choices)
    revision = serializers.IntegerField(min_value=0)
    reviewer = serializers.IntegerField(allow_null=True)
    submitted_by = serializers.IntegerField(allow_null=True)
    history = ReviewEventSerializer(many=True)


class ReviewMutationSerializer(serializers.Serializer[dict[str, Any]]):
    action = serializers.ChoiceField(choices=REVIEW_ACTIONS)
    expected_revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    reviewer = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Required only for submit.",
    )
    comment = serializers.CharField(
        min_length=1,
        max_length=2000,
        required=False,
        help_text="Required only for reject; 1-2000 trimmed Unicode characters.",
    )


class ReviewerSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    username = serializers.CharField()


class ReviewOptionsSerializer(serializers.Serializer[dict[str, Any]]):
    allowed_actions = serializers.ListField(
        child=serializers.ChoiceField(
            choices=REVIEW_ACTIONS,
        ),
    )
    results = ReviewerSerializer(many=True)


class ReviewQueueItemSerializer(serializers.Serializer[dict[str, Any]]):
    document = serializers.IntegerField()
    state = serializers.ChoiceField(choices=DocumentReview.State.choices)
    reviewer = serializers.IntegerField(allow_null=True)
    revision = serializers.IntegerField(min_value=1)
    title = serializers.CharField()


class ReviewQueueSerializer(serializers.Serializer[dict[str, Any]]):
    count = serializers.IntegerField(min_value=0)
    results = ReviewQueueItemSerializer(many=True)
