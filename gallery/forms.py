from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Photo

MAX_UPLOAD_MB = 8


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    pass


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ("title", "caption", "image")

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"Image must be smaller than {MAX_UPLOAD_MB} MB.")
        return image
