from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from django.utils.translation import gettext_lazy as _

from django.conf import settings

from paperless.consumers import StatusConsumer
from documents.views import (
    CorrespondentViewSet,
    UnifiedSearchViewSet,
    LogViewSet,
    TagViewSet,
    DocumentTypeViewSet,
    IndexView,
    SearchAutoCompleteView,
    StatisticsView,
    PostDocumentView,
    SavedViewViewSet,
    BulkEditView,
    SelectionDataView,
    BulkDownloadView
)
from paperless.views import FaviconView

api_router = DefaultRouter()
api_router.register(r"correspondents", CorrespondentViewSet)
api_router.register(r"document_types", DocumentTypeViewSet)
api_router.register(r"documents", UnifiedSearchViewSet)
api_router.register(r"logs", LogViewSet, basename="logs")
api_router.register(r"tags", TagViewSet)
api_router.register(r"saved_views", SavedViewViewSet)


urlpatterns = [
    re_path(r"^api/", include([
        re_path(r"^auth/",
                include(('rest_framework.urls', 'rest_framework'),
                        namespace="rest_framework")),

        re_path(r"^search/autocomplete/",
                SearchAutoCompleteView.as_view(),
                name="autocomplete"),

        re_path(r"^statistics/",
                StatisticsView.as_view(),
                name="statistics"),

        re_path(r"^documents/post_document/", PostDocumentView.as_view(),
                name="post_document"),

        re_path(r"^documents/bulk_edit/", BulkEditView.as_view(),
                name="bulk_edit"),

        re_path(r"^documents/selection_data/", SelectionDataView.as_view(),
                name="selection_data"),

        re_path(r"^documents/bulk_download/", BulkDownloadView.as_view(),
                name="bulk_download"),

        path('token/', views.obtain_auth_token)

    ] + api_router.urls)),

    re_path(r"^favicon.ico$", FaviconView.as_view(), name="favicon"),

    re_path(r"admin/", admin.site.urls),

    re_path(r"^fetch/", include([
        re_path(
            r"^doc/(?P<pk>\d+)$",
            RedirectView.as_view(url=settings.BASE_URL +
                                 'api/documents/%(pk)s/download/'),
        ),
        re_path(
            r"^thumb/(?P<pk>\d+)$",
            RedirectView.as_view(url=settings.BASE_URL +
                                 'api/documents/%(pk)s/thumb/'),
        ),
        re_path(
            r"^preview/(?P<pk>\d+)$",
            RedirectView.as_view(url=settings.BASE_URL +
                                 'api/documents/%(pk)s/preview/'),
        ),
    ])),

    re_path(r"^push$", csrf_exempt(
        RedirectView.as_view(url=settings.BASE_URL +
                             'api/documents/post_document/'))),

    # Frontend assets TODO: this is pretty bad, but it works.
    path('assets/<path:path>',
         RedirectView.as_view(url=settings.STATIC_URL +
                              'frontend/en-US/assets/%(path)s')),
    # TODO: with localization, this is even worse! :/

    # login, logout
    path('accounts/', include('django.contrib.auth.urls')),

    # Root of the Frontent
    re_path(r".*", login_required(IndexView.as_view()), name='base'),
]


websocket_urlpatterns = [
    re_path(r'ws/status/$', StatusConsumer.as_asgi()),
]

# Text in each page's <h1> (and above login form).
admin.site.site_header = 'Paperless-ng'
# Text at the end of each page's <title>.
admin.site.site_title = 'Paperless-ng'
# Text at the top of the admin index page.
admin.site.index_title = _('Paperless-ng administration')
