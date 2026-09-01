from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ThrottledTokenObtainPairView,
    LogoutView,
    UserViewSet,
    VerifyOTPView,
    ResendOTPView
)

router = DefaultRouter()
router.register(r'profile', UserViewSet, basename='profile')

urlpatterns = [
    # Router endpoints (e.g. /api/users/profile/me/)
    path('', include(router.urls)),
    
    # Registration & OTP Verification
    path('register/', UserViewSet.as_view({'post': 'create'}), name='user-register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    
    # JWT Authentication
    path('token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
]
