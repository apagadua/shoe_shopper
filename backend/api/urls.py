from django.urls import path

from backend.api.views import (
    DeleteAccountView,
    DevMockMeasurementView,
    FootMeasureView,
    GoogleLoginView,
    HealthView,
    LatestMeasurementView,
    ProfileView,
    RecommendationsView,
    ShoeListView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("shoes/", ShoeListView.as_view(), name="shoe-list"),
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/delete/", DeleteAccountView.as_view(), name="delete-account"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("foot/measure/", FootMeasureView.as_view(), name="foot-measure"),
    path("measurements/latest/", LatestMeasurementView.as_view(), name="latest-measurement"),
    path("recommendations/", RecommendationsView.as_view(), name="recommendations"),
    path("dev/mock-measurement/", DevMockMeasurementView.as_view(), name="dev-mock-measurement"),
]
