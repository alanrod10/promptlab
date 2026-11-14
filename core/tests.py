import csv
import io
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from .models import Prompt
from .services import calculate_rubric_score, get_gemini_response, TECHNIQUE_BLOCKS


class PromptLabServicesTests(TestCase):
    def test_trivial_input_scores_below_55(self):
        raw_eval = calculate_rubric_score("hola")
        self.assertLess(raw_eval["total"], 55)

        res = get_gemini_response("hola", "Otro / General", {}, "Completa", "Estándar")
        self.assertLess(res["final_score"], 55)

    def test_too_short_input_returns_error(self):
        res = get_gemini_response("ia", "Otro / General", {}, "Completa", "Estándar")
        self.assertIn("error", res)

    def test_rubric_sensitivity_with_and_without_audience(self):
        res_no_aud = get_gemini_response(
            "explicar regresion lineal y logistica en python con ejemplos practicos paso a paso",
            "Ninguna especificada",
            {},
            "Completa",
            "Paso a Paso",
        )
        self.assertEqual(res_no_aud["rubric_breakdown"]["Contexto y Público"], 14)
        self.assertGreaterEqual(res_no_aud["final_score"], 90)
        self.assertLess(res_no_aud["final_score"], 100)

        res_with_aud = get_gemini_response(
            "explicar regresion lineal y logistica en python con ejemplos practicos paso a paso",
            "Aprender y enseñar",
            {"Nivel Educativo": "Terciario / Universitario"},
            "Completa",
            "Paso a Paso",
        )
        self.assertEqual(res_with_aud["rubric_breakdown"]["Contexto y Público"], 20)
        self.assertEqual(res_with_aud["final_score"], 100)

    def test_all_levels_and_techniques(self):
        for level in ("Ligera", "Completa", "Profunda"):
            for tech in TECHNIQUE_BLOCKS:
                res = get_gemini_response(
                    "Analizar este csv con pandas para detectar valores nulos y graficar resultados",
                    "Investigar y analizar",
                    {"Formato de Salida": "Tabla comparativa o de datos"},
                    level,
                    tech,
                )
                self.assertIn("improved_prompt", res)
                self.assertIn("<datos_entrada>", res["improved_prompt"])
                self.assertEqual(res["technique"], tech)
                if level == "Ligera" and tech != "Estándar":
                    self.assertIn("Nota de técnica", res["improved_prompt"])


class PromptLabViewsAndIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="tester", password="123")

    def test_offline_static_vendor_assets_exist(self):
        required_assets = [
            "vendor/bootstrap/bootstrap.min.css",
            "vendor/bootstrap/bootstrap.bundle.min.js",
            "vendor/bootstrap-icons/bootstrap-icons.css",
            "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
            "vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
            "vendor/chartjs/chart.umd.min.js",
        ]
        for asset in required_assets:
            self.assertIsNotNone(finders.find(asset), f"Falta asset estático offline: {asset}")

    def test_get_routes_with_empty_db(self):
        for name in ("workspace", "history", "favorites", "templates_gallery", "analytics", "export_csv"):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 200, f"Falló ruta {name}")

    def test_workspace_load_and_preset(self):
        p = Prompt.objects.create(
            user=self.user,
            original_text="Explicar SQL desde cero",
            improved_text="# Rol\nActúa como docente.\n\n# Objetivo\nExplicar SQL desde cero para principiantes.",
            category="Aprender y enseñar",
            improvement_level="Completa",
            technique="Pedagógico",
            initial_score=30,
            final_score=95,
            quality_gain=65,
        )
        resp_load = self.client.get(reverse("workspace") + f"?load={p.id}")
        self.assertEqual(resp_load.status_code, 200)
        self.assertContains(resp_load, "Explicar SQL desde cero")
        self.assertContains(resp_load, "95/100")

        resp_preset = self.client.get(reverse("workspace") + "?preset=analisis-datos-pandas")
        self.assertEqual(resp_preset.status_code, 200)
        self.assertContains(resp_preset, "Analizar este dataset en Python con Pandas")

    def test_improve_api_valid_and_invalid_json(self):
        bad_json = self.client.post("/api/improve/", data="{invalid", content_type="application/json")
        self.assertEqual(bad_json.status_code, 400)

        non_dict = self.client.post("/api/improve/", data="[1, 2, 3]", content_type="application/json")
        self.assertEqual(non_dict.status_code, 400)

        payload = {
            "text": "explicar regresion lineal en python para principiantes",
            "level": "Completa",
            "technique": "Paso a Paso",
        }
        resp = self.client.post("/api/improve/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ("initial_score", "final_score", "quality_gain", "rubric_breakdown", "raw_objective"):
            self.assertIn(key, data)
        self.assertEqual(Prompt.objects.count(), 1)

    def test_toggle_favorite_and_delete_require_post_and_respect_next(self):
        p = Prompt.objects.create(
            user=self.user,
            original_text="Prueba favoritos",
            improved_text="Prompt mejorado\ncon salto de linea",
            category="General",
            is_favorite=True,
        )
        # GET debe ser rechazado con 405
        self.assertEqual(self.client.get(reverse("toggle_favorite", args=[p.id])).status_code, 405)
        self.assertEqual(self.client.get(reverse("delete_prompt", args=[p.id])).status_code, 405)

        # POST respetando next=favorites
        resp_fav = self.client.post(reverse("toggle_favorite", args=[p.id]), {"next": "favorites"})
        self.assertRedirects(resp_fav, reverse("favorites"))
        p.refresh_from_db()
        self.assertFalse(p.is_favorite)

        resp_del = self.client.post(reverse("delete_prompt", args=[p.id]), {"next": "favorites"})
        self.assertRedirects(resp_del, reverse("favorites"))
        self.assertEqual(Prompt.objects.count(), 0)

    def test_csv_export_structure_and_multiline_escaping(self):
        Prompt.objects.create(
            user=self.user,
            original_text="Analizar este csv con pandas",
            improved_text="# Rol\nAnalista\n\n# Datos\n<datos_entrada>\n[PEGA]\n</datos_entrada>",
            category="Investigar y analizar",
            improvement_level="Profunda",
            technique="Paso a Paso",
            initial_score=30,
            final_score=96,
            quality_gain=66,
            is_favorite=True,
        )
        resp = self.client.get(reverse("export_csv"))
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        expected_cols = [
            "id", "fecha_creacion", "categoria", "nivel_mejora", "tecnica_aplicada",
            "puntaje_inicial", "puntaje_final", "ganancia_calidad_pts", "es_favorito",
            "palabras_entrada", "palabras_salida", "caracteres_entrada", "caracteres_salida",
            "factor_expansion", "bloques_estructura", "tiene_delimitadores",
            "texto_original", "prompt_mejorado",
        ]
        self.assertEqual(rows[0], expected_cols)
        self.assertEqual(rows[1][15], "1")  # tiene_delimitadores == 1
