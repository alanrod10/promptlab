import csv
import io
import json
from pathlib import Path
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from .models import Prompt
from .services import (
    calculate_rubric_score,
    get_gemini_response,
    analyze_live_preview,
    detect_and_mask_pii,
    normalize_and_lemmatize,
    parse_request,
    TECHNIQUE_BLOCKS,
)


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
            "id", "fecha_creacion", "engine_version", "categoria", "detected_action",
            "detected_deliverable", "nivel_mejora", "tecnica_aplicada",
            "puntaje_inicial", "information_gain", "puntaje_final", "ganancia_calidad_pts",
            "intent_confidence", "intent_margin", "n_intents", "n_entities",
            "n_neg_constraints", "n_slots_used", "info_density", "user_corrected",
            "has_pii_masked", "es_favorito", "palabras_entrada", "palabras_salida",
            "caracteres_entrada", "caracteres_salida", "factor_expansion",
            "bloques_estructura", "tiene_delimitadores", "texto_original", "prompt_mejorado",
        ]
        self.assertEqual(rows[0], expected_cols)
        self.assertEqual(rows[1][28], "1")  # tiene_delimitadores == 1

    def test_v4_analyze_live_and_overrides(self):
        live_payload = {
            "text": "Armame un script en Python 3.12 con Pandas sin usar librerías externas; mi mail es test@example.com",
            "technique": "Paso a Paso",
        }
        resp_live = self.client.post("/api/analyze-live/", data=json.dumps(live_payload), content_type="application/json")
        self.assertEqual(resp_live.status_code, 200)
        live_data = resp_live.json()
        self.assertEqual(live_data["engine_version"], "v4.0")
        self.assertIn("python", live_data["entities"])
        self.assertIn("pandas", live_data["entities"])
        self.assertTrue(live_data["has_pii"])
        self.assertGreaterEqual(len(live_data["neg_constraints"]), 1)
        self.assertEqual(Prompt.objects.count(), 0)

        improve_payload = {
            "text": "Armame un script en Python con Pandas; mi mail es test@example.com",
            "override_domain": "Ciencia de Datos e IA",
            "override_action": "analizar_datos",
            "override_deliverable": "código",
            "mask_pii": True,
            "user_example": "Entrada: ventas.csv -> Salida: resumen de nulos",
        }
        resp_imp = self.client.post("/api/improve/", data=json.dumps(improve_payload), content_type="application/json")
        self.assertEqual(resp_imp.status_code, 200)
        imp_data = resp_imp.json()
        self.assertTrue(imp_data["user_corrected"])
        self.assertTrue(imp_data["has_pii_masked"])
        self.assertIn("[EMAIL_OCULTO]", imp_data["raw_objective"])
        self.assertGreater(imp_data["information_gain"], 0)
        self.assertIn("segments", imp_data)
        self.assertIn("trace", imp_data)
        self.assertEqual(Prompt.objects.count(), 1)

    def test_voseo_clitic_normalization(self):
        norm, tokens, _ = normalize_and_lemmatize("Armame un plan y explicamelo fácil")
        self.assertIn("armar", tokens)
        self.assertIn("explicar", tokens)
        self.assertIn("armar", norm)

    def test_pii_detection_and_masking(self):
        masked, warnings = detect_and_mask_pii(
            "Mi CUIL es 20-34567890-9, email usuario@dominio.com y tel 11 4567-8901"
        )
        self.assertIn("[DNI_CUIL_OCULTO]", masked)
        self.assertIn("[EMAIL_OCULTO]", masked)
        self.assertIn("[TELEFONO_OCULTO]", masked)
        types = {w["type"] for w in warnings}
        self.assertIn("dni_cuil", types)
        self.assertIn("email", types)
        self.assertIn("telefono", types)

    def test_negative_constraints_and_contradictions(self):
        parsed = parse_request(
            "Dame un resumen breve pero exhaustivo sin tecnicismos ni ejemplos",
            technique="Con Ejemplos",
        )
        self.assertTrue(any("tecnicismos" in nc for nc in parsed.neg_constraints))
        self.assertGreaterEqual(len(parsed.contradictions), 1)

    def test_orthogonal_classification_and_multi_intent(self):
        res = analyze_live_preview(
            "Analizar este ventas.csv con Pandas; y además redactar un correo para gerencia"
        )
        self.assertEqual(res["domain"], "Ciencia de Datos e IA")
        self.assertEqual(res["action"], "analizar_datos")
        self.assertIn("redactar_contenido", res["secondary_actions"])
        self.assertEqual(res["deliverable"], "email / mensaje")
        self.assertGreater(res["confidence"], 0.0)
        self.assertGreaterEqual(res["margin"], 0.0)

    def test_non_circular_rubric_v2_scores(self):
        res_plain = get_gemini_response("explicar bases de datos sql")
        res_rich = get_gemini_response(
            "explicar normalización en sql sin tecnicismos",
            form_data={"edu_level": "Terciario / Universitario"},
            user_example="Tabla Clientes -> 3FN",
            override_domain="Estudio y academia",
        )
        self.assertGreater(res_rich["information_gain"], res_plain["information_gain"])
        self.assertGreaterEqual(res_rich["final_score"], res_plain["final_score"])

    def test_offline_templates_have_no_external_urls(self):
        templates_dir = Path(__file__).resolve().parent / "templates"
        for html_file in templates_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", content, f"URL externa encontrada en {html_file.name}")
            self.assertNotIn("https://", content, f"URL externa encontrada en {html_file.name}")
