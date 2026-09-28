from django.urls import path

from users.views import RegistrationView

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
]
