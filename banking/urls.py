from django.urls import path

from banking.views import (
    AccountView,
    TransactionListView,
    TransferDetailView,
    TransferListCreateView,
)

urlpatterns = [
    path("account/", AccountView.as_view(), name="account"),
    path("account/transactions/", TransactionListView.as_view(), name="transactions"),
    path("transfers/", TransferListCreateView.as_view(), name="transfers"),
    path("transfers/<int:pk>/", TransferDetailView.as_view(), name="transfer-detail"),
]
