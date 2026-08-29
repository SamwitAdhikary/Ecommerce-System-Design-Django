from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import ThrottledTokenObtainPairView, LogoutView, SecurityProbeView

app_name = 'users'

urlpatterns = [
    # JWT Authentication & Token Lifecycle endpoints
    path('token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/logout/', LogoutView.as_view(), name='token_logout'),
    path('probe/', SecurityProbeView.as_view(), name='security_probe'),
]
