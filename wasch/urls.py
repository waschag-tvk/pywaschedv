from django.conf.urls import url
from django.contrib.auth import views as auth_views

from . import views

app_name = 'wasch'

urlpatterns = [
    url(r'^$', views.index_view, name='index'),
    url(r'^login/$', auth_views.LoginView.as_view(template_name='wasch/login.html'), name='login'),
    # url(r'^login/check/$', views.check_login_view, name='check_login'),
    url(r'^logout/$', auth_views.LogoutView.as_view(next_page='/wasch/'), name='logout'),
    url(r'^stats/$', views.stats, name='stats'),
]
