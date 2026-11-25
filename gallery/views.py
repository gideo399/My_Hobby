from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PhotoForm, SignUpForm
from .models import Photo


def signup(request):
    if request.user.is_authenticated:
        return redirect("gallery")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}. Your account is ready.")
            return redirect("gallery")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def gallery(request):
    scope = request.GET.get("show", "all")
    photos = Photo.objects.select_related("owner")
    if scope == "mine":
        photos = photos.filter(owner=request.user)
    return render(request, "gallery/gallery.html", {"photos": photos, "scope": scope})


@login_required
def upload(request):
    if request.method == "POST":
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.owner = request.user
            photo.save()
            messages.success(request, "Photo added to the gallery.")
            return redirect("gallery")
    else:
        form = PhotoForm()
    return render(request, "gallery/upload.html", {"form": form})


@login_required
@require_POST
def delete_photo(request, pk):
    photo = get_object_or_404(Photo, pk=pk, owner=request.user)
    photo.delete()
    messages.success(request, "Photo deleted.")
    return redirect("gallery")
