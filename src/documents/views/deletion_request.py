"""
API ViewSet for DeletionRequest management.

Provides endpoints for:
- Listing and retrieving deletion requests
- Approving deletion requests (POST /api/deletion-requests/{id}/approve/)
- Rejecting deletion requests (POST /api/deletion-requests/{id}/reject/)
- Canceling deletion requests (POST /api/deletion-requests/{id}/cancel/)
"""

import logging

from django.db import transaction
from django.http import HttpResponseForbidden
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.models import DeletionRequest
from documents.serialisers import DeletionRequestSerializer

logger = logging.getLogger("paperless.api")


class DeletionRequestViewSet(ModelViewSet):
    """
    ViewSet for managing deletion requests.
    
    Provides CRUD operations plus custom actions for approval workflow.
    """

    model = DeletionRequest
    serializer_class = DeletionRequestSerializer

    def get_queryset(self):
        """
        Return deletion requests for the current user.
        
        Superusers can see all requests.
        Regular users only see their own requests.
        """
        user = self.request.user
        if user.is_superuser:
            return DeletionRequest.objects.all()
        return DeletionRequest.objects.filter(user=user)

    def _can_manage_request(self, deletion_request):
        """
        Check if current user can manage (approve/reject/cancel) the request.
        
        Args:
            deletion_request: The DeletionRequest instance
            
        Returns:
            bool: True if user is the owner or a superuser
        """
        user = self.request.user
        return user.is_superuser or deletion_request.user == user

    @action(methods=["post"], detail=True)
    def approve(self, request, pk=None):
        """
        Approve a pending deletion request and execute the deletion.
        
        Validates:
        - User has permission (owner or admin)
        - Status is pending
        
        Returns:
            Response with execution results
        """
        deletion_request = self.get_object()

        # Check permissions
        if not self._can_manage_request(deletion_request):
            return HttpResponseForbidden(
                "You don't have permission to approve this deletion request.",
            )

        # Validate status
        if deletion_request.status != DeletionRequest.STATUS_PENDING:
            return Response(
                {
                    "error": "Only pending deletion requests can be approved.",
                    "current_status": deletion_request.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Execute approval and deletion in a transaction
        try:
            with transaction.atomic():
                # Approve the request
                if not deletion_request.approve(request.user, comment):
                    return Response(
                        {"error": "Failed to approve deletion request."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # Execute the deletion
                documents = list(deletion_request.documents.all())
                deleted_count = 0
                failed_deletions = []

                for doc in documents:
                    try:
                        doc_id = doc.id
                        doc_title = doc.title
                        doc.delete()
                        deleted_count += 1
                        logger.info(
                            f"Deleted document {doc_id} ('{doc_title}') "
                            f"as part of deletion request {deletion_request.id}",
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete document {doc.id}: {e!s}",
                        )
                        failed_deletions.append({
                            "id": doc.id,
                            "title": doc.title,
                            "error": str(e),
                        })

                # Update completion status
                deletion_request.status = DeletionRequest.STATUS_COMPLETED
                deletion_request.completed_at = timezone.now()
                deletion_request.completion_details = {
                    "deleted_count": deleted_count,
                    "failed_deletions": failed_deletions,
                    "total_documents": len(documents),
                }
                deletion_request.save()

                logger.info(
                    f"Deletion request {deletion_request.id} completed. "
                    f"Deleted {deleted_count}/{len(documents)} documents.",
                )
        except Exception as e:
            logger.error(
                f"Error executing deletion request {deletion_request.id}: {e!s}",
            )
            return Response(
                {"error": f"Failed to execute deletion: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(deletion_request)
        return Response(
            {
                "message": "Deletion request approved and executed successfully.",
                "execution_result": deletion_request.completion_details,
                "deletion_request": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(methods=["post"], detail=True)
    def reject(self, request, pk=None):
        """
        Reject a pending deletion request.
        
        Validates:
        - User has permission (owner or admin)
        - Status is pending
        
        Returns:
            Response with updated deletion request
        """
        deletion_request = self.get_object()

        # Check permissions
        if not self._can_manage_request(deletion_request):
            return HttpResponseForbidden(
                "You don't have permission to reject this deletion request.",
            )

        # Validate status
        if deletion_request.status != DeletionRequest.STATUS_PENDING:
            return Response(
                {
                    "error": "Only pending deletion requests can be rejected.",
                    "current_status": deletion_request.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Reject the request
        if not deletion_request.reject(request.user, comment):
            return Response(
                {"error": "Failed to reject deletion request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            f"Deletion request {deletion_request.id} rejected by user {request.user.username}",
        )

        serializer = self.get_serializer(deletion_request)
        return Response(
            {
                "message": "Deletion request rejected successfully.",
                "deletion_request": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(methods=["post"], detail=True)
    def cancel(self, request, pk=None):
        """
        Cancel a pending deletion request.
        
        Validates:
        - User has permission (owner or admin)
        - Status is pending
        
        Returns:
            Response with updated deletion request
        """
        deletion_request = self.get_object()

        # Check permissions
        if not self._can_manage_request(deletion_request):
            return HttpResponseForbidden(
                "You don't have permission to cancel this deletion request.",
            )

        # Validate status
        if deletion_request.status != DeletionRequest.STATUS_PENDING:
            return Response(
                {
                    "error": "Only pending deletion requests can be cancelled.",
                    "current_status": deletion_request.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel the request
        deletion_request.status = DeletionRequest.STATUS_CANCELLED
        deletion_request.reviewed_by = request.user
        deletion_request.reviewed_at = timezone.now()
        deletion_request.review_comment = request.data.get("comment", "Cancelled by user")
        deletion_request.save()

        logger.info(
            f"Deletion request {deletion_request.id} cancelled by user {request.user.username}",
        )

        serializer = self.get_serializer(deletion_request)
        return Response(
            {
                "message": "Deletion request cancelled successfully.",
                "deletion_request": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
