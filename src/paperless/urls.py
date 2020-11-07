from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from paperless.consumers import StatusConsumer
from paperless.views import FaviconView
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

api_router = DefaultRouter()
api_router.register(r"correspondents", CorrespondentViewSet)
api_router.register(r"document_types", DocumentTypeViewSet)
api_router.register(r"documents", DocumentViewSet)
api_router.register(r"logs", LogViewSet)
api_router.register(r"tags", TagViewSet)


urlpatterns = [

    # API
    url(r"^api/auth/",include(('rest_framework.urls', 'rest_framework'), namespace="rest_framework")),
    url(r"^api/search/autocomplete/", SearchAutoCompleteView.as_view(), name="autocomplete"),
    url(r"^api/search/", SearchView.as_view(), name="search"),
    url(r"^api/statistics/", StatisticsView.as_view(), name="statistics"),
    url(r"^api/token/", views.obtain_auth_token), url(r"^api/", include((api_router.urls, 'drf'), namespace="drf")),

    # Favicon
    url(r"^favicon.ico$", FaviconView.as_view(), name="favicon"),

    # The Django admin
    url(r"admin/", admin.site.urls),

    # These redirects are here to support clients that use the old FetchView.
    url(
        r"^fetch/doc/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/download/'),
    ),
    url(
        r"^fetch/thumb/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/thumb/'),
    ),
    url(
        r"^fetch/preview/(?P<pk>\d+)$",
        RedirectView.as_view(url='/api/documents/%(pk)s/preview/'),
    ),
    url(r"^push$", csrf_exempt(RedirectView.as_view(url='/api/documents/post_document/'))),

    # Frontend assets TODO: this is pretty bad.
    path('assets/<path:path>', RedirectView.as_view(url='/static/assets/%(path)s')),

    # Root of the Frontent
    url(r".*", IndexView.as_view()),

]


websocket_urlpatterns = [
    re_path(r'ws/status/$', StatusConsumer.as_asgi()),
]

# Text in each page's <h1> (and above login form).
admin.site.site_header = 'Paperless'
# Text at the end of each page's <title>.
admin.site.site_title = 'Paperless'
# Text at the top of the admin index page.
admin.site.index_title = 'Paperless administration'
