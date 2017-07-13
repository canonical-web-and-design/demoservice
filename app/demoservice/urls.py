"""demoservice URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

import os
from django.conf import settings
from django.conf.urls import include, url
from django.contrib.auth.decorators import login_required

from demoservice.views import (
    DemoIndexView,
    DemoStartView,
    DemoStopView,
    github_webhook,
)


def _login_required(function, *args, **kwargs):
    is_disabled = os.getenv('X_DISABLE_AUTH', 'false').lower() == 'true'
    if settings.DEBUG or is_disabled:
        return function
    return login_required(function, *args, **kwargs)


urlpatterns = [
    url(r'^openid/', include('django_openid_auth.urls')),
    url(r'^webhook/github$', github_webhook),
    url(
        r'^start$',
        _login_required(DemoStartView.as_view()),
        name='demo_start',
    ),
    url(
        r'^stop$',
        _login_required(DemoStopView.as_view()),
        name='demo_stop',
    ),
    url(
        r'^$',
        _login_required(DemoIndexView.as_view()),
        name='demo_index',
    ),
]
