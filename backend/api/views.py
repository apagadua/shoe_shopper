import os
import uuid
from datetime import timedelta

from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.serializers import (
    MeasurementSerializer,
    MeasurementUploadSerializer,
    ShoeSerializer,
)
from backend.models import GuestSession, Measurement, Shoe


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


class MeasurementUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = MeasurementUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        extension = os.path.splitext(image_file.name)[1] or ".jpg"
        storage_path = f"measurements/{uuid.uuid4()}{extension}"
        saved_path = default_storage.save(storage_path, image_file)

        image_url = default_storage.url(saved_path)
        if request is not None:
            image_url = request.build_absolute_uri(image_url)

        guest_session = GuestSession.objects.create(
            expires_at=timezone.now() + timedelta(days=30)
        )

        measurement = Measurement.objects.create(
            guest_session=guest_session,
            status=Measurement.Status.UPLOADED,
            image_url=image_url,
            image_width_px=serializer.validated_data.get("image_width_px"),
            image_height_px=serializer.validated_data.get("image_height_px"),
        )

        output = MeasurementSerializer(measurement).data
        return Response(output, status=status.HTTP_201_CREATED)
