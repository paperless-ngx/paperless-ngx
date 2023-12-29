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
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from documents.views import AcknowledgeTasksView
from documents.views import BulkDownloadView
from documents.views import BulkEditObjectPermissionsView
from documents.views import BulkEditView
from documents.views import ConsumptionTemplateViewSet
from documents.views import CorrespondentViewSet
from documents.views import CustomFieldViewSet
from documents.views import DocumentTypeViewSet
from documents.views import IndexView
from documents.views import LogViewSet
from documents.views import PostDocumentView
from documents.views import RemoteVersionView
from documents.views import SavedViewViewSet
from documents.views import SearchAutoCompleteView
from documents.views import SelectionDataView
from documents.views import SharedLinkView
from documents.views import ShareLinkViewSet
from documents.views import StatisticsView
from documents.views import StoragePathViewSet
from documents.views import TagViewSet
from documents.views import TasksViewSet
from documents.views import UiSettingsView
from documents.views import UnifiedSearchViewSet
from paperless.consumers import StatusConsumer
from paperless.views import ApplicationConfigurationViewSet
from paperless.views import FaviconView
from paperless.views import GenerateAuthTokenView
from paperless.views import GroupViewSet
from paperless.views import ProfileView
from paperless.views import UserViewSet
from paperless_mail.views import MailAccountTestView
from paperless_mail.views import MailAccountViewSet
from paperless_mail.views import MailRuleViewSet

api_router = DefaultRouter()
api_router.register(r"correspondents", CorrespondentViewSet)
api_router.register(r"document_types", DocumentTypeViewSet)
api_router.register(r"documents", UnifiedSearchViewSet)
api_router.register(r"logs", LogViewSet, basename="logs")
api_router.register(r"tags", TagViewSet)
api_router.register(r"saved_views", SavedViewViewSet)
api_router.register(r"storage_paths", StoragePathViewSet)
api_router.register(r"tasks", TasksViewSet, basename="tasks")
api_router.register(r"users", UserViewSet, basename="users")
api_router.register(r"groups", GroupViewSet, basename="groups")
api_router.register(r"mail_accounts", MailAccountViewSet)
api_router.register(r"mail_rules", MailRuleViewSet)
api_router.register(r"share_links", ShareLinkViewSet)
api_router.register(r"consumption_templates", ConsumptionTemplateViewSet)
api_router.register(r"custom_fields", CustomFieldViewSet)
api_router.register(r"config", ApplicationConfigurationViewSet)


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
                re_path("^statistics/", StatisticsView.as_view(), name="statistics"),
                re_path(
                    "^documents/post_document/",
                    PostDocumentView.as_view(),
                    name="post_document",
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
                ),
                re_path(
                    "^documents/bulk_download/",
                    BulkDownloadView.as_view(),
                    name="bulk_download",
                ),
                re_path(
                    "^remote_version/",
                    RemoteVersionView.as_view(),
                    name="remoteversion",
                ),
                re_path("^ui_settings/", UiSettingsView.as_view(), name="ui_settings"),
                re_path(
                    "^acknowledge_tasks/",
                    AcknowledgeTasksView.as_view(),
                    name="acknowledge_tasks",
                ),
                re_path(
                    "^mail_accounts/test/",
                    MailAccountTestView.as_view(),
                    name="mail_accounts_test",
                ),
                path("token/", views.obtain_auth_token),
                re_path(
                    "^bulk_edit_object_perms/",
                    BulkEditObjectPermissionsView.as_view(),
                    name="bulk_edit_object_permissions",
                ),
                path("profile/generate_auth_token/", GenerateAuthTokenView.as_view()),
                re_path(
                    "^profile/",
                    ProfileView.as_view(),
                    name="profile_view",
                ),
                *api_router.urls,
            ],
        ),
    ),
    re_path(r"share/(?P<slug>\w+)/?$", SharedLinkView.as_view()),
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
    ),
    # TODO: with localization, this is even worse! :/
    # login, logout
    path("accounts/", include("django.contrib.auth.urls")),
    # Root of the Frontend
    re_path(
        r".*",
        login_required(ensure_csrf_cookie(IndexView.as_view())),
        name="base",
    ),
]


websocket_urlpatterns = [
    path(settings.BASE_URL.lstrip("/") + "ws/status/", StatusConsumer.as_asgi()),
]

# Text in each page's <h1> (and above login form).
admin.site.site_header = "Paperless-ngx"
# Text at the end of each page's <title>.
admin.site.site_title = "Paperless-ngx"
# Text at the top of the admin index page.
admin.site.index_title = _("Paperless-ngx administration")
