"""
Configuration des URLs pour le module IMAP Paperless-ngx

Routes API REST pour la gestion des comptes IMAP, e-mails,
pièces jointes, événements et synchronisation.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.urlpatterns import format_suffix_patterns

from .views import (
    IMAPAccountViewSet, EmailMessageViewSet, EmailAttachmentViewSet,
    EmailEventViewSet, SyncLogViewSet, global_statistics
)


# Configuration du routeur REST
router = DefaultRouter()
router.register(r'accounts', IMAPAccountViewSet, basename='imapaccount')
router.register(r'emails', EmailMessageViewSet, basename='emailmessage')
router.register(r'attachments', EmailAttachmentViewSet, basename='emailattachment')
router.register(r'events', EmailEventViewSet, basename='emailevent')
router.register(r'sync-logs', SyncLogViewSet, basename='synclog')

# URLs de l'application
app_name = 'paperless_imap'

urlpatterns = [
    # API REST
    path('api/imap/', include(router.urls)),

    # Endpoint pour les statistiques globales
    path('api/imap/global-statistics/', global_statistics, name='global-statistics'),

    # URLs des ViewSets avec endpoints personnalisés
    # Les URLs suivantes sont automatiquement générées par le routeur :

    # IMAPAccount endpoints:
    # GET    /api/imap/accounts/                     -> list
    # POST   /api/imap/accounts/                     -> create
    # GET    /api/imap/accounts/{id}/                -> retrieve
    # PUT    /api/imap/accounts/{id}/                -> update
    # PATCH  /api/imap/accounts/{id}/                -> partial_update
    # DELETE /api/imap/accounts/{id}/                -> destroy
    # POST   /api/imap/accounts/{id}/sync/           -> sync
    # POST   /api/imap/accounts/{id}/test_connection/ -> test_connection
    # GET    /api/imap/accounts/{id}/statistics/     -> statistics
    # GET    /api/imap/accounts/{id}/sync_logs/      -> sync_logs
    # POST   /api/imap/accounts/test_new_connection/ -> test_new_connection

    # EmailMessage endpoints:
    # GET    /api/imap/emails/                       -> list
    # GET    /api/imap/emails/{id}/                  -> retrieve
    # POST   /api/imap/emails/{id}/mark_read/        -> mark_read
    # POST   /api/imap/emails/{id}/mark_unread/      -> mark_unread
    # POST   /api/imap/emails/{id}/toggle_flag/      -> toggle_flag
    # POST   /api/imap/emails/{id}/categorize/       -> categorize
    # POST   /api/imap/emails/{id}/process_attachments/ -> process_attachments
    # POST   /api/imap/emails/bulk_actions/          -> bulk_actions

    # EmailAttachment endpoints:
    # GET    /api/imap/attachments/                  -> list
    # GET    /api/imap/attachments/{id}/             -> retrieve
    # POST   /api/imap/attachments/{id}/process/     -> process
    # GET    /api/imap/attachments/{id}/download/    -> download

    # EmailEvent endpoints:
    # GET    /api/imap/events/                       -> list
    # POST   /api/imap/events/                       -> create
    # GET    /api/imap/events/{id}/                  -> retrieve
    # PUT    /api/imap/events/{id}/                  -> update
    # PATCH  /api/imap/events/{id}/                  -> partial_update
    # DELETE /api/imap/events/{id}/                  -> destroy
    # POST   /api/imap/events/{id}/validate/         -> validate
    # GET    /api/imap/events/calendar_view/         -> calendar_view

    # SyncLog endpoints:
    # GET    /api/imap/sync-logs/                    -> list
    # GET    /api/imap/sync-logs/{id}/               -> retrieve
    # GET    /api/imap/sync-logs/statistics/         -> statistics
]

# Ajout du support des suffixes de format (ex: .json, .xml)
urlpatterns = format_suffix_patterns(urlpatterns)


# Documentation des paramètres d'API
"""
Paramètres de requête supportés:

=== IMAPAccount ===
List/Filter:
- is_active: bool (true/false)
- auth_method: str (password/oauth2)
- search: str (recherche dans name, server, username)
- ordering: str (name, created, last_sync, -created)
- page: int
- page_size: int (max 100)

Statistics:
- days: int (défaut: 30) - période en jours

Sync logs:
- limit: int (défaut: 10) - nombre de logs

=== EmailMessage ===
List/Filter:
- account: uuid
- folder: str
- category: str (personal/professional/newsletter/notification/spam/other)
- priority: str (low/normal/high)
- is_read: bool
- is_flagged: bool
- is_processed: bool
- date_sent_from: datetime ISO
- date_sent_to: datetime ISO
- sender_contains: str
- subject_contains: str
- has_attachments: bool
- has_events: bool
- search: str (recherche dans subject, sender, body_text)
- ordering: str (date_sent, date_received, subject, sender)
- page: int
- page_size: int (max 100)

Bulk actions:
- action: str (mark_read/mark_unread/categorize/delete/process_attachments)
- email_ids: list[uuid]
- category: str (requis pour action categorize)

=== EmailAttachment ===
List/Filter:
- is_processed: bool
- is_supported_format: bool
- content_type: str
- search: str (recherche dans filename)
- ordering: str (filename, size, created)
- page: int
- page_size: int (max 100)

=== EmailEvent ===
List/Filter:
- event_type: str (meeting/appointment/deadline/reminder/other)
- is_validated: bool
- all_day: bool
- search: str (recherche dans title, description, location)
- ordering: str (start_date, created, confidence_score)
- page: int
- page_size: int (max 100)

Calendar view:
- start: datetime ISO (date de début)
- end: datetime ISO (date de fin)

=== SyncLog ===
List/Filter:
- status: str (running/success/error)
- account: uuid
- ordering: str (start_time, end_time, emails_processed)
- page: int
- page_size: int (max 100)

Statistics:
- days: int (défaut: 7) - période en jours

=== Réponses d'erreur communes ===
400 Bad Request: Paramètres invalides
401 Unauthorized: Authentification requise
403 Forbidden: Permissions insuffisantes
404 Not Found: Ressource introuvable
422 Unprocessable Entity: Données invalides
500 Internal Server Error: Erreur serveur

=== Formats de réponse ===
Les APIs supportent les formats JSON (défaut) et XML.
Utilisez l'en-tête Accept ou le suffixe d'URL:
- GET /api/imap/accounts/ (JSON)
- GET /api/imap/accounts.json (JSON explicite)
- GET /api/imap/accounts.xml (XML)

=== Pagination ===
Toutes les listes utilisent la pagination:
{
  "count": 150,
  "next": "http://example.com/api/imap/emails/?page=2",
  "previous": null,
  "results": [...]
}

=== Authentification ===
Toutes les APIs requièrent une authentification.
Utilisez l'authentification de session Django ou les tokens API.

=== Permissions ===
Les utilisateurs ne voient que leurs propres données :
- Comptes IMAP créés par eux
- E-mails de leurs comptes
- Pièces jointes de leurs e-mails
- Événements de leurs e-mails
- Logs de leurs comptes
"""
