from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.serializers import ShoeSerializer
from backend.models import Shoe


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "shoe_count": Shoe.objects.count()})


class ShoeListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        shoes = (
            Shoe.objects.prefetch_related("sizes")
            .order_by("brand", "model")
        )
        serializer = ShoeSerializer(shoes, many=True)
        return Response(serializer.data)
