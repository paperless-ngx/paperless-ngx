"""paperless URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Import the include() function: from django.conf.urls import url, include
    3. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf import settings
from django.conf.urls import url, static, include
from django.contrib import admin

from rest_framework.routers import DefaultRouter

from documents.views import (
    IndexView, FetchView, PushView,
    CorrespondentViewSet, TagViewSet, DocumentViewSet, LogViewSet
)
from reminders.views import ReminderViewSet

router = DefaultRouter()
router.register(r"correspondents", CorrespondentViewSet)
router.register(r"documents", DocumentViewSet)
router.register(r"logs", LogViewSet)
router.register(r"reminders", ReminderViewSet)
router.register(r"tags", TagViewSet)

urlpatterns = [

    # API
    url(
        r"^api/auth/",
        include('rest_framework.urls', namespace="rest_framework")
    ),
    url(r"^api/", include(router.urls, namespace="drf")),

    # Normal pages (coming soon)
    # url(r"^$", IndexView.as_view(), name="index"),

    # File downloads
    url(
        r"^fetch/(?P<kind>doc|thumb)/(?P<pk>\d+)$",
        FetchView.as_view(),
        name="fetch"
    ),

    # The Django admin
    url(r"admin/", admin.site.urls),
    url(r"", admin.site.urls),  # This is going away

] + static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.SHARED_SECRET:
    urlpatterns.insert(0, url(r"^push$", PushView.as_view(), name="push"))

# Text in each page's <h1> (and above login form).
admin.site.site_header = 'Paperless'
# Text at the end of each page's <title>.
admin.site.site_title = 'Paperless'
# Text at the top of the admin index page.
admin.site.index_title = 'Paperless administration'
