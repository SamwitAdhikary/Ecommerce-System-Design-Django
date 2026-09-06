from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet

app_name = 'catalog'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
]
