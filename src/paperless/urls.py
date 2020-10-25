from django.conf.urls import include, url
from django.contrib import admin
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from paperless.views import FaviconView
from documents.views import (
    CorrespondentViewSet,
    DocumentViewSet,
    LogViewSet,
    TagViewSet,
    DocumentTypeViewSet,
    SearchView,
    IndexView
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
    url(r"^api/search/", SearchView.as_view(), name="search"),
    url(r"^api/token/", views.obtain_auth_token), url(r"^api/", include((api_router.urls, 'drf'), namespace="drf")),

    # Favicon
    url(r"^favicon.ico$", FaviconView.as_view(), name="favicon"),

    # The Django admin
    url(r"admin/", admin.site.urls),

    # Root of the Frontent
    url(r".*", IndexView.as_view()),

]

# Text in each page's <h1> (and above login form).
admin.site.site_header = 'Paperless'
# Text at the end of each page's <title>.
admin.site.site_title = 'Paperless'
# Text at the top of the admin index page.
admin.site.index_title = 'Paperless administration'
