from django.db import models
from django.contrib.auth.models import User

class Prompt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prompts')
    original_text = models.TextField()
    improved_text = models.TextField()
    category = models.CharField(max_length=50, blank=True, null=True)
    improvement_level = models.CharField(max_length=20, default='Completa')
    technique = models.CharField(max_length=50, default='Estándar')
    initial_score = models.IntegerField(default=25)
    final_score = models.IntegerField(default=90)
    quality_gain = models.IntegerField(default=65)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category or 'General'} - {self.original_text[:30]}..."
