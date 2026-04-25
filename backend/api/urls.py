from django.urls import path

from backend.api.views import DeleteAccountView, FootMeasureView, GoogleLoginView, HealthView, ShoeListView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("shoes/", ShoeListView.as_view(), name="shoe-list"),
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/delete/", DeleteAccountView.as_view(), name="delete-account"),
    path("foot/measure/", FootMeasureView.as_view(), name="foot-measure"),
]
