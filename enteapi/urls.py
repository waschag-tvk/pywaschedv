from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'appointment', views.AppointmentViewSet, base_name='appointment')

urlpatterns = [
    url(r'^v1/', include(router.urls)),
]
