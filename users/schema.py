from drf_spectacular.contrib.rest_framework_simplejwt import TokenObtainPairSerializerExtension


class EmailTokenObtainPairSerializerExtension(TokenObtainPairSerializerExtension):
    """Documents the login response ({access, refresh}) for our case-insensitive subclass."""

    target_class = "users.serializers.EmailTokenObtainPairSerializer"
