from django.conf.urls import url, include
from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token
from . import views

router = routers.DefaultRouter()
router.register(r'appointment', views.AppointmentViewSet, base_name='appointment')

urlpatterns = [
    url(r'^v1/', include(router.urls)),
    url(r'^token-auth/', obtain_jwt_token),
]
