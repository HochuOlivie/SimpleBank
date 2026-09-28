from rest_framework import serializers

from banking.models import Account


class AccountSerializer(serializers.ModelSerializer[Account]):
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = ("number", "balance", "currency")
        read_only_fields = fields
