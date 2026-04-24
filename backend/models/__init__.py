import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.TextField(null=True, blank=True)
    avatar_url = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profile"


class GuestSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "guest_session"
        indexes = [
            models.Index(fields=["expires_at"], name="idx_guest_session_expires_at"),
        ]


class Measurement(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        COMPLETE = "complete", "Complete"
        ERROR = "error", "Error"

    class PaperType(models.TextChoices):
        LETTER = "letter", "Letter"
        A4 = "a4", "A4"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="measurements",
    )
    guest_session = models.ForeignKey(
        GuestSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="measurements",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    image_url = models.TextField()
    image_width_px = models.IntegerField(null=True, blank=True)
    image_height_px = models.IntegerField(null=True, blank=True)
    length_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    width_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    area_sq_in = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    perimeter_in = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    paper_type = models.CharField(max_length=10, choices=PaperType.choices, null=True, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    algorithm_version = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "measurement"
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(guest_session__isnull=True))
                    | (Q(user__isnull=True) & Q(guest_session__isnull=False))
                ),
                name="chk_measurement_owner",
            ),
            models.CheckConstraint(
                condition=Q(length_in__isnull=True) | Q(length_in__gt=0),
                name="chk_measurement_length_positive",
            ),
            models.CheckConstraint(
                condition=Q(width_in__isnull=True) | Q(width_in__gt=0),
                name="chk_measurement_width_positive",
            ),
            models.CheckConstraint(
                condition=Q(area_sq_in__isnull=True) | Q(area_sq_in__gt=0),
                name="chk_measurement_area_positive",
            ),
            models.CheckConstraint(
                condition=Q(perimeter_in__isnull=True) | Q(perimeter_in__gt=0),
                name="chk_measurement_perimeter_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="idx_measurement_user_created"),
            models.Index(fields=["guest_session", "-created_at"], name="idx_measurement_guest_created"),
            models.Index(fields=["status"], name="idx_measurement_status"),
        ]


class Shoe(models.Model):
    class Gender(models.TextChoices):
        WOMEN = "women", "Women"
        MEN = "men", "Men"
        UNISEX = "unisex", "Unisex"
        KIDS = "kids", "Kids"
        UNKNOWN = "unknown", "Unknown"

    brand = models.TextField()
    model = models.TextField()
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.UNKNOWN)
    function_tags = ArrayField(models.TextField(), default=list, blank=True)
    style_tags = ArrayField(models.TextField(), default=list, blank=True)
    attributes_json = models.JSONField(default=dict, blank=True)
    insole_length_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    insole_width_in = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    insole_area_sq_in = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    insole_perimeter_in = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    shoe_image_url = models.TextField(null=True, blank=True)
    product_url = models.TextField(null=True, blank=True)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shoe"
        indexes = [
            models.Index(fields=["brand", "model"], name="idx_shoe_brand_model"),
            GinIndex(fields=["function_tags"], name="idx_shoe_tags_gin_function"),
            GinIndex(fields=["style_tags"], name="idx_shoe_tags_gin_style"),
        ]


class ShoeSize(models.Model):
    class Width(models.TextChoices):
        NARROW = "narrow", "Narrow"
        REGULAR = "regular", "Regular"
        WIDE = "wide", "Wide"
        EXTRA_WIDE = "extra_wide", "Extra Wide"

    shoe = models.ForeignKey(Shoe, on_delete=models.CASCADE, related_name="sizes")
    us_size = models.DecimalField(max_digits=4, decimal_places=1)
    width = models.CharField(max_length=12, choices=Width.choices, default=Width.REGULAR)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shoe_size"
        constraints = [
            models.UniqueConstraint(fields=["shoe", "us_size", "width"], name="shoe_size_shoe_id_us_size_width_key"),
        ]
        indexes = [
            models.Index(fields=["shoe", "us_size", "width", "is_available"], name="idx_shoe_size_lookup"),
        ]


class UserCollection(models.Model):
    class CollectionType(models.TextChoices):
        WISHLIST = "wishlist", "Wishlist"
        OWNED = "owned", "Owned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
    )
    shoe = models.ForeignKey(Shoe, on_delete=models.CASCADE, related_name="collections")
    type = models.CharField(max_length=10, choices=CollectionType.choices)
    size = models.TextField(null=True, blank=True)
    color = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_collection"
        constraints = [
            models.UniqueConstraint(fields=["user", "shoe", "type"], name="user_collection_user_id_shoe_id_type_key"),
        ]
        indexes = [
            models.Index(fields=["user", "type", "-created_at"], name="idx_coll_user_type_created"),
        ]


class Recommendation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    shoe = models.ForeignKey(Shoe, on_delete=models.CASCADE, related_name="recommendations")
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    run_id = models.UUIDField()
    rank = models.IntegerField()
    score = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    algorithm_version = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendation"
        constraints = [
            models.CheckConstraint(condition=Q(rank__gt=0), name="chk_recommendation_rank_positive"),
            models.UniqueConstraint(fields=["user", "run_id", "rank"], name="recommendation_user_id_run_id_rank_key"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="idx_reco_user_created"),
            models.Index(fields=["user", "shoe"], name="idx_reco_user_shoe"),
            models.Index(fields=["user", "run_id", "rank"], name="idx_reco_user_run_rank"),
        ]


class TrainingImage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_images",
    )
    image_url = models.TextField()
    label_json = models.JSONField(default=dict, blank=True)
    in_dataset = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "training_image"
        indexes = [
            models.Index(fields=["in_dataset"], name="idx_training_in_dataset"),
            models.Index(fields=["user", "-created_at"], name="idx_training_user_created"),
        ]

class UserFeedback(models.Model):
    class FeedbackType(models.TextChoices):
        TOO_NARROW = "too_narrow", "Too Narrow"
        TOO_WIDE = "too_wide", "Too Wide"
        TOO_SHORT = "too_short", "Too Short"
        TOO_LONG = "too_long", "Too Long"
        PERFECT = "perfect", "Perfect"
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    shoe = models.ForeignKey(
        Shoe,
        on_delete=models.PROTECT,
        related_name="feedback"
    )
    
    feedback_type = models.CharField(
        max_length=20,
        choices=FeedbackType.choices
    )

    current_tolerances = models.JSONField()

    fit_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    measurements = models.ForeignKey(
        Measurement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    severity_rating = models.IntegerField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_feedback"
        indexes = [
            models.Index(fields=["shoe"], name="idx_feedback_shoe"),
            models.Index(fields=["created_at"], name="idx_feedback_created_at"),
            models.Index(fields=["feedback_type"], name="idx_feedback_type")
        ]

__all__ = [
    "Profile",
    "GuestSession",
    "Measurement",
    "Shoe",
    "ShoeSize",
    "UserCollection",
    "Recommendation",
    "TrainingImage",
]
