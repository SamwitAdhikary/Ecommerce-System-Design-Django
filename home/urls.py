from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteSettingsView, ShippingEstimateView, ShippingZoneViewSet

app_name = 'home'

router = DefaultRouter()
router.register(r'shipping-zones', ShippingZoneViewSet, basename='shipping-zone')

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('shipping-estimate/', ShippingEstimateView.as_view(), name='shipping-estimate'),
    path('shipping_estimate/', ShippingEstimateView.as_view(), name='shipping_estimate_alias'),
    path('', include(router.urls)),
]
