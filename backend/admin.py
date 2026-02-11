from django.contrib import admin

from .models import (
    GuestSession,
    Measurement,
    Profile,
    Recommendation,
    Shoe,
    ShoeSize,
    TrainingImage,
    UserCollection,
)

admin.site.register(Profile)
admin.site.register(GuestSession)
admin.site.register(Measurement)
admin.site.register(Shoe)
admin.site.register(ShoeSize)
admin.site.register(UserCollection)
admin.site.register(Recommendation)
admin.site.register(TrainingImage)
