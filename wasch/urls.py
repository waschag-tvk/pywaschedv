from django.conf.urls import url

from . import views

app_name = 'wasch'

urlpatterns = [
    url(r'^login/$', views.login_view, name='login'),
    url(r'^login/check/$', views.check_login_view, name='check_login'),
]
