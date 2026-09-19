from decimal import Decimal
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import SiteSettings, ShippingZone
from .serializers import (
    SiteSettingsSerializer,
    ShippingZoneSerializer,
    ShippingEstimateRequestSerializer,
    ShippingEstimateResponseSerializer,
)


class SiteSettingsView(APIView):
    """
    Public endpoint providing storefront configuration, order value limits,
    standard shipping fees, and active payment surcharges.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        settings = SiteSettings.get_solo()
        serializer = SiteSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ShippingEstimateView(APIView):
    """
    Calculates dynamic shipping fees, free shipping eligibility, and COD surcharges
    given a destination state, cart subtotal, and payment preference.
    Supports both POST payloads and GET query parameters.
    """
    permission_classes = [AllowAny]

    def _process_estimate(self, raw_data):
        serializer = ShippingEstimateRequestSerializer(data=raw_data)
        serializer.is_valid(raise_exception=True)

        state = serializer.validated_data.get('state', '')
        subtotal = serializer.validated_data.get('subtotal', Decimal('0.00'))
        is_cod = serializer.validated_data.get('is_cod', False)

        settings = SiteSettings.get_solo()
        estimate_data = settings.calculate_shipping(
            state=state,
            subtotal=subtotal,
            is_cod=is_cod
        )

        response_serializer = ShippingEstimateResponseSerializer(estimate_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        return self._process_estimate(request.query_params)

    def post(self, request, *args, **kwargs):
        return self._process_estimate(request.data)


class ShippingZoneViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint listing active regional shipping zones and covered states.
    """
    permission_classes = [AllowAny]
    queryset = ShippingZone.objects.filter(is_active=True)
    serializer_class = ShippingZoneSerializer
