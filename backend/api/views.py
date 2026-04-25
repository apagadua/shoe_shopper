import base64
import math

import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.serializers import ShoeSerializer
from backend.models import Profile, Shoe

User = get_user_model()


PAPER_WIDTH_LETTER = 8.5        # US Letter short side, inches
PAPER_WIDTH_A4 = 210 / 25.4    # A4 short side, inches (~8.268)

PAPER_LABELS = {
    'letter': 'US Letter',
    'a4': 'A4',
}


class FootMeasureView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"detail": "image field required"}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = image_file.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        workspace = settings.ROBOFLOW_WORKSPACE
        project = settings.ROBOFLOW_PROJECT
        api_key = settings.ROBOFLOW_API_KEY

        if not all([workspace, project, api_key]):
            return Response(
                {"detail": "Roboflow not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Resolve paper size: explicit override > IP geo > Letter fallback
        paper_size_param = request.data.get("paper_size", "").lower()
        if paper_size_param == "letter":
            paper_width_in = PAPER_WIDTH_LETTER
            paper_size_used = "letter"
        elif paper_size_param == "a4":
            paper_width_in = PAPER_WIDTH_A4
            paper_size_used = "a4"
        else:
            xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
            client_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
            try:
                geo = http_requests.get(
                    f"http://ip-api.com/json/{client_ip}",
                    params={"fields": "countryCode"},
                    timeout=3,
                )
                if geo.ok and geo.json().get("countryCode") == "US":
                    paper_width_in = PAPER_WIDTH_LETTER
                    paper_size_used = "letter"
                else:
                    paper_width_in = PAPER_WIDTH_A4
                    paper_size_used = "a4"
            except http_requests.RequestException:
                paper_width_in = PAPER_WIDTH_LETTER
                paper_size_used = "letter"

        rf_url = f"https://detect.roboflow.com/{workspace}/workflows/{project}"
        try:
            rf_resp = http_requests.post(
                rf_url,
                json={
                    "api_key": api_key,
                    "inputs": {
                        "image": {"type": "base64", "value": b64_image}
                    },
                },
                timeout=30,
            )
            rf_resp.raise_for_status()
        except http_requests.RequestException as exc:
            return Response(
                {"detail": f"Roboflow request failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_json = rf_resp.json()

        all_preds = []
        for output in response_json.get("outputs", []):
            for val in output.values():
                if not isinstance(val, dict):
                    continue
                preds = val.get("predictions", [])
                # Workflows API sometimes wraps: {"predictions": [...], "image": {...}}
                if isinstance(preds, dict):
                    preds = preds.get("predictions", [])
                if isinstance(preds, list):
                    all_preds.extend(preds)

        paper = next((p for p in all_preds if p.get("class") == "paper"), None)
        if paper is None:
            label = PAPER_LABELS[paper_size_used]
            return Response(
                {"detail": f"No paper detected in image. Place foot on a sheet of {label} paper."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ppi = paper["width"] / paper_width_in

        foot = None
        for cls in ("foot", "insole"):
            candidates = [p for p in all_preds if p.get("class") == cls]
            if candidates:
                foot = max(candidates, key=lambda p: p.get("confidence", 0))
                break

        if foot is None:
            return Response(
                {"detail": "No foot or insole detected in image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        length_in = foot["height"] / ppi
        width_in = foot["width"] / ppi

        points = foot.get("points", [])
        if len(points) >= 3:
            coords = [(pt["x"], pt["y"]) for pt in points]
            n = len(coords)
            area_px = abs(
                sum(
                    coords[i][0] * coords[(i + 1) % n][1]
                    - coords[(i + 1) % n][0] * coords[i][1]
                    for i in range(n)
                )
            ) / 2
            area_sq_in = area_px / (ppi * ppi)
        else:
            area_sq_in = length_in * width_in * 0.70

        return Response({
            "length_in": round(length_in, 2),
            "width_in": round(width_in, 2),
            "area_sq_in": round(area_sq_in, 2),
            "ppi": round(ppi, 2),
            "paper_size": paper_size_used,
        })


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "shoe_count": Shoe.objects.count()})


class ShoeListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        shoes = Shoe.objects.prefetch_related("sizes").order_by("brand", "model")
        serializer = ShoeSerializer(shoes, many=True)
        return Response(serializer.data)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('id_token', '')
        if isinstance(token, str):
            token = token.strip()
        if not token:
            return Response(
                {'detail': 'id_token required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {'detail': 'Invalid ID token'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = idinfo.get('email')
        if not email:
            return Response(
                {'detail': 'No email in token'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': idinfo.get('given_name', ''),
                    'last_name': idinfo.get('family_name', ''),
                },
            )
            if created:
                Profile.objects.create(
                    user=user,
                    display_name=idinfo.get('name', ''),
                    avatar_url=idinfo.get('picture', ''),
                )

        user_token, _ = Token.objects.get_or_create(user=user)
        return Response({'key': user_token.key})
