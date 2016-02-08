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
from django.conf.urls import url, static
from django.contrib import admin

from documents.views import PdfView, PushView

urlpatterns = [
    url(r"^fetch/(?P<pk>\d+)$", PdfView.as_view(), name="fetch"),
    url(r'', admin.site.urls),
] + static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.UPLOAD_SHARED_SECRET:
    urlpatterns.insert(0, url(r"^push$", PushView.as_view(), name="push"))
