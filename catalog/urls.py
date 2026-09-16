from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ProductViewSet,
    ReviewViewSet,
    WishlistViewSet,
    ActiveVisitorViewSet,
)

app_name = 'catalog'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'visitors', ActiveVisitorViewSet, basename='visitor')

urlpatterns = [
    path('', include(router.urls)),
]
