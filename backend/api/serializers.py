from rest_framework import serializers

from backend.models import Shoe, ShoeSize
from backend.services.fit_algorithm import status_label


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


class RecommendationSerializer(serializers.Serializer):
    """Serializes a {shoe, fit} dict produced by RecommendationsView."""

    id               = serializers.SerializerMethodField()
    brand            = serializers.SerializerMethodField()
    model            = serializers.SerializerMethodField()
    gender           = serializers.SerializerMethodField()
    price_usd        = serializers.SerializerMethodField()
    shoe_image_url   = serializers.SerializerMethodField()
    product_url      = serializers.SerializerMethodField()
    sizes            = serializers.SerializerMethodField()
    function_tags    = serializers.SerializerMethodField()
    style_tags       = serializers.SerializerMethodField()
    attributes_json  = serializers.SerializerMethodField()
    fit_score        = serializers.SerializerMethodField()
    fit_status       = serializers.SerializerMethodField()
    fit_status_label = serializers.SerializerMethodField()
    fit_profile      = serializers.SerializerMethodField()
    fit_flags        = serializers.SerializerMethodField()
    fit_dimensions   = serializers.SerializerMethodField()
    reject_reason    = serializers.SerializerMethodField()
    recommended_size = serializers.SerializerMethodField()
    estimated_us_size = serializers.SerializerMethodField()

    def get_id(self, obj):             return obj["shoe"].id
    def get_brand(self, obj):          return obj["shoe"].brand
    def get_model(self, obj):          return obj["shoe"].model
    def get_gender(self, obj):         return obj["shoe"].gender
    def get_price_usd(self, obj):      return str(obj["shoe"].price_usd) if obj["shoe"].price_usd else None
    def get_shoe_image_url(self, obj): return obj["shoe"].shoe_image_url
    def get_product_url(self, obj):    return obj["shoe"].product_url
    def get_function_tags(self, obj):  return obj["shoe"].function_tags or []
    def get_style_tags(self, obj):     return obj["shoe"].style_tags or []

    def get_sizes(self, obj):
        return ShoeSizeSerializer(obj["shoe"].sizes.all(), many=True).data

    def get_attributes_json(self, obj): return obj.get("attributes", {})

    def get_fit_score(self, obj):        return obj["fit"]["total_score"]
    def get_fit_status(self, obj):       return obj["fit"]["status"]
    def get_fit_status_label(self, obj): return status_label(obj["fit"]["status"])
    def get_fit_profile(self, obj):      return obj["fit"]["profile_used"]
    def get_fit_flags(self, obj):        return obj["fit"]["flags"]
    def get_fit_dimensions(self, obj):   return obj["fit"]["dimensions"]
    def get_reject_reason(self, obj):      return obj["fit"]["reject_reason"]
    def get_recommended_size(self, obj):  return obj.get("recommended_size")
    def get_estimated_us_size(self, obj): return obj["fit"].get("estimated_us_size")
