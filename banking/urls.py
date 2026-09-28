from django.urls import path

from banking.views import AccountView, TransactionListView, TransferListCreateView

urlpatterns = [
    path("account/", AccountView.as_view(), name="account"),
    path("account/transactions/", TransactionListView.as_view(), name="transactions"),
    path("transfers/", TransferListCreateView.as_view(), name="transfers"),
]
