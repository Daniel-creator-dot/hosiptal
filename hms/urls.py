"""
URL configuration for hms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout/password-change
    path('hms/', include('hospital.urls')),  # Frontend hospital management views
    path('hms/telemedicine/', include('hospital.urls_telemedicine')),  # Telemedicine URLs
    
    # Redirect legacy URLs to /hms/ prefix
    re_path(r'^patients/(?P<pk>[0-9a-f-]+)/$', RedirectView.as_view(url='/hms/patients/%(pk)s/', permanent=True)),
    re_path(r'^patients/$', RedirectView.as_view(url='/hms/patients/', permanent=True)),
    
    path('api/', include('rest_framework.urls')),
    path('api/hospital/', include('hospital.api_urls')),  # REST API
    # path('api/auth/', include('rest_framework_simplejwt.urls')),  # Temporarily disabled
    path('api/allauth/', include('allauth.urls')),
    path('health/', include('health_check.urls')),
    path('prometheus/', include('django_prometheus.urls')),
]

# Add debug toolbar URLs in development - DISABLED for performance
if False and settings.DEBUG:  # Disabled for performance
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
        path('silk/', include('silk.urls', namespace='silk')),
    ]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
