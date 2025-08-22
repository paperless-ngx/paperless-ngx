"""
Vues API REST pour le module IMAP Paperless-ngx

Gestion des comptes IMAP, e-mails, pièces jointes et synchronisation
via des APIs REST complètes.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters

from .models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)
from .serializers import (
    IMAPAccountSerializer, EmailMessageSerializer, EmailMessageDetailSerializer,
    EmailAttachmentSerializer, EmailEventSerializer, SyncLogSerializer,
    EmailStatisticsSerializer, IMAPTestConnectionSerializer,
    BulkEmailActionSerializer
)
from .tasks import (
    sync_imap_account, process_email_attachment,
    process_pending_attachments, generate_email_statistics
)
from .imap_engine import IMAPProcessor, IMAPConnectionError, IMAPAuthenticationError


logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Pagination standard pour les APIs IMAP"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmailMessageFilter(filters.FilterSet):
    """Filtres pour les e-mails"""

    date_sent_from = filters.DateTimeFilter(field_name='date_sent', lookup_expr='gte')
    date_sent_to = filters.DateTimeFilter(field_name='date_sent', lookup_expr='lte')
    sender_contains = filters.CharFilter(field_name='sender', lookup_expr='icontains')
    subject_contains = filters.CharFilter(field_name='subject', lookup_expr='icontains')
    has_attachments = filters.BooleanFilter(method='filter_has_attachments')
    has_events = filters.BooleanFilter(method='filter_has_events')

    class Meta:
        model = EmailMessage
        fields = [
            'account', 'folder', 'category', 'priority',
            'is_read', 'is_flagged', 'is_processed'
        ]

    def filter_has_attachments(self, queryset, name, value):
        """Filtre les e-mails avec/sans pièces jointes"""
        if value:
            return queryset.filter(attachments__isnull=False).distinct()
        else:
            return queryset.filter(attachments__isnull=True)

    def filter_has_events(self, queryset, name, value):
        """Filtre les e-mails avec/sans événements"""
        if value:
            return queryset.filter(events__isnull=False).distinct()
        else:
            return queryset.filter(events__isnull=True)


class IMAPAccountViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des comptes IMAP"""

    serializer_class = IMAPAccountSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'auth_method']
    search_fields = ['name', 'server', 'username']
    ordering_fields = ['name', 'created', 'last_sync']
    ordering = ['-created']

    def get_queryset(self):
        """Retourne seulement les comptes de l'utilisateur connecté"""
        return IMAPAccount.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """Assigne le propriétaire lors de la création"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Lance la synchronisation d'un compte spécifique

        POST /api/imap/accounts/{id}/sync/
        Body: {"force_full_sync": false}
        """
        account = self.get_object()
        force_full_sync = request.data.get('force_full_sync', False)

        try:
            # Lancement de la tâche asynchrone
            task = sync_imap_account.delay(str(account.id), force_full_sync)

            return Response({
                'message': 'Synchronisation lancée',
                'task_id': task.id,
                'account_id': str(account.id),
                'force_full_sync': force_full_sync
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(f"Erreur lancement synchronisation {account.name}: {e}")
            return Response({
                'error': f"Erreur lancement synchronisation: {e}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """
        Teste la connexion d'un compte IMAP

        POST /api/imap/accounts/{id}/test_connection/
        """
        account = self.get_object()

        try:
            processor = IMAPProcessor(account)
            success = processor.connect()
            processor.disconnect()

            if success:
                return Response({
                    'status': 'success',
                    'message': 'Connexion IMAP réussie',
                    'account_id': str(account.id)
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Échec de connexion IMAP',
                    'account_id': str(account.id)
                }, status=status.HTTP_400_BAD_REQUEST)

        except IMAPAuthenticationError as e:
            return Response({
                'status': 'error',
                'message': f'Erreur d\'authentification: {e}',
                'account_id': str(account.id)
            }, status=status.HTTP_401_UNAUTHORIZED)

        except IMAPConnectionError as e:
            return Response({
                'status': 'error',
                'message': f'Erreur de connexion: {e}',
                'account_id': str(account.id)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Erreur test connexion {account.name}: {e}")
            return Response({
                'status': 'error',
                'message': f'Erreur inattendue: {e}',
                'account_id': str(account.id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Retourne les statistiques d'un compte

        GET /api/imap/accounts/{id}/statistics/?days=30
        """
        account = self.get_object()
        days = int(request.query_params.get('days', 30))

        cutoff_date = timezone.now() - timedelta(days=days)

        # Statistiques du compte
        emails = EmailMessage.objects.filter(account=account, created__gte=cutoff_date)
        attachments = EmailAttachment.objects.filter(email__account=account, email__created__gte=cutoff_date)

        stats = {
            'account_id': str(account.id),
            'account_name': account.name,
            'period_days': days,
            'total_emails': emails.count(),
            'total_attachments': attachments.count(),
            'processed_attachments': attachments.filter(is_processed=True).count(),
            'unread_emails': emails.filter(is_read=False).count(),
            'flagged_emails': emails.filter(is_flagged=True).count(),
            'last_sync': account.last_sync.isoformat() if account.last_sync else None,
            'sync_errors': len(account.sync_errors or []),
            'categories': {}
        }

        # Statistiques par catégorie
        for category, label in EmailMessage.CATEGORY_CHOICES:
            count = emails.filter(category=category).count()
            stats['categories'][category] = {
                'label': label,
                'count': count
            }

        return Response(stats)

    @action(detail=True, methods=['get'])
    def sync_logs(self, request, pk=None):
        """
        Retourne les logs de synchronisation d'un compte

        GET /api/imap/accounts/{id}/sync_logs/?limit=10
        """
        account = self.get_object()
        limit = int(request.query_params.get('limit', 10))

        logs = SyncLog.objects.filter(account=account).order_by('-start_time')[:limit]
        serializer = SyncLogSerializer(logs, many=True)

        return Response({
            'account_id': str(account.id),
            'logs': serializer.data,
            'total_logs': SyncLog.objects.filter(account=account).count()
        })

    @action(detail=False, methods=['post'])
    def test_new_connection(self, request):
        """
        Teste une nouvelle connexion IMAP sans créer de compte

        POST /api/imap/accounts/test_new_connection/
        Body: {server, port, username, password, etc.}
        """
        serializer = IMAPTestConnectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Création d'un compte temporaire pour le test
        temp_account = IMAPAccount(
            server=data['server'],
            port=data['port'],
            use_ssl=data['use_ssl'],
            use_starttls=data['use_starttls'],
            auth_method=data['auth_method'],
            username=data['username'],
            oauth2_client_id=data.get('oauth2_client_id', ''),
            oauth2_client_secret=data.get('oauth2_client_secret', ''),
            oauth2_access_token=data.get('oauth2_access_token', ''),
        )

        if data.get('password'):
            temp_account.set_password(data['password'])

        try:
            processor = IMAPProcessor(temp_account)
            success = processor.connect()
            processor.disconnect()

            if success:
                return Response({
                    'status': 'success',
                    'message': 'Connexion IMAP réussie'
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Échec de connexion IMAP'
                }, status=status.HTTP_400_BAD_REQUEST)

        except IMAPAuthenticationError as e:
            return Response({
                'status': 'error',
                'message': f'Erreur d\'authentification: {e}'
            }, status=status.HTTP_401_UNAUTHORIZED)

        except IMAPConnectionError as e:
            return Response({
                'status': 'error',
                'message': f'Erreur de connexion: {e}'
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Erreur test nouvelle connexion: {e}")
            return Response({
                'status': 'error',
                'message': f'Erreur inattendue: {e}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les e-mails"""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmailMessageFilter
    search_fields = ['subject', 'sender', 'body_text']
    ordering_fields = ['date_sent', 'date_received', 'subject', 'sender']
    ordering = ['-date_sent']

    def get_queryset(self):
        """Retourne seulement les e-mails des comptes de l'utilisateur"""
        return EmailMessage.objects.filter(account__owner=self.request.user)

    def get_serializer_class(self):
        """Utilise le sérialiseur détaillé pour la vue de détail"""
        if self.action == 'retrieve':
            return EmailMessageDetailSerializer
        return EmailMessageSerializer

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Marque un e-mail comme lu

        POST /api/imap/emails/{id}/mark_read/
        """
        email = self.get_object()
        email.is_read = True
        email.save(update_fields=['is_read'])

        return Response({
            'message': 'E-mail marqué comme lu',
            'email_id': str(email.id),
            'is_read': email.is_read
        })

    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """
        Marque un e-mail comme non lu

        POST /api/imap/emails/{id}/mark_unread/
        """
        email = self.get_object()
        email.is_read = False
        email.save(update_fields=['is_read'])

        return Response({
            'message': 'E-mail marqué comme non lu',
            'email_id': str(email.id),
            'is_read': email.is_read
        })

    @action(detail=True, methods=['post'])
    def toggle_flag(self, request, pk=None):
        """
        Bascule le marquage d'un e-mail

        POST /api/imap/emails/{id}/toggle_flag/
        """
        email = self.get_object()
        email.is_flagged = not email.is_flagged
        email.save(update_fields=['is_flagged'])

        return Response({
            'message': f'E-mail {"marqué" if email.is_flagged else "démarqué"}',
            'email_id': str(email.id),
            'is_flagged': email.is_flagged
        })

    @action(detail=True, methods=['post'])
    def categorize(self, request, pk=None):
        """
        Change la catégorie d'un e-mail

        POST /api/imap/emails/{id}/categorize/
        Body: {"category": "professional"}
        """
        email = self.get_object()
        category = request.data.get('category')

        if not category:
            return Response({
                'error': 'La catégorie est requise'
            }, status=status.HTTP_400_BAD_REQUEST)

        valid_categories = [choice[0] for choice in EmailMessage.CATEGORY_CHOICES]
        if category not in valid_categories:
            return Response({
                'error': f'Catégorie invalide. Choix valides: {valid_categories}'
            }, status=status.HTTP_400_BAD_REQUEST)

        email.category = category
        email.save(update_fields=['category'])

        return Response({
            'message': 'Catégorie mise à jour',
            'email_id': str(email.id),
            'category': email.category,
            'category_display': email.get_category_display()
        })

    @action(detail=True, methods=['post'])
    def process_attachments(self, request, pk=None):
        """
        Lance le traitement des pièces jointes d'un e-mail

        POST /api/imap/emails/{id}/process_attachments/
        """
        email = self.get_object()

        # Récupération des pièces jointes non traitées
        pending_attachments = email.attachments.filter(
            is_processed=False,
            is_supported_format=True
        )

        if not pending_attachments.exists():
            return Response({
                'message': 'Aucune pièce jointe à traiter',
                'email_id': str(email.id),
                'pending_count': 0
            })

        # Lancement des tâches de traitement
        task_ids = []
        for attachment in pending_attachments:
            task = process_email_attachment.delay(str(attachment.id))
            task_ids.append(task.id)

        return Response({
            'message': f'Traitement lancé pour {len(task_ids)} pièce(s) jointe(s)',
            'email_id': str(email.id),
            'attachment_count': len(task_ids),
            'task_ids': task_ids
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['post'])
    def bulk_actions(self, request):
        """
        Actions en lot sur les e-mails

        POST /api/imap/emails/bulk_actions/
        Body: {
            "action": "mark_read",
            "email_ids": ["uuid1", "uuid2"],
            "category": "professional"  # Optionnel selon l'action
        }
        """
        serializer = BulkEmailActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        action = data['action']
        email_ids = data['email_ids']

        # Récupération des e-mails (seulement ceux de l'utilisateur)
        emails = EmailMessage.objects.filter(
            id__in=email_ids,
            account__owner=self.request.user
        )

        if not emails.exists():
            return Response({
                'error': 'Aucun e-mail trouvé avec les IDs fournis'
            }, status=status.HTTP_404_NOT_FOUND)

        # Exécution de l'action
        updated_count = 0

        with transaction.atomic():
            if action == BulkEmailActionSerializer.ACTION_MARK_READ:
                updated_count = emails.update(is_read=True)

            elif action == BulkEmailActionSerializer.ACTION_MARK_UNREAD:
                updated_count = emails.update(is_read=False)

            elif action == BulkEmailActionSerializer.ACTION_CATEGORIZE:
                category = data.get('category')
                updated_count = emails.update(category=category)

            elif action == BulkEmailActionSerializer.ACTION_DELETE:
                updated_count = emails.count()
                emails.delete()

            elif action == BulkEmailActionSerializer.ACTION_PROCESS_ATTACHMENTS:
                # Lancement du traitement des pièces jointes
                task_ids = []
                for email in emails:
                    attachments = email.attachments.filter(
                        is_processed=False,
                        is_supported_format=True
                    )
                    for attachment in attachments:
                        task = process_email_attachment.delay(str(attachment.id))
                        task_ids.append(task.id)

                return Response({
                    'message': f'Traitement lancé pour {len(task_ids)} pièce(s) jointe(s)',
                    'email_count': emails.count(),
                    'task_count': len(task_ids),
                    'task_ids': task_ids
                }, status=status.HTTP_202_ACCEPTED)

        return Response({
            'message': f'Action "{action}" appliquée à {updated_count} e-mail(s)',
            'action': action,
            'updated_count': updated_count,
            'requested_count': len(email_ids)
        })


class EmailAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les pièces jointes"""

    serializer_class = EmailAttachmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_processed', 'is_supported_format', 'content_type']
    search_fields = ['filename']
    ordering_fields = ['filename', 'size', 'created']
    ordering = ['-created']

    def get_queryset(self):
        """Retourne seulement les pièces jointes des comptes de l'utilisateur"""
        return EmailAttachment.objects.filter(email__account__owner=self.request.user)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Lance le traitement d'une pièce jointe

        POST /api/imap/attachments/{id}/process/
        """
        attachment = self.get_object()

        if attachment.is_processed:
            return Response({
                'message': 'Pièce jointe déjà traitée',
                'attachment_id': str(attachment.id),
                'document_id': attachment.document.id if attachment.document else None
            })

        if not attachment.is_supported_format:
            return Response({
                'error': 'Format de pièce jointe non supporté',
                'attachment_id': str(attachment.id),
                'content_type': attachment.content_type
            }, status=status.HTTP_400_BAD_REQUEST)

        # Lancement du traitement
        task = process_email_attachment.delay(str(attachment.id))

        return Response({
            'message': 'Traitement de la pièce jointe lancé',
            'attachment_id': str(attachment.id),
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Télécharge le contenu d'une pièce jointe

        GET /api/imap/attachments/{id}/download/
        """
        attachment = self.get_object()

        # TODO: Implémenter le téléchargement sécurisé
        # Cette fonctionnalité nécessiterait une gestion spéciale
        # du contenu binaire et des permissions de sécurité

        return Response({
            'message': 'Téléchargement non encore implémenté',
            'attachment_id': str(attachment.id),
            'filename': attachment.filename,
            'size': attachment.size
        }, status=status.HTTP_501_NOT_IMPLEMENTED)


class EmailEventViewSet(viewsets.ModelViewSet):
    """ViewSet pour les événements extraits des e-mails"""

    serializer_class = EmailEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['event_type', 'is_validated', 'all_day']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['start_date', 'created', 'confidence_score']
    ordering = ['-start_date']

    def get_queryset(self):
        """Retourne seulement les événements des comptes de l'utilisateur"""
        return EmailEvent.objects.filter(email__account__owner=self.request.user)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Valide un événement extrait

        POST /api/imap/events/{id}/validate/
        """
        event = self.get_object()
        event.is_validated = True
        event.save(update_fields=['is_validated'])

        return Response({
            'message': 'Événement validé',
            'event_id': str(event.id),
            'is_validated': event.is_validated
        })

    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """
        Vue calendrier des événements

        GET /api/imap/events/calendar_view/?start=2024-01-01&end=2024-01-31
        """
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        queryset = self.get_queryset()

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(start_date__gte=start_dt)
            except ValueError:
                return Response({
                    'error': 'Format de date invalide pour start'
                }, status=status.HTTP_400_BAD_REQUEST)

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(start_date__lte=end_dt)
            except ValueError:
                return Response({
                    'error': 'Format de date invalide pour end'
                }, status=status.HTTP_400_BAD_REQUEST)

        events = queryset.order_by('start_date')
        serializer = self.get_serializer(events, many=True)

        return Response({
            'events': serializer.data,
            'count': events.count(),
            'period': {
                'start': start_date,
                'end': end_date
            }
        })


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les logs de synchronisation"""

    serializer_class = SyncLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'account']
    ordering_fields = ['start_time', 'end_time', 'emails_processed']
    ordering = ['-start_time']

    def get_queryset(self):
        """Retourne seulement les logs des comptes de l'utilisateur"""
        return SyncLog.objects.filter(account__owner=self.request.user)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Statistiques des synchronisations

        GET /api/imap/sync-logs/statistics/?days=7
        """
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timedelta(days=days)

        logs = self.get_queryset().filter(start_time__gte=cutoff_date)

        stats = {
            'period_days': days,
            'total_syncs': logs.count(),
            'successful_syncs': logs.filter(status=SyncLog.STATUS_SUCCESS).count(),
            'failed_syncs': logs.filter(status=SyncLog.STATUS_ERROR).count(),
            'running_syncs': logs.filter(status=SyncLog.STATUS_RUNNING).count(),
            'total_emails_processed': logs.aggregate(total=Count('emails_processed'))['total'] or 0,
            'total_attachments_processed': logs.aggregate(total=Count('attachments_processed'))['total'] or 0,
            'average_duration': 0,
        }

        # Calcul de la durée moyenne
        completed_logs = logs.filter(status__in=[SyncLog.STATUS_SUCCESS, SyncLog.STATUS_ERROR])
        if completed_logs.exists():
            durations = []
            for log in completed_logs:
                if log.get_duration():
                    durations.append(log.get_duration().total_seconds())

            if durations:
                stats['average_duration'] = sum(durations) / len(durations)

        return Response(stats)


@action(detail=False, methods=['get'], url_path='global-statistics')
def global_statistics(request):
    """
    Statistiques globales du système IMAP

    GET /api/imap/global-statistics/?days=30
    """
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    days = int(request.GET.get('days', 30))

    # Lancement de la tâche de génération des statistiques
    task = generate_email_statistics.delay(days)

    try:
        # Attente du résultat (timeout de 30 secondes)
        result = task.get(timeout=30)

        # Filtrage pour l'utilisateur actuel
        user_accounts = IMAPAccount.objects.filter(owner=request.user).values_list('id', flat=True)
        user_account_ids = [str(acc_id) for acc_id in user_accounts]

        # Filtrage des statistiques par compte
        filtered_account_stats = [
            stat for stat in result['account_statistics']
            if stat['account_id'] in user_account_ids
        ]
        result['account_statistics'] = filtered_account_stats

        return Response(result)

    except Exception as e:
        logger.error(f"Erreur génération statistiques globales: {e}")
        return Response({
            'error': f'Erreur génération des statistiques: {e}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
