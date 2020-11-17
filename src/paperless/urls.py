from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter

from documents.views import (
    CorrespondentViewSet,
    DocumentViewSet,
    LogViewSet,
    TagViewSet,
    DocumentTypeViewSet,
    SearchView,
    IndexView,
    SearchAutoCompleteView,
    StatisticsView
)
from paperless.views import FaviconView

api_router = DefaultRouter()
api_router.register(r"correspondents", CorrespondentViewSet)
api_router.register(r"document_types", DocumentTypeViewSet)
api_router.register(r"documents", DocumentViewSet)
api_router.register(r"logs", LogViewSet)
api_router.register(r"tags", TagViewSet)


urlpatterns = [

    # API
    re_path(r"^api/auth/", include(('rest_framework.urls', 'rest_framework'), namespace="rest_framework")),
    re_path(r"^api/search/autocomplete/", SearchAutoCompleteView.as_view(), name="autocomplete"),
    re_path(r"^api/search/", SearchView.as_view(), name="search"),
    re_path(r"^api/statistics/", StatisticsView.as_view(), name="statistics"),
    re_path(r"^api/", include((api_router.urls, 'drf'), namespace="drf")),

    # Favicon
    re_path(r"^favicon.ico$", FaviconView.as_view(), name="favicon"),

    # The Django admin
    re_path(r"admin/", admin.site.urls),

    # These redirects are here to support clients that use the old FetchView.
    re_path(
        r"^fetch/doc/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/download/'),
    ),
    re_path(
        r"^fetch/thumb/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/thumb/'),
    ),
    re_path(
        r"^fetch/preview/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/preview/'),
    ),
    re_path(r"^push$", csrf_exempt(RedirectView.as_view(url='/api/documents/post_document/'))),

    # Frontend assets TODO: this is pretty bad.
    path('assets/<path:path>', RedirectView.as_view(url='/static/frontend/assets/%(path)s')),

    path('accounts/', include('django.contrib.auth.urls')),

    # Root of the Frontent
    re_path(r".*", login_required(IndexView.as_view())),

]

# Text in each page's <h1> (and above login form).
admin.site.site_header = 'Paperless-ng'
# Text at the end of each page's <title>.
admin.site.site_title = 'Paperless-ng'
# Text at the top of the admin index page.
admin.site.index_title = 'Paperless-ng administration'
