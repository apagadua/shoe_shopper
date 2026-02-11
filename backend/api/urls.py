from django.urls import path

from backend.api.views import HealthView, ShoeListView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("shoes/", ShoeListView.as_view(), name="shoe-list"),
]
