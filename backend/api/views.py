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
