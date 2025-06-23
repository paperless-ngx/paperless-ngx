import os

import debug_toolbar
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path
from django.urls import re_path
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import RedirectView
from django.views.static import serve
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter
from documents.views import WarehouseMoveRequestViewSet
from documents.views import CreatedDepartmentViewSet
from documents.views import ManageDepartmentViewSet
from documents.views import AcknowledgeTasksView, DocumentElasticSearch
from documents.views import (WebhookViewSet, SelectQueryViewSet, PostFolderView, MovedHistoryViewSet)
from documents.views import ContainerMoveHistoryViewSet
from documents.views import ApprovalUpdateMutipleView
from documents.views import ApprovalViewSet
from documents.views import ArchiveFontViewSet
from documents.views import BackupRecordViewSet
from documents.views import BulkDownloadView
from documents.views import BulkEditObjectsView
from documents.views import BulkEditView
from documents.views import BulkExportExcelFromFolderView
from documents.views import BulkExportExcelView
from documents.views import CorrespondentViewSet
from documents.views import CustomFieldViewSet
from documents.views import DocumentTypeViewSet
from documents.views import DossierFormViewSet
from documents.views import DossierViewSet
from documents.views import EdocTasksViewSet
from documents.views import FolderViewSet
from documents.views import FontLanguageViewSet
from documents.views import IndexView
from documents.views import LogViewSet
from documents.views import PostDocumentView
from documents.views import RemoteVersionView
from documents.views import SavedViewViewSet
from documents.views import SearchAutoCompleteView
from documents.views import SelectionDataView
from documents.views import ShareLinkViewSet
from documents.views import SharedLinkView
from documents.views import StatisticsCustomView
from documents.views import StatisticsView
from documents.views import StoragePathViewSet
from documents.views import SystemStatusView
from documents.views import SystemStorageStatusView
from documents.views import TagViewSet
from documents.views import TasksViewSet
from documents.views import TrashView
from documents.views import UiSettingsView
from documents.views import UnifiedSearchViewSet
from documents.views import WarehouseViewSet
from documents.views import WorkflowActionViewSet
from documents.views import WorkflowTriggerViewSet
from documents.views import WorkflowViewSet
from edoc.consumers import StatusConsumer
from edoc.views import ApplicationConfigurationViewSet, expired_view
from edoc.views import ContentTypeViewSet
from edoc.views import DisconnectSocialAccountView
from edoc.views import FaviconView
from edoc.views import GenerateAuthTokenView
from edoc.views import GroupViewSet
from edoc.views import ProfileView
from edoc.views import SocialAccountProvidersView
from edoc.views import UserViewSet
from edoc_mail.views import MailAccountTestView
from edoc_mail.views import MailAccountViewSet
from edoc_mail.views import MailRuleViewSet

api_router = DefaultRouter()
api_router.register(r"correspondents", CorrespondentViewSet)
api_router.register(r"document_types", DocumentTypeViewSet)
api_router.register(r"archive_fonts", ArchiveFontViewSet)
api_router.register(r"font_languages", FontLanguageViewSet)
api_router.register(r"documents", UnifiedSearchViewSet)
api_router.register(r"elastic_searchs", DocumentElasticSearch,
                    basename="elastic_searchs")
api_router.register(r"logs", LogViewSet, basename="logs")
api_router.register(r"tags", TagViewSet)
api_router.register(r"saved_views", SavedViewViewSet)
api_router.register(r"storage_paths", StoragePathViewSet)
api_router.register(r"tasks", TasksViewSet, basename="tasks")
api_router.register(r"edoc_tasks", EdocTasksViewSet, basename="edoc_tasks")
api_router.register(r"users", UserViewSet, basename="users")
api_router.register(r"groups", GroupViewSet, basename="groups")
api_router.register(r"mail_accounts", MailAccountViewSet)
api_router.register(r"mail_rules", MailRuleViewSet)
api_router.register(r"share_links", ShareLinkViewSet)
api_router.register(r"workflow_triggers", WorkflowTriggerViewSet)
api_router.register(r"workflow_actions", WorkflowActionViewSet)
api_router.register(r"workflows", WorkflowViewSet)
api_router.register(r"custom_fields", CustomFieldViewSet)
api_router.register(r"config", ApplicationConfigurationViewSet)
api_router.register(r"warehouses", WarehouseViewSet)
api_router.register(r"approvals", ApprovalViewSet)
api_router.register(r"content_types", ContentTypeViewSet,
                    basename="content_types")
