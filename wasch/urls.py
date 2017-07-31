from django.conf.urls import url
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required

from . import views

app_name = 'wasch'

urlpatterns = [
    url(r'^$', views.index_view, name='index'),
    url(r'^welcome/$', views.welcome_view, name='welcome'),
    url(r'^login/$', auth_views.LoginView.as_view(template_name='wasch/login.html'), name='login'),
    # url(r'^login/check/$', views.check_login_view, name='check_login'),
    url(r'^logout/$', auth_views.LogoutView.as_view(next_page='/wasch/'), name='logout'),
    url(r'^stats/$', views.stats, name='stats'),
    url(
        r'^statsapi_appointments_per_day/$',
        login_required(views.AppointmentsPerDayChart.as_view()),
        name='statsapi_appointments_per_day'),
    url(
        r'^statsapi_appointments_per_floor/$',
        login_required(views.AppointmentsPerFloorChart.as_view()),
        name='statsapi_appointments_per_floor'),
]
