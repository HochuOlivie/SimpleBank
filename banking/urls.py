from django.urls import path

from banking.views import AccountView, TransactionListView

urlpatterns = [
    path("account/", AccountView.as_view(), name="account"),
    path("account/transactions/", TransactionListView.as_view(), name="transactions"),
]