api_router.register(r"folders", FolderViewSet)
api_router.register(r"dossiers", DossierViewSet)
api_router.register(r"dossier_forms", DossierFormViewSet)
api_router.register(r"backup_records", BackupRecordViewSet)
api_router.register(r'process_ocr', WebhookViewSet, basename='webhook')
# api_router.register(r"approvals", ApprovalViewSet)
api_router.register(r"content_types", ContentTypeViewSet,
                    basename="content_types")
api_router.register(r"history", MovedHistoryViewSet, basename='history')
api_router.register(r"container",ContainerMoveHistoryViewSet)
api_router.register(r"created_dpm", CreatedDepartmentViewSet)
api_router.register(r"manage_dpm", ManageDepartmentViewSet)
api_router.register(r"move", WarehouseMoveRequestViewSet, basename="moverequest")

urlpatterns = [
    re_path(
        r"^api/",
        include(
            [
                re_path(
                    "^auth/",
                    include(
                        ("rest_framework.urls", "rest_framework"),
                        namespace="rest_framework",
                    ),
                ),
                re_path(
                    "^search/autocomplete/",
                    SearchAutoCompleteView.as_view(),
                    name="autocomplete",
                ),
                # re_path(
                #     "^elastic_search/",
                #     DocumentElasticSearch.as_view({"get":"list"}),
                #     name="document_elastic_search",
                # ),
                re_path("^statistics/", StatisticsView.as_view(),
                        name="statistics"),
                re_path(
                    "^statistics_custom/",
                    StatisticsCustomView.as_view(),
                    name="statistics_custom",
                ),
                re_path(
                    "^documents/post_document/",
                    PostDocumentView.as_view(),
                    name="post_document",
                ),
                re_path(
                    "^documents/post_folder/",
                    PostFolderView.as_view(),
                    name="post_folder",
                ),
                re_path(
                    "^documents/bulk_edit/",
                    BulkEditView.as_view(),
                    name="bulk_edit",
                ),
                re_path(
                    "^documents/selection_data/",
                    SelectionDataView.as_view(),
                    name="selection_data",
                ), re_path(
                    "^documents/selection_query_data/",
                    SelectQueryViewSet.as_view({'get': 'list'}),
                    name="selection_query_data",
                ),
                re_path(
                    "^documents/bulk_download/",
                    BulkDownloadView.as_view(),
                    name="bulk_download",
                ),
                re_path(
                    "^documents/bulk_export_excel/",
                    BulkExportExcelView.as_view(),
                    name="bulk_export_excel",
                ),
                re_path(
                    "^documents/bulk_export_excel/",
                    BulkExportExcelView.as_view(),
                    name="bulk_export_excel",
                ),
                re_path(
                    "^folders/bulk_export_excel_folder/",
                    BulkExportExcelFromFolderView.as_view(),
                    name="bulk_export_excel_folder",
                ),
                re_path(
                    "^remote_version/",
                    RemoteVersionView.as_view(),
                    name="remoteversion",
                ),
                re_path("^ui_settings/", UiSettingsView.as_view(),
                        name="ui_settings"),
                re_path(
                    "^acknowledge_tasks/",
                    AcknowledgeTasksView.as_view(),
                    name="acknowledge_tasks",
                ),
                re_path(
                    "^update_approvals/",
                    ApprovalUpdateMutipleView.as_view(),
                    name="update_approvals",
                ),
                re_path(
                    "^mail_accounts/test/",
                    MailAccountTestView.as_view(),
                    name="mail_accounts_test",
                ),
                path("token/", views.obtain_auth_token),
                re_path(
                    "^bulk_edit_objects/",
                    BulkEditObjectsView.as_view(),
                    name="bulk_edit_objects",
                ),
                path("profile/generate_auth_token/",
                     GenerateAuthTokenView.as_view()),
                path(
                    "profile/disconnect_social_account/",
                    DisconnectSocialAccountView.as_view(),
                ),
                path(
                    "profile/social_account_providers/",
                    SocialAccountProvidersView.as_view(),
                ),
                re_path(
                    "^profile/",
                    ProfileView.as_view(),
                    name="profile_view",
                ),
                re_path(
                    "^status/",
                    SystemStatusView.as_view(),
                    name="system_status",
                ),
                re_path(
                    "^status_storage/",
                    SystemStorageStatusView.as_view(),
                    name="system_storage_status",
                ),
                re_path(
                    "^trash/",
                    TrashView.as_view(),
                    name="trash",
                ),
                *api_router.urls,
            ],
        ),
    ),
    re_path(r"share/(?P<slug>\w+)/?$", SharedLinkView.as_view()),
    re_path(r"expired/", expired_view),
    # re_path(r"check_expiration", CheckExpirationDate.as_view()),
    re_path(r"^favicon.ico$", FaviconView.as_view(), name="favicon"),
    re_path(r"admin/", admin.site.urls),
    re_path(
        r"^fetch/",
        include(
            [
                re_path(
                    r"^doc/(?P<pk>\d+)$",
                    RedirectView.as_view(
                        url=settings.BASE_URL + "api/documents/%(pk)s/download/",
                    ),
                ),
                re_path(
                    r"^doc/(?P<pk>\d+)$",
                    RedirectView.as_view(
                        url=settings.BASE_URL + "api/documents/%(pk)s/export_excel/",
                    ),
                ),
                re_path(
                    r"^thumb/(?P<pk>\d+)$",
                    RedirectView.as_view(
                        url=settings.BASE_URL + "api/documents/%(pk)s/thumb/",
                    ),
                ),
                re_path(
                    r"^preview/(?P<pk>\d+)$",
                    RedirectView.as_view(
                        url=settings.BASE_URL + "api/documents/%(pk)s/preview/",
                    ),
                ),
                re_path(
                    "^restore/",
                    RedirectView.as_view(
                        url=settings.BASE_URL + "api/backup_records/restore/",
                    ),
                    name="restore",
                ),
            ],
        ),
    ),
    re_path(
        r"^push$",
        csrf_exempt(
            RedirectView.as_view(
                url=settings.BASE_URL + "api/documents/post_document/",
            ),
        ),
    ),
    # Frontend assets TODO: this is pretty bad, but it works.
    path(
        "assets/<path:path>",
        RedirectView.as_view(
            url=settings.STATIC_URL + "frontend/en-US/assets/%(path)s",
        ),
        # TODO: with localization, this is even worse! :/
    ),
    # App logo
    re_path(
        r"^logo(?P<path>.*)$",
        serve,
        kwargs={"document_root": os.path.join(settings.MEDIA_ROOT, "logo")},
    ),
    # login, logout
    path("accounts/", include("allauth.urls")),
    # Root of the Frontend
    re_path(
        r".*",
        login_required(ensure_csrf_cookie(IndexView.as_view())),
        name="base",
    ),
]

websocket_urlpatterns = [
    path(settings.BASE_URL.lstrip("/") + "ws/status/",
         StatusConsumer.as_asgi()),
]

# Text in each page's <h1> (and above login form).
admin.site.site_header = "Edoc"
# Text at the end of each page's <title>.
admin.site.site_title = "Edoc"
# Text at the top of the admin index page.
admin.site.index_title = _("Edoc administration")

urlpatterns = [
                  re_path(r'^__debug__/', include(debug_toolbar.urls)),
              ] + urlpatterns
