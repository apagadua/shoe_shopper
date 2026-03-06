from rest_framework import serializers

from backend.models import Measurement, Shoe, ShoeSize


class ShoeSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoeSize
        fields = ["id", "us_size", "width", "is_available"]


class ShoeSerializer(serializers.ModelSerializer):
    sizes = ShoeSizeSerializer(many=True, read_only=True)

    class Meta:
        model = Shoe
        fields = [
            "id",
            "brand",
            "model",
            "gender",
            "price_usd",
            "shoe_image_url",
            "product_url",
            "sizes",
        ]


class MeasurementUploadSerializer(serializers.Serializer):
    image = serializers.FileField()
    image_width_px = serializers.IntegerField(required=False, min_value=1)
    image_height_px = serializers.IntegerField(required=False, min_value=1)


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = [
            "id",
            "status",
            "image_url",
            "image_width_px",
            "image_height_px",
            "created_at",
        ]
