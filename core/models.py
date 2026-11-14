from django.db import models
from django.contrib.auth.models import User


class Prompt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prompts')
    original_text = models.TextField()
    improved_text = models.TextField()
    category = models.CharField(max_length=60, blank=True, null=True)
    detected_action = models.CharField(max_length=50, default='explicar_concepto')
    detected_deliverable = models.CharField(max_length=50, default='informe estructurado')
    improvement_level = models.CharField(max_length=20, default='Completa')
    technique = models.CharField(max_length=50, default='Estándar')
    engine_version = models.CharField(max_length=20, default='v4.0')

    # Métricas de Rúbrica v2 (no circular)
    initial_score = models.IntegerField(default=25)      # Puntaje de la idea cruda del usuario
    information_gain = models.IntegerField(default=0)    # Puntos aportados por el usuario (slots/restricciones/entidades)
    final_score = models.IntegerField(default=90)        # Puntaje estructural final
    quality_gain = models.IntegerField(default=65)       # Diferencia total

    # Telemetría NLP y Aprendizaje Activo
    intent_confidence = models.FloatField(default=0.85)
    intent_margin = models.FloatField(default=0.30)
    n_intents = models.IntegerField(default=1)
    n_entities = models.IntegerField(default=0)
    n_neg_constraints = models.IntegerField(default=0)
    n_slots_used = models.IntegerField(default=0)
    info_density = models.FloatField(default=0.0)
    user_corrected = models.BooleanField(default=False)
    has_pii_masked = models.BooleanField(default=False)

    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.engine_version}] {self.category or 'General'} - {self.original_text[:35]}..."
