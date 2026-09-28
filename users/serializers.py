from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from banking.serializers import AccountSerializer
from users.models import User
from users.services import register_user

EMAIL_TAKEN = "A user with this email already exists."


class RegistrationSerializer(serializers.ModelSerializer[User]):
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}, trim_whitespace=False
    )
    account = AccountSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "password", "account")
        extra_kwargs = {  # noqa: RUF012
            "email": {
                "validators": [
                    UniqueValidator(User.objects.all(), message=EMAIL_TAKEN, lookup="iexact")
                ]
            }
        }

    def validate_email(self, email: str) -> str:
        return email.lower()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        try:
            validate_password(attrs["password"], User(email=attrs["email"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        email = validated_data["email"]
        try:
            return register_user(email, validated_data["password"])
        except IntegrityError as exc:
            # A concurrent request may have registered the same email after validation.
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": [EMAIL_TAKEN]}) from exc
            raise


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Log in with the email in any letter case, matching how it was registered."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        attrs[self.username_field] = attrs[self.username_field].lower()
        data: dict[str, str] = super().validate(attrs)
        return data
