from rest_framework import serializers

from backend.models import Shoe, ShoeSize


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
