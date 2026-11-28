from django.db import models
from django.contrib.auth.models import User


class Prompt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prompts')
    original_text = models.TextField()
    improved_text = models.TextField()
    category = models.CharField(max_length=60, blank=True, null=True)
    detected_action = models.CharField(max_length=50, default='explicar_concepto')
    detected_deliverable = models.CharField(max_length=50, default='informe estructurado')
    subintent = models.CharField(max_length=50, default='general')
    improvement_level = models.CharField(max_length=20, default='Completa')
    technique = models.CharField(max_length=50, default='Estándar')
    engine_version = models.CharField(max_length=20, default='v7.2')

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
    noise_ratio = models.FloatField(default=0.04)
    anchor_coverage = models.FloatField(default=0.95)
    payload_kind = models.CharField(max_length=40, default='sin_insumo')
    roles_filled = models.FloatField(default=0.80)
    verifiable_ratio = models.FloatField(default=0.85)
    user_corrected = models.BooleanField(default=False)
    has_pii_masked = models.BooleanField(default=False)

    parent_prompt = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_versions',
    )
    root_prompt = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='version_family',
    )
    version_number = models.PositiveIntegerField(default=1)
    version_note = models.CharField(max_length=240, blank=True, default="")

    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.engine_version}] v{self.version_number} {self.category or 'General'} - {self.original_text[:35]}..."


class ActiveLearningRule(models.Model):
    term = models.CharField(max_length=100, unique=True)
    target_action = models.CharField(max_length=80)
    target_category = models.CharField(max_length=120, blank=True, default="")
    source_z_score = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at", "-id"]

    def __str__(self):
        state = "activa" if self.is_active else "inactiva"
        return f"{self.term} -> {self.target_action} ({state})"


class UserTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_templates')
    title = models.CharField(max_length=140)
    category = models.CharField(max_length=120, default="Otro / General")
    recommended_mode = models.CharField(max_length=20, default="guiado")
    prompt_body = models.TextField()
    why_it_works = models.CharField(max_length=280, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.title} ({self.recommended_mode})"
