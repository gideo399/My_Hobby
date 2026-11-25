from django.conf import settings
from django.db import models


class Photo(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="photos"
    )
    title = models.CharField(max_length=120)
    caption = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to="photos/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        # Remove the file from disk along with the database row
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
