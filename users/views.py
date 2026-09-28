from rest_framework import generics, permissions

from users.models import User
from users.serializers import RegistrationSerializer


class RegistrationView(generics.CreateAPIView[User]):
    """Register with email and password. Opens an account funded with the welcome bonus."""

    serializer_class = RegistrationSerializer
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
