from django.db import models
from django.contrib.auth.models import User

class UserConfig(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='config')
    theme_preference = models.CharField(max_length=10, default='auto')
    api_key = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Configuración de {self.user.username}"

class Prompt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prompts')
    original_text = models.TextField()
    improved_text = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    improvement_level = models.CharField(max_length=20)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prompt de {self.user.username} - {self.created_at.strftime('%d/%m/%Y')}"
