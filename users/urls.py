from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ThrottledTokenObtainPairView,
    LogoutView,
    SecurityProbeView,
    UserViewSet,
    AddressViewSet,
    WalletTransactionViewSet,
    VerifyOTPView,
    ResendOTPView,
    PasswordResetView,
    PasswordResetConfirmView,
)

router = DefaultRouter()
router.register(r'profile', UserViewSet, basename='profile')
router.register(r'addresses', AddressViewSet, basename='addresses')
router.register(r'wallet_transactions', WalletTransactionViewSet, basename='wallet_transactions')

urlpatterns = [
    # Router endpoints (e.g. /api/users/profile/me/, /api/users/addresses/, /api/users/wallet_transactions/)
    path('', include(router.urls)),
    
    # Registration & OTP Verification
    path('register/', UserViewSet.as_view({'post': 'create'}), name='user-register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    
    # Cryptographic Password Reset
    path('password-reset/', PasswordResetView.as_view(), name='password-reset'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    # JWT Authentication & Probe
    path('token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('probe/', SecurityProbeView.as_view(), name='security-probe'),
]
