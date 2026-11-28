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
    rewrite_goal,
    check_fidelity,
    KNOWLEDGE_BASE,
    TECHNIQUE_BLOCKS,
)
from .universal_engine import (
    inspect_attached_payload,
    compute_control_values,
    mine_long_tail_candidates,
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
        self.client.force_login(self.user)

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
            "detected_deliverable", "subintent", "nivel_mejora", "tecnica_aplicada",
            "puntaje_inicial", "information_gain", "puntaje_final", "ganancia_calidad_pts",
            "intent_confidence", "intent_margin", "n_intents", "n_entities",
            "n_neg_constraints", "n_slots_used", "info_density", "noise_ratio",
            "anchor_coverage", "payload_kind", "roles_filled", "verifiable_ratio",
            "tiene_criterio_exito", "user_corrected",
            "has_pii_masked", "es_favorito", "palabras_entrada", "palabras_salida",
            "caracteres_entrada", "caracteres_salida", "factor_expansion",
            "bloques_estructura", "tiene_delimitadores", "texto_original", "prompt_mejorado",
        ]
        self.assertEqual(len(expected_cols), 38)
        self.assertEqual(rows[0], expected_cols)
        self.assertEqual(rows[1][35], "1")  # tiene_delimitadores == 1

    def test_v4_analyze_live_and_overrides(self):
        live_payload = {
            "text": "Armame un script en Python 3.12 con Pandas sin usar librerías externas; mi mail es test@example.com",
            "technique": "Paso a Paso",
        }
        resp_live = self.client.post("/api/analyze-live/", data=json.dumps(live_payload), content_type="application/json")
        self.assertEqual(resp_live.status_code, 200)
        live_data = resp_live.json()
        self.assertEqual(live_data["engine_version"], "v7.2")
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


class PromptLabV5EngineTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_gold_set_5_real_cases(self):
        # Caso 1: Ciencia de datos con restricción sin gráficos
        r1 = get_gemini_response(
            "analizame el archivo ventas.csv con pandas y decime si hay relación entre precio y cantidad vendida, sin gráficos",
            level="Completa",
        )
        self.assertIn("pandas.inspeccion", r1["directives_used"])
        self.assertIn("pandas.correlacion_regresion", r1["directives_used"])
        self.assertIn("pandas.outliers_iqr", r1["directives_used"])
        self.assertIn("neg.sin_graficos", r1["directives_used"])
        self.assertIn("# Criterio de éxito", r1["improved_prompt"])
        self.assertLess(r1["noise_ratio"], 0.10)

        # Caso 2: Debug KeyError
        r2 = get_gemini_response(
            "me da KeyError: 'precio' cuando corro df['precio'].mean(), no entiendo por qué",
            level="Completa",
        )
        self.assertIn("debug.keyerror", r2["directives_used"])
        self.assertIn("<datos_entrada>", r2["improved_prompt"])
        self.assertIn("df.columns", r2["improved_prompt"])
        self.assertLess(r2["noise_ratio"], 0.10)

        # Caso 3: Estudio principiante + parcial + comparación
        r3 = get_gemini_response(
            "explicame la diferencia entre mitosis y meiosis para el parcial del viernes, soy principiante",
            level="Completa",
        )
        self.assertIn("estudio.principiante", r3["directives_used"])
        self.assertIn("estudio.comparar", r3["directives_used"])
        self.assertIn("estudio.errores_comunes", r3["directives_used"])
        self.assertIn("estudio.parcial", r3["directives_used"])
        self.assertLess(r3["noise_ratio"], 0.10)

        # Caso 4: Negocio ventas + vencimientos
        r4 = get_gemini_response(
            "necesito saber como controlar las ventas y vencimientos de mi negocio",
            level="Completa",
        )
        self.assertIn("neg.ventas", r4["directives_used"])
        self.assertIn("neg.vencimientos", r4["directives_used"])
        self.assertIn("neg.cruce_ventas_vencimientos", r4["directives_used"])
        self.assertIn("neg.rutina", r4["directives_used"])
        self.assertIn("neg.herramienta", r4["directives_used"])
        self.assertLess(r4["noise_ratio"], 0.10)

        # Caso 5: Nota formal licencia por examen
        r5 = get_gemini_response(
            "necesito escribir una nota formal a mi empleador pidiendo licencia por examen el 3 y 4 de diciembre",
            level="Completa",
        )
        self.assertIn("red.nota_formal", r5["directives_used"])
        self.assertIn("tram.no_inventar", r5["directives_used"])
        self.assertIn("[COMPLETAR", r5["improved_prompt"])
        self.assertIn("# Criterio de éxito", r5["improved_prompt"])
        self.assertLess(r5["noise_ratio"], 0.10)

    def test_anti_filler_linter_and_noise_ratio(self):
        import re as _re
        r = get_gemini_response(
            "Necesito una respuesta clara y completa de python para analizar datos.csv teniendo en cuenta todos los aspectos",
            level="Completa",
        )
        for pat in KNOWLEDGE_BASE["lint_rules"]["banned_patterns"]:
            self.assertIsNone(_re.search(pat, r["improved_prompt"], flags=_re.IGNORECASE))
        self.assertLess(r["noise_ratio"], 0.10)
        self.assertGreaterEqual(r["anchor_coverage"], 0.90)

    def test_rewrite_fidelity_and_no_empty_blocks(self):
        parsed = parse_request("necesito saber como analizar ventas.csv con pandas")
        rewritten, _ = rewrite_goal(parsed)
        fid = check_fidelity(parsed.raw_text, rewritten, parsed)
        self.assertIn("ventas.csv", fid["goal"])
        self.assertIn("pandas", fid["goal"].lower())

        res = get_gemini_response("explicar que es una api rest", level="Completa")
        # Ninguna sección debe estar vacía (dos encabezados seguidos sin contenido)
        self.assertNotRegex(res["improved_prompt"], r"# [^\n]+\n\s*\n# ")

    def test_vague_input_suggested_paths(self):
        live = analyze_live_preview("ventas")
        self.assertTrue(live["is_vague"])
        self.assertEqual(len(live["suggested_paths"]), 3)

    def test_ux_simple_language_labels_in_views(self):
        ws = self.client.get(reverse("workspace"))
        self.assertEqual(ws.status_code, 200)
        self.assertContains(ws, "Prompt Listo para Usar")
        self.assertContains(ws, "De dónde sale cada frase")
        self.assertContains(ws, "Breve (Directo)")
        self.assertContains(ws, "Datos que faltan para mejorar tu resultado")

        an = self.client.get(reverse("analytics"))
        self.assertEqual(an.status_code, 200)
        self.assertContains(an, "Prompts Analizados")
        self.assertContains(an, "Precisión sin Relleno")
        self.assertContains(an, "Ver Fórmulas y Detalle Técnico para Evaluación Académica")


class PromptLabV6UniversalEngineTests(TestCase):
    def test_v6_gold_case1_transformar_payload_prices(self):
        raw = (
            "Tengo esta lista de precios en un WhatsApp, pasamela a JSON con campos nombre, precio, categoria:\n"
            "Coca 2.25lt $3200\n"
            "Galletitas Oreo 1450\n"
            "Yerba Playadito 1kg 6800\n"
            "Fideos Matarazzo 500g $1.900,50\n"
            "Aceite Natura 2100"
        )
        res = get_gemini_response(raw, level="Completa")
        self.assertEqual(res["engine_version"], "v7.2")
        self.assertEqual(res["detected_action"], "transformar_formato")
        self.assertEqual(res["detected_deliverable"], "json")
        self.assertEqual(res["payload_kind"], "lista_registros")
        self.assertEqual(res["payload_info"]["extracted_prices"], [3200, 1450, 6800, 1900.5, 2100])
        self.assertIn("<datos_entrada>", res["improved_prompt"])
        self.assertLess(res["noise_ratio"], 0.10)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90)

    def test_v6_gold_case2_auditar_clausula_inquilino(self):
        raw = "Revisame esta cláusula de alquiler como inquilino y decime qué riesgos tiene"
        res = get_gemini_response(raw, level="Completa")
        self.assertEqual(res["detected_action"], "auditar_criticar")
        self.assertEqual(res["roles"]["perspectiva"], "inquilino")
        self.assertIn("[PEGÁ ACÁ EL TEXTO DE LA CLÁUSULA]", res["improved_prompt"])
        self.assertLess(res["noise_ratio"], 0.10)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90)

    def test_v6_gold_case3_simular_cliente_whatsapp(self):
        raw = "Simula ser un cliente enojado por WhatsApp al que le llegó un producto vencido para practicar cómo responderle"
        res = get_gemini_response(raw, level="Completa")
        self.assertEqual(res["detected_action"], "simular_practicar")
        self.assertEqual(res["detected_deliverable"], "diálogo interactivo")
        self.assertEqual(res["roles"]["canal"].lower(), "whatsapp")
        self.assertIn("WhatsApp", res["improved_prompt"])
        self.assertLess(res["noise_ratio"], 0.10)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90)

    def test_v6_gold_case4_calcular_punto_equilibrio(self):
        raw = (
            "Tengo $1.200.000 de gastos fijos mensuales y vendo con margen promedio del 30%. "
            "Calculame cuánto tengo que vender por mes, por semana y por día para empatar y qué pasa si quiero ganar $360.000 netos."
        )
        res = get_gemini_response(raw, level="Completa")
        self.assertEqual(res["detected_action"], "calcular_modelar")
        self.assertTrue(res["has_calculation"])
        for marker in ("$4.000.000", "$5.200.000", "$166.667", "$153.846", "$133.333"):
            self.assertIn(marker, res["improved_prompt"])
        self.assertLess(res["noise_ratio"], 0.10)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90)

    def test_v6_gold_case5_idear_sin_humo_instagram(self):
        raw = (
            "Dame 5 ideas de contenido educativo para Instagram sobre inteligencia artificial "
            "aplicada a comercios chicos, sin humo ni promesas falsas"
        )
        res = get_gemini_response(raw, level="Completa")
        self.assertEqual(res["detected_action"], "idear_alternativas")
        self.assertEqual(res["detected_deliverable"], "lista")
        self.assertEqual(res["roles"]["canal"].lower(), "instagram")
        self.assertIn("inteligencia artificial aplicada a comercios chicos", res["roles"]["tema"].lower())
        self.assertIn("sin humo", res["improved_prompt"].lower())
        self.assertLess(res["noise_ratio"], 0.10)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90)

    def test_v6_inspector_calc_mining_and_38_csv_columns(self):
        payload_sample = (
            "Coca 2.25lt $3200\n"
            "Galletitas Oreo 1450\n"
            "Yerba Playadito 1kg 6800\n"
            "Fideos Matarazzo 500g $1.900,50\n"
            "Aceite Natura 2100"
        )
        insp = inspect_attached_payload(payload_sample, "pasamela a JSON")
        self.assertEqual(insp["payload_kind"], "lista_registros")
        self.assertEqual(insp["n_lineas"], 5)
        self.assertEqual(insp["extracted_prices"], [3200, 1450, 6800, 1900.5, 2100])
        self.assertIn("2.25lt", insp["extracted_units"])

        calc = compute_control_values("Tengo $1.200.000 de gastos fijos mensuales y margen del 30%")
        self.assertTrue(calc["has_calculation"])
        self.assertEqual(calc["ventas_sobre_venta_fmt"], "$4.000.000")
        self.assertEqual(calc["ventas_sobre_costo_fmt"], "$5.200.000")

        prompts_to_create = [
            "Revisame esta cláusula de alquiler como inquilino",
            "Revisame este contrato de franquicia en alquiler comercial",
            "Auditar esta cláusula penal en alquiler de local",
            "Simula ser un cliente enojado por WhatsApp",
        ]
        for txt in prompts_to_create:
            resp = self.client.post("/api/improve/", data=json.dumps({"text": txt}), content_type="application/json")
            self.assertEqual(resp.status_code, 200)

        candidates = mine_long_tail_candidates(Prompt.objects.all(), top_n=5)
        self.assertIsInstance(candidates, list)
        self.assertGreaterEqual(len(candidates), 1)
        self.assertIn("term", candidates[0])
        self.assertIn("z_score", candidates[0])

        an = self.client.get(reverse("analytics"))
        self.assertEqual(an.status_code, 200)
        self.assertContains(an, "Descubrimiento de Nuevos Temas (Bucle de Aprendizaje Offline)")
        self.assertContains(an, "38 columnas")

        csv_resp = self.client.get(reverse("export_csv"))
        self.assertEqual(csv_resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(csv_resp.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows[0]), 38)
        self.assertEqual(rows[0][22:25], ["payload_kind", "roles_filled", "verifiable_ratio"])


class PromptLabV7EngineAndWorkspaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="tester_v7", password="123")

    def test_clitic_normalizer_preserves_nouns_and_tech(self):
        norm, tokens, _ = normalize_and_lemmatize(
            "clausula sqlite dataframe cliente principiante"
        )
        for word in ("clausula", "sqlite", "dataframe", "cliente", "principiante"):
            self.assertIn(word, tokens)
            self.assertIn(word, norm)

        r_clause = parse_request("Revisame esta cláusula de alquiler como inquilino")
        self.assertEqual(r_clause.domain, "Trámites y documentos")

        r_sql = parse_request("Comparar SQLite vs PostgreSQL")
        self.assertIn("sqlite", r_sql.entities)

        r_aud = parse_request(
            "explicame la diferencia entre mitosis y meiosis para el parcial del viernes, soy principiante"
        )
        self.assertEqual(r_aud.audience, "Principiante / Sin conocimientos previos")

    def test_deliverable_word_boundaries_no_false_positives(self):
        r = parse_request(
            "Diagnosticar por qué bajaron las ventas y descartar causas secundarias de forma realista"
        )
        self.assertNotEqual(r.deliverable, "email / mensaje")
        self.assertNotEqual(r.deliverable, "lista")

    def test_confidence_calibration_on_clear_requests(self):
        clear_prompts = [
            "Armame un script en Python",
            "Pulir la redacción de este correo para un cliente",
            "explicame la diferencia entre mitosis y meiosis para el parcial del viernes, soy principiante",
        ]
        for txt in clear_prompts:
            res = analyze_live_preview(txt)
            self.assertGreaterEqual(
                res["confidence"],
                0.65,
                f"Confianza baja ({res['confidence']}) para pedido claro: {txt}",
            )

        vague = analyze_live_preview("ventas")
        self.assertLess(vague["confidence"], 0.50)

    def test_active_learning_sqlite_boost(self):
        from .services import _get_learned_correction_boosts, _score_actions_detailed, invalidate_learned_boosts_cache

        invalidate_learned_boosts_cache()
        sample = "Gestionar pliego de licitacion municipal con anexos tecnicos"
        norm_sample, toks_sample, _ = normalize_and_lemmatize(sample)

        base_scores, _ = _score_actions_detailed(sample, norm_sample, tokens=toks_sample)
        base_audit = base_scores["auditar_criticar"]

        # Dos correcciones persistidas en SQLite para el término "licitacion" / "pliego"
        Prompt.objects.create(
            user=self.user,
            original_text="Revisar pliego de licitacion obra publica",
            improved_text="# Rol\nAuditor",
            category="Trámites y documentos",
            detected_action="auditar_criticar",
            user_corrected=True,
        )
        Prompt.objects.create(
            user=self.user,
            original_text="Chequear pliego de licitacion proveedor",
            improved_text="# Rol\nAuditor",
            category="Trámites y documentos",
            detected_action="auditar_criticar",
            user_corrected=True,
        )
        invalidate_learned_boosts_cache()

        learned = _get_learned_correction_boosts(user=self.user)
        self.assertIn("licitacion", learned["actions"])
        self.assertIn("auditar_criticar", learned["actions"]["licitacion"])
        self.assertLessEqual(learned["actions"]["licitacion"]["auditar_criticar"], 0.12)

        boosted_req = parse_request(sample, active_user=self.user)
        self.assertEqual(boosted_req.domain, "Trámites y documentos")

        boosted_scores, _ = _score_actions_detailed(
            sample,
            norm_sample,
            tokens=toks_sample,
            learned_action_boosts={"auditar_criticar": learned["actions"]["licitacion"]["auditar_criticar"]},
        )
        self.assertGreater(boosted_scores["auditar_criticar"], base_audit)

    def test_improve_api_returns_prompt_id_and_disambiguation(self):
        resp = self.client.post(
            "/api/improve/",
            data=json.dumps({"text": "Analizar o resumir este texto", "level": "Completa"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prompt_id", data)
        self.assertIsInstance(data["prompt_id"], int)
        self.assertTrue(Prompt.objects.filter(id=data["prompt_id"]).exists())
        self.assertTrue(data["needs_disambiguation"])
        self.assertIn("disambiguation_options", data)
        self.assertGreaterEqual(len(data["disambiguation_options"]), 2)

        # Toggle favorito vía AJAX (fetch) desde Espacio de Trabajo
        fav_resp = self.client.post(
            reverse("toggle_favorite", args=[data["prompt_id"]]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(fav_resp.status_code, 200)
        fav_json = fav_resp.json()
        self.assertTrue(fav_json["is_favorite"])

    def test_workspace_v7_progressive_modes_and_static_js(self):
        js_path = Path(__file__).resolve().parent / "static" / "js" / "workspace.js"
        self.assertTrue(js_path.is_file(), "Falta archivo estático core/static/js/workspace.js")
        self.assertIsNotNone(finders.find("js/workspace.js"))

        ws = self.client.get(reverse("workspace"))
        self.assertEqual(ws.status_code, 200)
        self.assertContains(ws, "js/workspace.js")
        self.assertContains(ws, "Express")
        self.assertContains(ws, "Guiado")
        self.assertContains(ws, "Estudio Pro")
        self.assertContains(ws, "Prompt Listo para Usar")
        self.assertContains(ws, "De dónde sale cada frase")
        self.assertContains(ws, "Breve (Directo)")
        self.assertContains(ws, "Datos que faltan para mejorar tu resultado")

    def test_conceptual_datascience_from_scratch_regression(self):
        from .services import calculate_rubric_v2

        prompt_txt = "Quiero que me ayudes a entender la ciencia de datos desde cero"
        form_data = {
            "edu_level": "Autodidacta desde cero",
            "explain_depth": "Intuitiva desde cero",
            "Reglas Rápidas": "Agregar ejemplos reales, Explicar sin tecnicismos",
        }

        # Live preview con dominio Ciencia de Datos e IA no debe sugerir slots de dataset/modelo
        live = analyze_live_preview(prompt_txt, category="Ciencia de Datos e IA")
        slot_questions = " ".join(s["question"].lower() for s in live["suggested_slots"])
        self.assertNotIn("tamaño aproximado tiene tu dataset", slot_questions)
        self.assertEqual(live["topic_anchor"].lower(), "ciencia de datos")

        results_by_level = {}
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(
                prompt_txt,
                category="Ciencia de Datos e IA",
                form_data=form_data,
                level=level,
                technique="Estándar",
            )
            results_by_level[level] = res
            out = res["improved_prompt"]
            out_low = out.lower()

            # 1. Cero claves técnicas crudas ni "Reglas Rápidas:" literal
            for forbidden_key in ("edu_level", "explain_depth", "study_focus", "reglas rápidas:"):
                self.assertNotIn(forbidden_key, out_low, f"Clave cruda '{forbidden_key}' en nivel {level}")

            # 2. Cero slots/guardrails de dataset o data leakage en pedido conceptual
            for forbidden_ops in ("tamaño aproximado tiene tu dataset", "data leakage", "p-valores"):
                self.assertNotIn(forbidden_ops, out_low, f"Texto operativo '{forbidden_ops}' en nivel {level}")

            # 3. Sin autoevaluación no solicitada y sin 'exámenes' si no pidió examen
            self.assertNotIn("autoevaluación", out_low)
            self.assertNotIn("en exámenes", out_low)

            # 4. Anchor coverage >= 0.90 y noise_ratio < 0.10 en los 3 niveles
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en {level}")
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en {level}")

        # 5. En Ligera: no hay dos instrucciones seguidas pidiendo definición inicial duplicada
        ligera_lines = [ln.strip().lower() for ln in results_by_level["Ligera"]["improved_prompt"].splitlines() if ln.strip().startswith(("1.", "2.", "3.", "4."))]
        def_openers = [ln for ln in ligera_lines if "definición" in ln]
        self.assertLessEqual(len(def_openers), 1, f"Definición duplicada en Ligera: {ligera_lines}")

        # 6. En Completa: Reglas Rápidas operacionalizadas + etiquetas en español + 3-4 pasos progresivos
        completa_out = results_by_level["Completa"]["improved_prompt"]
        self.assertIn("Nivel educativo:", completa_out)
        self.assertIn("Nivel de profundidad:", completa_out)
        self.assertIn("2 ejemplos reales", completa_out)
        self.assertIn("# Restricciones", completa_out)

        # 7. En Profunda: cero líneas duplicadas entre # Validación previa a responder y # Criterio de éxito
        profunda_out = results_by_level["Profunda"]["improved_prompt"]
        self.assertIn("# Validación previa a responder", profunda_out)
        self.assertIn("# Criterio de éxito", profunda_out)
        val_block = profunda_out.split("# Validación previa a responder", 1)[1].split("# ", 1)[0]
        crit_block = profunda_out.split("# Criterio de éxito", 1)[1].split("# ", 1)[0]
        val_lines = {ln.lstrip("- ").replace("Verificar:", "").strip().lower() for ln in val_block.splitlines() if ln.strip().startswith("-")}
        crit_lines = {ln.lstrip("- ").strip().lower() for ln in crit_block.splitlines() if ln.strip().startswith("-")}
        self.assertTrue(val_lines, "Validación previa vacía")
        self.assertTrue(crit_lines, "Criterio de éxito vacío")
        self.assertEqual(val_lines & crit_lines, set(), f"Líneas duplicadas entre Validación y Criterio: {val_lines & crit_lines}")

        # 8. Detección de contradicción: Explicar sin tecnicismos + Técnica con ejemplos prácticos
        contra_live = analyze_live_preview(
            prompt_txt,
            form_data={
                "explain_depth": "Técnica con ejemplos prácticos",
                "Reglas Rápidas": "Explicar sin tecnicismos",
            },
        )
        self.assertGreaterEqual(len(contra_live["contradictions"]), 1)

        # 9. Consistencia rúbrica v2: si noise_ratio >= 0.10 nunca puede devolver 100/100
        parsed = parse_request(prompt_txt, form_data=form_data)
        penalized = calculate_rubric_v2(
            parsed=parsed,
            improved_prompt=profunda_out,
            form_data=form_data,
            level="Profunda",
            noise_ratio=0.18,
            anchor_coverage=0.82,
        )
        self.assertLess(penalized["final_score"], 100)

        # 10. Operacionalización de study_focus='Con ejercicios resueltos' + ficha de repaso al final en Profunda
        prof_ej = get_gemini_response(
            prompt_txt,
            form_data={
                **form_data,
                "study_focus": "Con ejercicios resueltos",
            },
            level="Profunda",
            technique="Estándar",
        )
        prof_ej_out = prof_ej["improved_prompt"]
        self.assertGreaterEqual(prof_ej["anchor_coverage"], 0.90)
        self.assertLess(prof_ej["noise_ratio"], 0.10)
        inst_block = prof_ej_out.split("# Instrucciones", 1)[1].split("# ", 1)[0]
        self.assertIn("ejercicios prácticos sobre ciencia de datos resueltos paso a paso", inst_block.lower())
        self.assertIn("en 60 segundos", inst_block.lower())
        idx_paso = inst_block.lower().index("desarrolla paso a paso")
        idx_ejemplos = inst_block.lower().index("2 ejemplos reales")
        idx_ficha = inst_block.lower().index("en 60 segundos")
        self.assertGreater(idx_ficha, idx_paso, "La ficha 'en 60 segundos' debe ir después del desarrollo paso a paso")
        self.assertGreater(idx_ficha, idx_ejemplos, "La ficha 'en 60 segundos' debe ir después de los ejemplos")
        numbered_steps = [ln.strip() for ln in inst_block.splitlines() if ln.strip() and ln.strip()[0].isdigit()]
        self.assertIn("en 60 segundos", numbered_steps[-1].lower(), "La ficha de repaso debe ser el último paso")

        # 11. Operacionalización de preguntas de examen/repaso (sin duplicar si técnica='Pedagógico')
        prof_preg = get_gemini_response(
            prompt_txt,
            form_data={"study_focus": "Con preguntas de examen"},
            level="Profunda",
            technique="Estándar",
        )
        self.assertIn("3 preguntas de autoevaluación o examen sobre ciencia de datos", prof_preg["improved_prompt"].lower())
        self.assertGreaterEqual(prof_preg["anchor_coverage"], 0.90)
        self.assertLess(prof_preg["noise_ratio"], 0.10)

        prof_ped = get_gemini_response(
            prompt_txt,
            form_data={"study_focus": "Con preguntas de examen"},
            level="Profunda",
            technique="Pedagógico",
        )
        self.assertNotIn("3 preguntas de autoevaluación o examen sobre ciencia de datos", prof_ped["improved_prompt"].lower())


class PromptLabV72RegressionTests(TestCase):
    """Suite dorada de regresión para PromptLab v7.2 (Express, Guiado y Estudio Pro)."""

    def _assert_studio_pro_invariants(self, res: dict, label: str = ""):
        out = res["improved_prompt"]
        self.assertEqual(res["engine_version"], "v7.2", label)

        # 1. 100% de viñetas bajo # Qué no hacer deben iniciar con negación clara
        if "# Qué no hacer" in out:
            qnh_block = out.split("# Qué no hacer", 1)[1].split("# ", 1)[0]
            bullets = [ln.strip()[2:].strip() for ln in qnh_block.splitlines() if ln.strip().startswith("- ")]
            self.assertTrue(bullets, f"# Qué no hacer vacío en {label}")
            for b in bullets:
                self.assertTrue(
                    b.startswith(("No ", "Evita ", "Nunca ", "Prohibido ")),
                    f"Ítem positivo en # Qué no hacer ({label}): {b}",
                )

        # 2. % Datos útiles idéntico en tarjeta y diagnóstico (fuente única de verdad)
        expected_pct = res["anchor_coverage_pct"]
        self.assertEqual(round(res["anchor_coverage"] * 100), expected_pct, label)
        self.assertIn(f"Datos útiles: {expected_pct}%", res["analysis"][1], label)
        self.assertIn("Motor v7.2", res["analysis"][0], label)

        # 3. Calidad sin relleno excesivo
        self.assertLess(res["noise_ratio"], 0.10, label)
        self.assertGreaterEqual(res["anchor_coverage"], 0.90, label)

    def test_01_json_custom_fields_and_presentation_split(self):
        raw = (
            "pasame esta lista a un json limpio con producto, presentacion y precio unitario:\n"
            "Coca Cola 2.25lt - $3.450\n"
            "Yerba Playadito 1kg $4.800\n"
            "Galletitas Toddy 180g - $1.650\n"
            "Agua Villavicencio 2lt $1.200"
        )
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertIn("producto", low)
            self.assertIn("presentacion", low)
            self.assertIn("precio", low)
            self.assertIn("4 objetos", low)
            self.assertIn("<datos_entrada>\nCoca Cola 2.25lt - $3.450", out)
            self.assertNotIn("precio unitario:.", out)
            self.assertNotIn("dentro del campo `nombre`", out)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 2 ({level})")

    def test_02_formal_claim_argentine_pii_python_and_js_sync(self):
        raw = (
            "redactame un reclamo formal a la empresa de internet por 4 dias sin servicio, "
            "mi nombre es Juan Perez DNI 33.456.789 tel 3885123456 y mail juanperez@gmail.com"
        )
        live = analyze_live_preview(raw)
        self.assertTrue(live["has_pii"])
        pii_types = {w["type"] for w in live["pii_warnings"]}
        self.assertEqual(pii_types, {"dni_cuil", "telefono", "email"})
        self.assertNotIn("sin servicio", [nc.lower() for nc in live["neg_constraints"]])

        # Verificar sincronía en frontend JS (workspace.js)
        js_path = Path(__file__).resolve().parent / "static" / "js" / "workspace.js"
        js_src = js_path.read_text(encoding="utf-8")
        self.assertIn("detectPiiClientSide", js_src)
        self.assertIn("[TELEFONO_OCULTO]", js_src)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level, mask_pii=True)
            out = res["improved_prompt"]
            self.assertIn("[DNI_CUIL_OCULTO]", out)
            self.assertIn("[TELEFONO_OCULTO]", out)
            self.assertIn("[EMAIL_OCULTO]", out)
            self.assertNotIn("3885123456", out)
            self.assertNotIn("Restricción del usuario:", out)
            if "# Restricciones" in out:
                restr_blk = out.split("# Restricciones", 1)[1].split("# ", 1)[0].lower()
                self.assertNotIn("sin servicio", restr_blk)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 3 ({level})")

    def test_03_debugging_python_traceback_preserves_indentation(self):
        raw = (
            "tengo este error en mi script de python y no se como arreglarlo:\n"
            "Traceback (most recent call last):\n"
            '  File "reporte.py", line 14, in <module>\n'
            '    total += fila["sucursal"]\n'
            "KeyError: 'sucursal'"
        )
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            self.assertIn("KeyError", out)
            self.assertIn("código corregido", out.lower())
            self.assertIn('  File "reporte.py", line 14, in <module>', out)
            self.assertIn('    total += fila["sucursal"]', out)
            self.assertNotIn("por sucursal: (involucrando:", out)
            self.assertNotIn("arreglarlo: (involucrando:", out)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 4 ({level})")

    def test_04_tech_comparison_sqlite_vs_postgresql_no_business_leak(self):
        raw = (
            "comparame SQLite vs PostgreSQL para un sistema de ventas de un negocio chico, "
            "decime ventajas, desventajas y cual me conviene"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["domain"], "Tecnología y programación")
        self.assertEqual(live["action"], "comparar_evaluar")
        slot_q = " ".join(s["question"].lower() for s in live["suggested_slots"])
        self.assertNotIn("cuántas opciones comparas", slot_q)
        self.assertNotIn("escala de negocio", slot_q)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["domain"], "Tecnología y programación")
            self.assertEqual(res["detected_action"], "comparar_evaluar")
            self.assertIn("recomendación", low)
            for forbidden in (
                "planilla simple",
                "semáforo",
                "join explícitos",
                "desglose de ventas",
                "ventas fiadas",
                "horarios pico",
            ):
                self.assertNotIn(forbidden, low, f"Contaminación '{forbidden}' en Prueba 6 ({level})")
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 6 ({level})")

    def test_05_interview_simulation_adaptive_no_anger_no_de_el(self):
        raw = (
            "simula una entrevista laboral para un puesto de analista de datos junior, "
            "haceme preguntas de a una y al final dame feedback de mis respuestas"
        )
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertIn("entrevista laboral", low)
            self.assertIn("`FIN`", out)
            self.assertIn("turno", low)
            self.assertNotIn("enojo", low)
            self.assertNotIn("de el canal", low)
            self.assertNotIn("el canal indicado", low)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 7 ({level})")

    def test_06_four_week_promo_plan_whatsapp_and_posters(self):
        raw = (
            "armame un plan de 4 semanas para lanzar una promocion de combos en mi negocio "
            "sin gastar en publicidad paga, tengo 1 hora por dia y solo uso whatsapp y carteles impresos"
        )
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["detected_action"], "planificar_pasos")
            self.assertIn("plan", res["detected_deliverable"].lower())
            self.assertIn("4 semanas", low)
            self.assertIn("1 hora", low)
            self.assertIn("carteles impresos", low)
            for forbidden in (
                "Asunto",
                "Correos demasiado largos",
                "email / mensaje",
                "planilla simple",
                "semáforo",
                "al abordar 4 semanas",
                "Tema principal: 4 semanas",
            ):
                self.assertNotIn(forbidden, out, f"Fuga '{forbidden}' en Prueba 9 ({level})")
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 9 ({level})")

    def test_07_meeting_minutes_extraction_table_lane_isolation(self):
        raw = (
            "extraeme en una tabla las tareas pendientes, el responsable y la fecha limite de esta minuta:\n"
            "Hoy revisamos el avance del local. Martin queda a cargo de actualizar la lista de precios "
            "del proveedor antes del viernes 15. Laura tiene que revisar el stock de bebidas y llamar "
            "al tecnico de la heladera (urgente, sin fecha definida). Yo me encargo de mandar el resumen por mail el lunes 18."
        )
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["detected_action"], "extraer_informacion")
            self.assertIn("tareas", low)
            self.assertIn("responsable", low)
            self.assertIn("fecha", low)
            self.assertIn("sin asignar", low)
            self.assertIn("sin inventar", low)
            for forbidden in (
                "(involucrando: proveedor, stock)",
                "tabla comparativa con al menos 5 criterios",
                "punto mínimo de reposición",
                "Define campos por venta",
            ):
                self.assertNotIn(forbidden, out, f"Contaminación '{forbidden}' en Prueba 10 ({level})")
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 10 ({level})")

    def test_08_python_script_no_external_libs_anti_contradiction(self):
        raw = (
            "escribime un script en python sin librerias externas que lea un csv de ventas "
            "y muestre el total vendido por categoria, comentado en español y que maneje el caso de archivo vacio"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["action"], "generar_codigo")
        self.assertFalse(live["needs_disambiguation"])
        self.assertGreaterEqual(live["confidence"], 0.85)
        self.assertEqual(live["neg_constraints"], ["sin librerias externas"])
        slot_q = " ".join(s["question"].lower() for s in live["suggested_slots"])
        self.assertNotIn("qué lenguaje", slot_q)
        self.assertNotIn("restricción técnica", slot_q)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["detected_action"], "generar_codigo")
            self.assertEqual(res["neg_constraints"], ["sin librerias externas"])
            self.assertIn("librería estándar", low)
            self.assertIn("vacío", low)
            self.assertIn("español", low)
            for forbidden in (
                "df.info()",
                "df.shape",
                "df.isna()",
                "Pandas",
                "NumPy",
                "SciPy",
                "Desglose de ventas",
                "Desglose de dataset",
            ):
                self.assertNotIn(forbidden, out, f"Contradicción '{forbidden}' en Prueba 11 ({level})")
            # Verificar que la restricción extraída en Restricciones / Qué no hacer se cortó en 'sin librerias externas'
            non_goal_lines = "\n".join(
                ln for ln in out.splitlines()
                if not ln.startswith("Objetivo:") and "Desarrollar un script" not in ln
            )
            self.assertNotIn("sin librerias externas que lea un csv", non_goal_lines)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 11 ({level})")

    def test_09_vague_sales_improvement_routes_to_diagnosis_or_plan(self):
        raw = "necesito mejorar las ventas de mi negocio porque este mes estuvo flojo"
        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            self.assertIn(res["detected_action"], ("diagnosticar_resolver", "planificar_pasos"))
            self.assertNotIn("Reescribe el texto", out)
            self.assertNotIn("versión pulida", out)
            self.assertNotIn("Asunto", out)
            if level == "Profunda":
                self._assert_studio_pro_invariants(res, f"Prueba 12 ({level})")

    def test_10_api_improve_persists_v72_and_consistent_metrics(self):
        client = Client()
        resp = client.post(
            "/api/improve/",
            data=json.dumps({
                "text": "escribime un script en python sin librerias externas que lea un csv de ventas y muestre el total vendido por categoria, comentado en español y que maneje el caso de archivo vacio",
                "level": "Profunda",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["engine_version"], "v7.2")
        self._assert_studio_pro_invariants(data, "API Profunda")
        saved = Prompt.objects.get(id=data["prompt_id"])
        self.assertEqual(saved.engine_version, "v7.2")


class PromptLabV721AuditRegressionTests(TestCase):
    """Suite de regresión v7.2.1 basada en auditoría real de casos N1–N6."""

    def test_n1_didactic_explanation_overfitting_vs_underfitting(self):
        raw = (
            "explicame la diferencia entre overfitting y underfitting en machine learning "
            "como si se lo contaras a alguien que recien empieza, usando una analogia de la vida cotidiana "
            "y sin usar formulas matematicas"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["domain"], "Ciencia de Datos e IA")
        self.assertEqual(live["action"], "explicar_concepto")
        self.assertEqual(live["subintent"], "comparacion")
        self.assertEqual(live["audience"], "Principiante / Sin conocimientos previos")
        self.assertEqual(live["neg_constraints"], ["sin usar formulas matematicas"])
        self.assertEqual(live["topic_anchor"].lower(), "overfitting y underfitting en machine learning")

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["detected_action"], "explicar_concepto")
            self.assertEqual(res["roles"]["perspectiva"], "")
            self.assertIn("analogía", low)
            self.assertIn("tabla comparativa", low)
            self.assertNotIn("ventajas, desventajas y limitaciones concretas de cada alternativa", low)
            self.assertNotIn("si se lo contaras a alguien", low.split("# contexto", 1)[1].split("# ", 1)[0] if "# contexto" in low else "")
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en N1 ({level})")
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en N1 ({level})")

    def test_n2_sql_query_no_false_client_audience_and_sql_smart_slots(self):
        raw = (
            "escribime una consulta SQL en PostgreSQL que una las tablas ventas, clientes y productos "
            "para mostrar el total facturado y la cantidad de compras por cliente en los ultimos 30 dias, "
            "ordenada de mayor a menor"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["domain"], "Tecnología y programación")
        self.assertEqual(live["action"], "generar_codigo")
        self.assertEqual(live["subintent"], "consulta_sql")
        self.assertEqual(live["audience"], "")
        slot_ids = [s["id"] for s in live["suggested_slots"]]
        self.assertNotIn("code_io", slot_ids)
        all_slot_options = [opt for s in live["suggested_slots"] for opt in s.get("options", [])]
        self.assertNotIn("Consulta base de datos", all_slot_options)
        self.assertNotIn("Solo librería estándar", all_slot_options)
        self.assertIn("SQL estándar ANSI", all_slot_options)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            self.assertEqual(res["detected_action"], "generar_codigo")
            self.assertNotIn("Directivo / Cliente", out)
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en N2 ({level})")
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en N2 ({level})")

    def test_n3_short_video_script_routes_to_redactar_and_cleans_hardcoded_template(self):
        kb_text = (Path(__file__).resolve().parent / "rules" / "knowledge_base.json").read_text(encoding="utf-8")
        ue_text = (Path(__file__).resolve().parent / "universal_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("Límite honesto", kb_text)
        self.assertNotIn("qué NO resuelve la herramienta", ue_text)
        self.assertNotIn("Límite honesto", ue_text)

        raw = (
            "armame un guion de 30 segundos para un video corto de TikTok o Reels promocionando "
            "un combo de desayuno en un local de barrio, con tono cercano y sin frases cliche de vendedor"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["domain"], "Redacción y comunicación")
        self.assertEqual(live["action"], "redactar_contenido")
        self.assertEqual(live["subintent"], "guion_video")
        self.assertEqual(live["tone"], "Cercano y claro")
        slot_ids = [s["id"] for s in live["suggested_slots"]]
        self.assertNotIn("comm_tone", slot_ids)
        slot_questions = " ".join(s["question"] for s in live["suggested_slots"])
        self.assertNotIn("¿Qué tono debe transmitir el mensaje?", slot_questions)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["detected_action"], "redactar_contenido")
            self.assertIn("0–3 s", out)
            self.assertIn("30 segundos", low)
            self.assertIn("[Video / Escena]", out)
            self.assertIn("[Audio / Locución]", out)
            self.assertIn("llamado a la acción", low)
            self.assertNotIn("límite honesto", low)
            self.assertNotIn("la herramienta", low)
            self.assertNotIn("Asunto", out)
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en N3 ({level})")
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en N3 ({level})")

    def test_n4_afip_invoice_no_false_dni_full_negative_constraint_and_no_express_dup(self):
        raw = (
            "redactame un mensaje cordial pero firme para pedirle a mi proveedor que me extienda 10 dias "
            "el plazo de pago de la factura 0004-00018291 por 480000 pesos, "
            "mi CUIL es 20-33456789-4 y mi cel 3884912345, sin sonar desesperado ni perder la buena relacion"
        )
        live = analyze_live_preview(raw)
        self.assertTrue(live["has_pii"])
        pii_map = {w["type"]: w["count"] for w in live["pii_warnings"]}
        self.assertEqual(pii_map, {"dni_cuil": 1, "telefono": 1})
        self.assertEqual(live["neg_constraints"], ["sin sonar desesperado ni perder la buena relacion"])

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level, mask_pii=True)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertIn("0004-00018291", out)
            self.assertIn("extienda 10 dias el plazo de pago", low)
            self.assertNotIn("reclamar el pago", low)
            self.assertIn("[DNI_CUIL_OCULTO]", out)
            self.assertIn("[TELEFONO_OCULTO]", out)
            self.assertNotIn("20-33456789-4", out)
            self.assertNotIn("3884912345", out)
            self.assertIn("sin sonar desesperado ni perder la buena relacion", low)
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en N4 ({level})")
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en N4 ({level})")

        # Express en redactar_contenido general sin duplicar instrucciones estructurales
        express_msg = get_gemini_response(
            "redactame un mensaje para confirmar una reunion mañana por la tarde",
            level="Ligera",
        )["improved_prompt"]
        self.assertFalse(
            "Incluye Asunto, saludo, cuerpo breve y cierre" in express_msg
            and "Estructura el mensaje con apertura clara" in express_msg
        )

        # Sincronía en frontend workspace.js para excluir facturas AFIP
        js_src = (Path(__file__).resolve().parent / "static" / "js" / "workspace.js").read_text(encoding="utf-8")
        self.assertIn('m.startsWith("000")', js_src)
        self.assertIn("factura|fc|comprobante", js_src)

    def test_n5_ui_singular_plural_labels_placeholder_button_and_cache_busting(self):
        one_line = inspect_attached_payload("Este es un texto adjunto de una sola línea", "resumime esto")
        self.assertEqual(one_line["summary_label"], "Texto adjunto (1 línea)")

        one_table = inspect_attached_payload("col1 | col2 | col3", "analiza esto")
        self.assertEqual(one_table["summary_label"], "Tabla (1 fila)")

        two_lines = inspect_attached_payload("Línea uno\nLínea dos", "resumime esto")
        self.assertEqual(two_lines["summary_label"], "Texto adjunto (2 líneas)")

        js_src = (Path(__file__).resolve().parent / "static" / "js" / "workspace.js").read_text(encoding="utf-8")
        fn_block = js_src.split("function hasPendingPlaceholders(text)", 1)[1].split("}", 1)[0]
        self.assertIn('"[COMPLETAR:"', fn_block)
        self.assertNotIn("<datos_entrada>", fn_block)

        ws = self.client.get(reverse("workspace"))
        self.assertEqual(ws.status_code, 200)
        self.assertContains(ws, 'promptlab.css?v=8.0"')
        self.assertContains(ws, 'workspace.js?v=8.0"')

    def test_n6_five_day_study_plan_clean_topic_daily_tasks_and_filtered_slots(self):
        raw = (
            "armame un plan de estudio de 5 dias para preparar un parcial de estadistica y probabilidad, "
            "tengo 2 horas cada noche despues de cursar y necesito priorizar ejercicios practicos y un simulacro el ultimo dia, "
            "sin trasnochar"
        )
        live = analyze_live_preview(raw)
        self.assertEqual(live["domain"], "Estudio y academia")
        self.assertEqual(live["action"], "planificar_pasos")
        self.assertEqual(live["subintent"], "estudio")
        self.assertEqual(live["topic_anchor"].lower(), "estadistica y probabilidad")
        self.assertNotIn("parcial", live["entities"])
        self.assertIn("estadistica", live["entities"])
        self.assertIn("probabilidad", live["entities"])
        slot_ids = [s["id"] for s in live["suggested_slots"]]
        self.assertNotIn("edu_level", slot_ids)
        self.assertNotIn("study_focus", slot_ids)

        for level in ("Ligera", "Completa", "Profunda"):
            res = get_gemini_response(raw, level=level)
            out = res["improved_prompt"]
            low = out.lower()
            self.assertEqual(res["roles"]["dedicacion"].lower(), "2 horas cada noche")
            self.assertEqual(res["roles"]["plazo"].lower(), "5 dias")
            self.assertIn("tareas diarias concretas", low)
            self.assertIn("organizado por días", low)
            self.assertIn("simulacro", low)
            self.assertNotIn("tareas semanales", low)
            self.assertNotIn("herramientas / conceptos:** parcial", low)
            self.assertNotIn("desglose de parcial", low)
            self.assertLess(res["noise_ratio"], 0.10, f"noise_ratio alto en N6 ({level})")
            self.assertGreaterEqual(res["anchor_coverage"], 0.90, f"anchor_coverage bajo en N6 ({level})")


class PromptLabTemplatesCatalogTests(TestCase):
    """Pruebas del catálogo multivariado de 18 plantillas y su conexión con el Espacio de Trabajo."""

    EXPECTED_CATEGORIES = {
        "Tecnología y Programación",
        "Ciencia de Datos e IA",
        "Negocios y Comercio",
        "Estudio y Academia",
        "Redacción y Comunicación",
        "Carrera y Productividad",
    }
    MODE_TO_LEVEL = {
        "express": "Ligera",
        "guiado": "Completa",
        "estudio_pro": "Profunda",
    }

    def setUp(self):
        self.client = Client()

    def test_templates_gallery_view_returns_200_and_didactic_ux(self):
        js_path = Path(__file__).resolve().parent / "static" / "js" / "templates_gallery.js"
        self.assertTrue(js_path.is_file(), "Falta archivo estático core/static/js/templates_gallery.js")
        self.assertIsNotNone(finders.find("js/templates_gallery.js"))

        resp = self.client.get(reverse("templates_gallery"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Plantillas Listas para Usar")
        self.assertContains(resp, "1. Elegí tu caso")
        self.assertContains(resp, "Usar esta plantilla")
        self.assertContains(resp, 'promptlab.css?v=8.0"')
        self.assertContains(resp, 'templates_gallery.js?v=8.0"')
        self.assertContains(resp, "Mostrando 18 de 18 plantillas")
        for cat in self.EXPECTED_CATEGORIES:
            self.assertContains(resp, cat)

        ws = self.client.get(reverse("workspace"))
        self.assertEqual(ws.status_code, 200)
        self.assertContains(ws, 'promptlab.css?v=8.0"')
        self.assertContains(ws, 'workspace.js?v=8.0"')

    def test_catalog_has_18_templates_across_6_categories_with_valid_fields(self):
        import re as _re
        from .views import TEMPLATES_CATALOG

        self.assertGreaterEqual(len(TEMPLATES_CATALOG), 18)
        self.assertEqual(len(TEMPLATES_CATALOG), 18)

        categories_count = {}
        for slug, tpl in TEMPLATES_CATALOG.items():
            self.assertEqual(tpl["slug"], slug)
            self.assertEqual(tpl["id"], slug)
            self.assertIn(tpl["categoria"], self.EXPECTED_CATEGORIES)
            categories_count[tpl["categoria"]] = categories_count.get(tpl["categoria"], 0) + 1
            self.assertTrue(tpl["titulo"].strip(), f"Falta título en {slug}")
            self.assertTrue(tpl["descripcion"].strip(), f"Falta descripción en {slug}")
            self.assertIn(tpl["modo"], ("express", "guiado", "estudio_pro"), f"Modo inválido en {slug}")
            self.assertTrue(tpl["por_que_funciona"].strip(), f"Falta por_que_funciona en {slug}")
            self.assertTrue(tpl["prompt"].strip(), f"Falta prompt en {slug}")
            self.assertIsNotNone(
                _re.search(r"\[[^\[\]\n]+\]", tpl["prompt"]),
                f"La plantilla {slug} debe incluir placeholders entre [corchetes]",
            )

        self.assertEqual(set(categories_count.keys()), self.EXPECTED_CATEGORIES)
        for cat, count in categories_count.items():
            self.assertEqual(count, 3, f"La categoría {cat} debería tener 3 plantillas")

    def test_all_18_templates_pass_engine_and_load_in_workspace(self):
        from .services import build_prompt
        from .views import TEMPLATES_CATALOG

        for slug, tpl in TEMPLATES_CATALOG.items():
            level = self.MODE_TO_LEVEL[tpl["modo"]]
            res = build_prompt(tpl["prompt"], level=level)
            self.assertNotIn("error", res, f"Error en motor para plantilla {slug}: {res.get('error')}")
            self.assertEqual(res["engine_version"], "v7.2")
            self.assertTrue(res["improved_prompt"].strip(), f"Salida vacía para {slug}")

            live = analyze_live_preview(tpl["prompt"])
            self.assertIn("domain", live)
            self.assertIn("action", live)

        # Verificar carga por ?preset=<slug> en Espacio de Trabajo para modos Express, Guiado y Estudio Pro
        sample_slugs = [
            ("explicar-concepto-analogia", 'data-mode="express"'),
            ("debug-corregir-codigo", 'data-mode="guiado"'),
            ("python-csv-sin-librerias", 'data-mode="pro"'),
        ]
        for slug, expected_attr in sample_slugs:
            ws_resp = self.client.get(reverse("workspace") + f"?preset={slug}")
            self.assertEqual(ws_resp.status_code, 200)
            self.assertContains(ws_resp, expected_attr)
            self.assertContains(ws_resp, TEMPLATES_CATALOG[slug]["prompt"].splitlines()[0])
            self.assertContains(ws_resp, "Plantilla cargada:")


class PromptLabStatsDashboardTests(TestCase):
    """Pruebas del dashboard claro de Estadísticas y Datos (v7.2.3)."""

    FORBIDDEN_JARGON = (
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "Ligera",
        "Completa",
        "Profunda",
        "delta",
    )

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="stats_tester", password="123")
        self.client.force_login(self.user)

    def test_stats_empty_state(self):
        resp = self.client.get(reverse("analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Todavía no hay estadísticas para mostrar")
        self.assertContains(resp, reverse("workspace"))
        self.assertContains(resp, reverse("templates_gallery"))
        self.assertContains(resp, 'promptlab.css?v=8.0"')
        for term in self.FORBIDDEN_JARGON:
            self.assertNotContains(resp, term)

    def test_stats_populated_dashboard_and_no_jargon(self):
        Prompt.objects.create(
            user=self.user,
            original_text="Explicar machine learning con analogía simple",
            improved_text="# Rol\nDocente\n# Objetivo\nExplicar machine learning.",
            category="Ciencia de Datos e IA",
            detected_action="explicar_concepto",
            improvement_level="Ligera",
            initial_score=40,
            final_score=86,
            quality_gain=46,
            anchor_coverage=0.95,
            noise_ratio=0.05,
            is_favorite=True,
            has_pii_masked=False,
        )
        Prompt.objects.create(
            user=self.user,
            original_text="Crear consulta SQL con JOIN para facturación",
            improved_text="# Rol\nDBA\n# Objetivo\nConsulta SQL en PostgreSQL.",
            category="Tecnología y Programación",
            detected_action="generar_codigo",
            improvement_level="Profunda",
            initial_score=55,
            final_score=95,
            quality_gain=40,
            anchor_coverage=0.96,
            noise_ratio=0.04,
            is_favorite=False,
            has_pii_masked=True,
        )
        # Registro legacy con final_score=0 para probar cálculo en memoria sin mutar BD
        Prompt.objects.create(
            user=self.user,
            original_text="Armar plan de control de stock semanal",
            improved_text="# Rol\nConsultor\n\n# Objetivo\nPlan de control de stock.\n\n# Formato de salida\n- Lista",
            category=None,
            detected_action="planificar_pasos",
            improvement_level="Completa",
            initial_score=35,
            final_score=0,
            quality_gain=0,
        )

        resp = self.client.get(reverse("analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tu resumen rápido")
        self.assertContains(resp, 'Comparativa "Antes vs. Después"')
        self.assertContains(resp, "Qué podés aprovechar mejor")
        self.assertContains(resp, "Últimos 5 prompts evaluados")
        self.assertContains(resp, "Express")
        self.assertContains(resp, "Guiado")
        self.assertContains(resp, "Estudio Pro")
        self.assertContains(resp, "Prompts Analizados")
        self.assertContains(resp, "Precisión sin Relleno")
        self.assertContains(resp, "con privacidad protegida")
        for term in self.FORBIDDEN_JARGON:
            self.assertNotContains(resp, term)

    def test_stats_period_filtering_real(self):
        from datetime import timedelta
        from django.utils import timezone

        old_p = Prompt.objects.create(
            user=self.user,
            original_text="Pedido antiguo de hace 45 días sobre finanzas",
            improved_text="# Rol\nAsesor\n# Objetivo\nFinanzas.",
            category="Negocios y Comercio",
            improvement_level="Completa",
            initial_score=40,
            final_score=84,
            quality_gain=44,
        )
        Prompt.objects.filter(id=old_p.id).update(created_at=timezone.now() - timedelta(days=45))

        Prompt.objects.create(
            user=self.user,
            original_text="Pedido reciente de hoy sobre Python CSV",
            improved_text="# Rol\nDev\n# Objetivo\nPython CSV.",
            category="Tecnología y Programación",
            improvement_level="Ligera",
            initial_score=50,
            final_score=92,
            quality_gain=42,
        )

        resp_7d = self.client.get(reverse("analytics") + "?periodo=7d")
        self.assertEqual(resp_7d.status_code, 200)
        self.assertContains(resp_7d, "Pedido reciente de hoy sobre Python CSV")
        self.assertNotContains(resp_7d, "Pedido antiguo de hace 45 días sobre finanzas")

        resp_30d = self.client.get(reverse("analytics") + "?periodo=30d")
        self.assertEqual(resp_30d.status_code, 200)
        self.assertContains(resp_30d, "Pedido reciente de hoy sobre Python CSV")
        self.assertNotContains(resp_30d, "Pedido antiguo de hace 45 días sobre finanzas")

        resp_all = self.client.get(reverse("analytics") + "?periodo=all")
        self.assertEqual(resp_all.status_code, 200)
        self.assertContains(resp_all, "Pedido reciente de hoy sobre Python CSV")
        self.assertContains(resp_all, "Pedido antiguo de hace 45 días sobre finanzas")

        resp_invalid = self.client.get(reverse("analytics") + "?periodo=invalido")
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertContains(resp_invalid, "Pedido reciente de hoy sobre Python CSV")
        self.assertContains(resp_invalid, "Pedido antiguo de hace 45 días sobre finanzas")

    def test_stats_empty_period_with_old_data(self):
        from datetime import timedelta
        from django.utils import timezone

        old_p = Prompt.objects.create(
            user=self.user,
            original_text="Prompt histórico de hace 45 días",
            improved_text="# Rol\nAsistente\n# Objetivo\nHistórico.",
            category="Estudio y Academia",
            improvement_level="Completa",
            initial_score=45,
            final_score=88,
            quality_gain=43,
        )
        Prompt.objects.filter(id=old_p.id).update(created_at=timezone.now() - timedelta(days=45))

        resp = self.client.get(reverse("analytics") + "?periodo=7d")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sin actividad en los últimos 7 días")
        self.assertContains(resp, "Ver todo el historial")
        for term in self.FORBIDDEN_JARGON:
            self.assertNotContains(resp, term)

    def test_stats_chart_json_payload_and_five_chart_containers(self):
        import re as _re

        js_path = Path(__file__).resolve().parent / "static" / "js" / "analytics_charts.js"
        self.assertTrue(js_path.is_file(), "Falta archivo estático core/static/js/analytics_charts.js")
        self.assertIsNotNone(finders.find("js/analytics_charts.js"))

        Prompt.objects.create(
            user=self.user,
            original_text="Armar script en Python para procesar ventas",
            improved_text="# Rol\nDev\n# Objetivo\nScript en Python.",
            category="Tecnología y Programación",
            detected_action="generar_codigo",
            improvement_level="Profunda",
            technique="Paso a Paso",
            initial_score=48,
            final_score=94,
            quality_gain=46,
        )
        Prompt.objects.create(
            user=self.user,
            original_text="Explicar qué es una red neuronal",
            improved_text="# Rol\nDocente\n# Objetivo\nExplicar red neuronal.",
            category="Ciencia de Datos e IA",
            detected_action="explicar_concepto",
            improvement_level="Ligera",
            technique="Estándar",
            initial_score=42,
            final_score=85,
            quality_gain=43,
        )
        Prompt.objects.create(
            user=self.user,
            original_text="Planificar estudio semanal de estadística",
            improved_text="# Rol\nTutor\n# Objetivo\nPlan de estudio.",
            category="Estudio y Academia",
            detected_action="planificar_pasos",
            improvement_level="Completa",
            technique="Con Ejemplos",
            initial_score=50,
            final_score=90,
            quality_gain=40,
        )

        resp = self.client.get(reverse("analytics"))
        self.assertEqual(resp.status_code, 200)
        html_body = resp.content.decode("utf-8")

        self.assertIn('id="analytics-chart-data"', html_body)
        self.assertIn('analytics_charts.js?v=8.0"', html_body)
        for container_id in (
            'id="chart-domains-svg"',
            'id="chart-donut-svg"',
            'id="chart-tech-grouped-svg"',
            'id="chart-task-grouped-svg"',
            'id="chart-evolution-svg"',
        ):
            self.assertIn(container_id, html_body)

        match = _re.search(
            r'<script id="analytics-chart-data" type="application/json">(.*?)</script>',
            html_body,
            flags=_re.DOTALL,
        )
        self.assertIsNotNone(match, "No se encontró el bloque JSON analytics-chart-data")
        payload = json.loads(match.group(1))
        for key in ("total", "domains", "donut", "evolution", "by_technique", "by_mode", "by_task", "quality_bands"):
            self.assertIn(key, payload)
        self.assertEqual(payload["total"], 3)

        task_labels = {item["label"] for item in payload["by_task"]}
        self.assertIn("Generar código", task_labels)
        self.assertIn("Explicar concepto", task_labels)
        self.assertIn("Planificar pasos", task_labels)
        style_labels = {item["label"] for item in payload["donut"]["styles"]}
        self.assertIn("Estándar", style_labels)

        for forbidden in self.FORBIDDEN_JARGON + ("user_score", "final_score"):
            self.assertNotIn(forbidden, html_body)

    def test_stats_single_prompt_edge_case(self):
        import re as _re

        Prompt.objects.create(
            user=self.user,
            original_text="Consulta SQL con JOIN para facturación mensual",
            improved_text="# Rol\nDBA\n# Objetivo\nConsulta SQL.",
            category="Tecnología y Programación",
            detected_action="generar_codigo",
            improvement_level="Completa",
            technique="Estándar",
            initial_score=52,
            final_score=91,
            quality_gain=39,
        )

        resp = self.client.get(reverse("analytics"))
        self.assertEqual(resp.status_code, 200)
        html_body = resp.content.decode("utf-8")
        self.assertNotIn("NaN", html_body)

        match = _re.search(
            r'<script id="analytics-chart-data" type="application/json">(.*?)</script>',
            html_body,
            flags=_re.DOTALL,
        )
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["donut"]["styles"]), 1)
        self.assertEqual(payload["donut"]["styles"][0]["pct"], 100)
        self.assertEqual(len(payload["evolution"]), 1)
        self.assertEqual(payload["evolution"][0]["before"], 52)
        self.assertEqual(payload["evolution"][0]["after"], 91)


class PromptLabSiteCoherenceTests(TestCase):
    """Pruebas de coherencia de diseño, lenguaje, cache-busting v7.2.4 y navegación entre las 4 pestañas."""

    EXTERNAL_CDNS = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
    )
    RAW_JARGON = (
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "user_score",
        "final_score",
    )
    RAW_MODE_WORDS = ("Ligera", "Completa", "Profunda")

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="coherence_user", password="123")
        self.client.force_login(self.user)

    def _create_sample_prompts(self):
        Prompt.objects.create(
            user=self.user,
            original_text="Armar script en Python para procesar CSV diario",
            improved_text="# Rol\nDev\n# Objetivo\nScript en Python.",
            category="Tecnología y Programación",
            detected_action="generar_codigo",
            improvement_level="Profunda",
            technique="Paso a Paso",
            initial_score=45,
            final_score=93,
            quality_gain=48,
            is_favorite=True,
            has_pii_masked=True,
        )
        Prompt.objects.create(
            user=self.user,
            original_text="Explicar qué es overfitting con analogía cotidiana",
            improved_text="# Rol\nDocente\n# Objetivo\nExplicar overfitting.",
            category="Ciencia de Datos e IA",
            detected_action="explicar_concepto",
            improvement_level="Ligera",
            technique="Estándar",
            initial_score=42,
            final_score=86,
            quality_gain=44,
            is_favorite=False,
        )

    def test_all_tabs_respond_200_empty_and_populated(self):
        routes = ("workspace", "templates_gallery", "history", "favorites", "analytics")
        for route_name in routes:
            resp = self.client.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200, f"Falló {route_name} con DB vacía")

        self._create_sample_prompts()
        for route_name in routes:
            resp = self.client.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200, f"Falló {route_name} con datos")

    def test_cache_busting_v724_and_no_external_cdns(self):
        self._create_sample_prompts()
        checks = [
            ("workspace", ["promptlab.css?v=8.0", "workspace.js?v=8.0"]),
            ("templates_gallery", ["promptlab.css?v=8.0", "templates_gallery.js?v=8.0"]),
            ("history", ["promptlab.css?v=8.0"]),
            ("favorites", ["promptlab.css?v=8.0"]),
            ("analytics", ["promptlab.css?v=8.0", "analytics_charts.js?v=8.0"]),
        ]
        for route_name, expected_assets in checks:
            resp = self.client.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode("utf-8")
            for asset in expected_assets:
                self.assertIn(asset, body, f"Falta {asset} en {route_name}")
            for cdn in self.EXTERNAL_CDNS:
                self.assertNotIn(cdn, body, f"CDN externo {cdn} detectado en {route_name}")

    def test_no_raw_jargon_or_internal_mode_names_in_ui(self):
        self._create_sample_prompts()
        for route_name in ("workspace", "templates_gallery", "history", "favorites", "analytics"):
            resp = self.client.get(reverse(route_name))
            body = resp.content.decode("utf-8")
            for term in self.RAW_JARGON:
                self.assertNotIn(term, body, f"Jerga cruda '{term}' encontrada en {route_name}")

        for route_name in ("templates_gallery", "history", "favorites", "analytics"):
            resp = self.client.get(reverse(route_name))
            body = resp.content.decode("utf-8")
            for raw_mode in self.RAW_MODE_WORDS:
                self.assertNotIn(raw_mode, body, f"Modo interno '{raw_mode}' expuesto en {route_name}")

        hist_body = self.client.get(reverse("history")).content.decode("utf-8")
        self.assertIn("Modo Express", hist_body)
        self.assertIn("Modo Estudio Pro", hist_body)
        self.assertIn("Privacidad protegida", hist_body)

    def test_navigation_coherence_titles_and_aria_current(self):
        expected = [
            ("workspace", "Espacio de Trabajo · PromptLab", reverse("workspace")),
            ("templates_gallery", "Plantillas · PromptLab", reverse("templates_gallery")),
            ("history", "Mi Historial · PromptLab", reverse("history")),
            ("favorites", "Favoritos · PromptLab", reverse("favorites")),
            ("analytics", "Estadísticas y Datos · PromptLab", reverse("analytics")),
        ]
        for route_name, expected_title, expected_href in expected:
            resp = self.client.get(expected_href)
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode("utf-8")
            self.assertIn(f"<title>{expected_title}</title>", body)
            self.assertIn('aria-current="page"', body)
            for nav_label in ("Espacio de Trabajo", "Mi Historial", "Favoritos", "Plantillas", "Estadísticas y Datos"):
                self.assertIn(nav_label, body)
            self.assertIn("Motor Híbrido v8.0 • 100% Offline", body)
            self.assertIn("themeChanged", body)


class PromptLabV73WorkspaceSmartFeaturesTests(TestCase):
    """Pruebas v7.3: ejemplos auto-ocultables, 4.º ejemplo social/PII, estimador multi-IA y sello de privacidad."""

    EXTERNAL_CDNS = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
    )
    FORBIDDEN_INTERNAL_TERMS = (
        "o200k_base",
        "SentencePiece",
        "tiktoken",
        "has_pii_masked",
        "pii_warnings",
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "user_score",
        "final_score",
    )
    SOCIAL_PRIVACY_PROMPT = (
        "Redactame una nota formal de seguimiento por una asistencia alimentaria para María Gómez, "
        "CUIL 27-34567890-4, cel 3884123456, mail maria.gomez@correo.com, "
        "adjuntando el comprobante AFIP 0004-00018291, en tono claro y respetuoso."
    )

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="tester_v73", password="123")
        self.client.force_login(self.user)

    def test_quick_examples_autohide_and_fourth_social_privacy_chip(self):
        resp_empty = self.client.get(reverse("workspace"))
        self.assertEqual(resp_empty.status_code, 200)
        body_empty = resp_empty.content.decode("utf-8")
        self.assertIn('id="express-examples"', body_empty)
        self.assertIn("pl-examples-collapse", body_empty)
        self.assertIn('aria-hidden="false"', body_empty)
        self.assertNotIn("pl-examples-collapse is-hidden", body_empty)
        self.assertIn("Proteger datos en nota oficial", body_empty)
        self.assertIn(self.SOCIAL_PRIVACY_PROMPT, body_empty)

        p = Prompt.objects.create(
            user=self.user,
            original_text="Nota de prueba cargada",
            improved_text="# Rol\nEspecialista\n# Objetivo\nNota de prueba.",
            category="Redacción y comunicación",
            improvement_level="Completa",
            technique="Estándar",
            initial_score=40,
            final_score=90,
            quality_gain=50,
            has_pii_masked=False,
        )
        resp_load = self.client.get(reverse("workspace") + f"?load={p.id}")
        self.assertEqual(resp_load.status_code, 200)
        body_load = resp_load.content.decode("utf-8")
        self.assertIn("pl-examples-collapse is-hidden", body_load)
        self.assertIn('aria-hidden="true"', body_load)

        resp_preset = self.client.get(reverse("workspace") + "?preset=python-csv-sin-librerias")
        self.assertEqual(resp_preset.status_code, 200)
        body_preset = resp_preset.content.decode("utf-8")
        self.assertIn("pl-examples-collapse is-hidden", body_preset)
        self.assertIn('aria-hidden="true"', body_preset)

    def test_fourth_example_live_pii_and_afip_preservation_end_to_end(self):
        resp_live = self.client.post(
            "/api/analyze-live/",
            data=json.dumps({"text": self.SOCIAL_PRIVACY_PROMPT}),
            content_type="application/json",
        )
        self.assertEqual(resp_live.status_code, 200)
        live_data = resp_live.json()
        self.assertEqual(live_data["engine_version"], "v7.2")
        self.assertTrue(live_data["has_pii"])
        live_types = {w["type"] for w in live_data["pii_warnings"]}
        self.assertEqual(live_types, {"dni_cuil", "telefono", "email"})

        resp_imp = self.client.post(
            "/api/improve/",
            data=json.dumps({
                "text": self.SOCIAL_PRIVACY_PROMPT,
                "level": "Ligera",
                "mask_pii": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_imp.status_code, 200)
        imp_data = resp_imp.json()
        self.assertEqual(imp_data["engine_version"], "v7.2")
        self.assertTrue(imp_data["has_pii_masked"])
        self.assertIn("[DNI_CUIL_OCULTO]", imp_data["improved_prompt"])
        self.assertIn("[TELEFONO_OCULTO]", imp_data["improved_prompt"])
        self.assertIn("[EMAIL_OCULTO]", imp_data["improved_prompt"])
        self.assertIn("0004-00018291", imp_data["improved_prompt"])

    def test_token_estimator_and_privacy_seal_in_workspace_no_cdns_or_jargon(self):
        resp = self.client.get(reverse("workspace"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")

        for expected in (
            'id="token-estimator-card"',
            "Consumo estimado al copiar a una IA",
            "ChatGPT",
            "Gemini",
            "Claude",
            "Estimación heurística orientativa para español; 100 % offline sin APIs.",
            'id="cmp-models-strip"',
            'id="privacy-verified-seal"',
            "Privacidad verificada antes de copiar a una IA externa",
            "Comprobante AFIP preservado sin falsos positivos.",
        ):
            self.assertIn(expected, body)

        self.assertIn('data-loaded-protected="false"', body)

        p_pii = Prompt.objects.create(
            user=self.user,
            original_text="Nota con CUIL [DNI_CUIL_OCULTO] y comprobante 0004-00018291",
            improved_text="# Objetivo\nNota para [DNI_CUIL_OCULTO] con comprobante AFIP 0004-00018291.",
            category="Redacción y comunicación",
            improvement_level="Ligera",
            technique="Estándar",
            initial_score=45,
            final_score=88,
            quality_gain=43,
            has_pii_masked=True,
        )
        resp_pii = self.client.get(reverse("workspace") + f"?load={p_pii.id}")
        self.assertEqual(resp_pii.status_code, 200)
        body_pii = resp_pii.content.decode("utf-8")
        self.assertIn('data-loaded-protected="true"', body_pii)

        clean_body = body.replace("http://www.w3.org/2000/svg", "")
        self.assertNotIn("http://", clean_body)
        self.assertNotIn("https://", clean_body)
        for cdn in self.EXTERNAL_CDNS:
            self.assertNotIn(cdn, body)
        for term in self.FORBIDDEN_INTERNAL_TERMS:
            self.assertNotIn(term, body)

    def test_static_workspace_js_has_token_estimator_and_privacy_seal_functions(self):
        js_path = Path(__file__).resolve().parent / "static" / "js" / "workspace.js"
        js_text = js_path.read_text(encoding="utf-8")
        for symbol in (
            "estimateTokensByModel",
            "syncQuickExamplesVisibility",
            "renderTokenEstimator",
            "renderPrivacyVerifiedSeal",
            "128000",
            "1000000",
            "200000",
            "[DNI_CUIL_OCULTO]",
            "[TELEFONO_OCULTO]",
            "[EMAIL_OCULTO]",
            "[CBU_OCULTO]",
            "[ALIAS_OCULTO]",
        ):
            self.assertIn(symbol, js_text)


class PromptLabV73OptionalAuthTests(TestCase):
    """Pruebas v7.3: registro simple opcional, login/logout y aislamiento estricto multiusuario."""

    EXTERNAL_CDNS = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
    )
    FORBIDDEN_JARGON = (
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "user_score",
        "final_score",
        "Ligera",
        "Completa",
        "Profunda",
    )

    def test_auth_pages_render_200_offline_and_standardized_titles(self):
        for route_name, expected_title, expected_link in (
            ("login", "<title>Ingresar · PromptLab</title>", "Creala gratis"),
            ("register", "<title>Crear cuenta · PromptLab</title>", "Ingresá"),
        ):
            resp = self.client.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode("utf-8")
            self.assertIn(expected_title, body)
            self.assertIn(expected_link, body)
            self.assertIn("Seguir sin cuenta", body)
            clean_body = body.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", clean_body)
            self.assertNotIn("https://", clean_body)
            for cdn in self.EXTERNAL_CDNS:
                self.assertNotIn(cdn, body)
            for term in self.FORBIDDEN_JARGON:
                self.assertNotIn(term, body)

    def test_register_validations_autologin_and_sidebar_username(self):
        # 1. Usuario demasiado corto
        r_short = self.client.post(
            reverse("register"),
            {"username": "ab", "password": "secret123", "password_confirm": "secret123"},
        )
        self.assertEqual(r_short.status_code, 200)
        self.assertContains(r_short, "al menos 3 caracteres")

        # 2. Caracteres inválidos
        r_bad_chars = self.client.post(
            reverse("register"),
            {"username": "juan perez!", "password": "secret123", "password_confirm": "secret123"},
        )
        self.assertEqual(r_bad_chars.status_code, 200)
        self.assertContains(r_bad_chars, "letras sin espacios")

        # 3. Contraseña corta
        r_short_pw = self.client.post(
            reverse("register"),
            {"username": "maria_gomez", "password": "123", "password_confirm": "123"},
        )
        self.assertEqual(r_short_pw.status_code, 200)
        self.assertContains(r_short_pw, "al menos 6 caracteres")

        # 4. Confirmación distinta
        r_mismatch = self.client.post(
            reverse("register"),
            {"username": "maria_gomez", "password": "secret123", "password_confirm": "otra1234"},
        )
        self.assertEqual(r_mismatch.status_code, 200)
        self.assertContains(r_mismatch, "no coinciden")

        # 5. Registro exitoso (con espacios extremos que se recortan)
        r_ok = self.client.post(
            reverse("register"),
            {"username": "  maria_gomez  ", "password": "secret123", "password_confirm": "secret123"},
        )
        self.assertRedirects(r_ok, reverse("workspace"))
        user = User.objects.get(username="maria_gomez")
        self.assertTrue(user.check_password("secret123"))

        ws = self.client.get(reverse("workspace"))
        self.assertContains(ws, "Sesión activa")
        self.assertContains(ws, "@maria_gomez")

        # 6. Usuario ya autenticado redirige al Espacio de Trabajo si entra a /registro/ o /ingresar/
        self.assertRedirects(self.client.get(reverse("register")), reverse("workspace"))
        self.assertRedirects(self.client.get(reverse("login")), reverse("workspace"))

        # 7. Duplicado insensible a mayúsculas rechazado para otro cliente
        other = Client()
        r_dup = other.post(
            reverse("register"),
            {"username": "Maria_Gomez", "password": "secret123", "password_confirm": "secret123"},
        )
        self.assertEqual(r_dup.status_code, 200)
        self.assertContains(r_dup, "ya está en uso")

    def test_logout_post_only_and_login_flow(self):
        User.objects.create_user(username="carlos_dev", password="clave_segura")

        # GET /salir/ debe ser rechazado con 405
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

        # Credenciales incorrectas
        r_bad = self.client.post(
            reverse("login"),
            {"username": "carlos_dev", "password": "incorrecta"},
        )
        self.assertEqual(r_bad.status_code, 200)
        self.assertContains(r_bad, "no son correctos")

        # Login exitoso respetando next interno seguro
        r_ok = self.client.post(
            reverse("login"),
            {"username": "carlos_dev", "password": "clave_segura", "next": reverse("history")},
        )
        self.assertRedirects(r_ok, reverse("history"))

        # Logout por POST vuelve a Modo invitado
        r_out = self.client.post(reverse("logout"))
        self.assertRedirects(r_out, reverse("workspace"))
        ws_guest = self.client.get(reverse("workspace"))
        self.assertContains(ws_guest, "Modo invitado")
        self.assertNotContains(ws_guest, "@carlos_dev")

        # next externo es ignorado y redirige a /
        r_ext = self.client.post(
            reverse("login"),
            {"username": "carlos_dev", "password": "clave_segura", "next": "https://evil.example/steal"},
        )
        self.assertRedirects(r_ext, reverse("workspace"))

    def test_strict_user_isolation_across_all_views_and_csv(self):
        client_a = Client()
        client_b = Client()
        guest_client = Client()

        # Registrar Usuario A y generar un prompt único
        reg_a = client_a.post(
            reverse("register"),
            {"username": "usuario_a", "password": "password_a", "password_confirm": "password_a"},
        )
        self.assertRedirects(reg_a, reverse("workspace"))
        secret_text_a = "Analizar inventario secreto alfa de usuario_a con Python y Pandas"
        resp_imp_a = client_a.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": secret_text_a, "level": "Completa"}),
            content_type="application/json",
        )
        self.assertEqual(resp_imp_a.status_code, 200)
        prompt_a_id = resp_imp_a.json()["prompt_id"]

        # Usuario A lo ve en historial, analítica y CSV
        self.assertContains(client_a.get(reverse("history")), secret_text_a)
        self.assertContains(client_a.get(reverse("analytics")), secret_text_a)
        self.assertIn(secret_text_a, client_a.get(reverse("export_csv")).content.decode("utf-8-sig"))

        # Modo invitado NO ve el prompt de Usuario A
        self.assertNotContains(guest_client.get(reverse("history")), secret_text_a)
        self.assertNotContains(guest_client.get(reverse("analytics")), secret_text_a)
        self.assertNotIn(secret_text_a, guest_client.get(reverse("export_csv")).content.decode("utf-8-sig"))

        # Registrar Usuario B
        reg_b = client_b.post(
            reverse("register"),
            {"username": "usuario_b", "password": "password_b", "password_confirm": "password_b"},
        )
        self.assertRedirects(reg_b, reverse("workspace"))

        # Usuario B NO ve el prompt de A en historial, favoritos, analítica ni CSV
        self.assertNotContains(client_b.get(reverse("history")), secret_text_a)
        self.assertNotContains(client_b.get(reverse("favorites")), secret_text_a)
        self.assertNotContains(client_b.get(reverse("analytics")), secret_text_a)
        self.assertNotIn(secret_text_a, client_b.get(reverse("export_csv")).content.decode("utf-8-sig"))

        # Usuario B no puede cargar ?load=<id_de_A> ni mutar favorito/eliminar (404)
        resp_load_b = client_b.get(reverse("workspace") + f"?load={prompt_a_id}")
        self.assertEqual(resp_load_b.status_code, 200)
        self.assertNotContains(resp_load_b, secret_text_a)

        self.assertEqual(client_b.post(reverse("toggle_favorite", args=[prompt_a_id])).status_code, 404)
        self.assertEqual(client_b.post(reverse("delete_prompt", args=[prompt_a_id])).status_code, 404)
        self.assertTrue(Prompt.objects.filter(id=prompt_a_id).exists())

    def test_guest_mode_remains_fully_operational_without_account(self):
        guest = Client()
        for name in ("workspace", "templates_gallery", "history", "favorites", "analytics", "export_csv"):
            resp = guest.get(reverse(name))
            self.assertEqual(resp.status_code, 200)

        live = guest.post(
            reverse("analyze_live_api"),
            data=json.dumps({"text": "Explicar qué es una base de datos relacional"}),
            content_type="application/json",
        )
        self.assertEqual(live.status_code, 200)

        imp = guest.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Explicar qué es una base de datos relacional", "level": "Ligera"}),
            content_type="application/json",
        )
        self.assertEqual(imp.status_code, 200)
        pid = imp.json()["prompt_id"]

        self.assertContains(guest.get(reverse("history")), "base de datos relacional")
        self.assertEqual(guest.post(reverse("toggle_favorite", args=[pid]), {"next": "favorites"}).status_code, 302)
        self.assertContains(guest.get(reverse("favorites")), "base de datos relacional")
        self.assertEqual(guest.post(reverse("delete_prompt", args=[pid]), {"next": "history"}).status_code, 302)
        self.assertFalse(Prompt.objects.filter(id=pid).exists())


class PromptLabV80ScientificAndActiveLearningTests(TestCase):
    """Pruebas Fase 1 v8.0: Dataset dorado, benchmark 5-Fold Python puro, comando CLI y capa Overlay."""

    EXTERNAL_CDNS = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
    )
    FORBIDDEN_JARGON = (
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "user_score",
        "final_score",
        "Ligera",
        "Completa",
        "Profunda",
        "delta",
        "NaN",
    )

    def setUp(self):
        from .scientific_eval import invalidate_scientific_cache
        from .services import invalidate_learned_boosts_cache

        invalidate_scientific_cache()
        invalidate_learned_boosts_cache()
        self.client = Client()
        self.user = User.objects.create_user(username="tester_v80", password="123", is_staff=True)
        self.client.force_login(self.user)

    def test_benchmark_dataset_validity_and_stratification(self):
        from collections import Counter
        from .scientific_eval import BENCHMARK_DATASET_PATH, load_benchmark_dataset

        self.assertTrue(BENCHMARK_DATASET_PATH.is_file(), "Falta core/rules/benchmark_dataset.json")
        cases = load_benchmark_dataset()
        self.assertGreaterEqual(len(cases), 60)

        valid_actions = set(KNOWLEDGE_BASE.get("actions", {}).keys())
        valid_domains = set(KNOWLEDGE_BASE.get("domains", {}).keys())
        required_fields = {"id", "text", "expected_action", "expected_category", "difficulty", "notes"}

        seen_ids = set()
        action_counts = Counter()
        difficulties = Counter()

        for case in cases:
            self.assertEqual(set(case.keys()), required_fields)
            self.assertNotIn(case["id"], seen_ids)
            seen_ids.add(case["id"])
            self.assertTrue(case["text"].strip())
            self.assertIn(case["expected_action"], valid_actions)
            self.assertIn(case["expected_category"], valid_domains)
            self.assertIn(case["difficulty"], ("normal", "borde"))
            self.assertTrue(case["notes"].strip())
            action_counts[case["expected_action"]] += 1
            difficulties[case["difficulty"]] += 1

        self.assertGreaterEqual(difficulties["normal"], 30)
        self.assertGreaterEqual(difficulties["borde"], 10)
        for act, cnt in action_counts.items():
            self.assertGreaterEqual(cnt, 5, f"La clase {act} debe tener al menos 5 casos para 5-Fold estratificado")

    def test_scientific_benchmark_5fold_no_leakage_and_hybrid_gain(self):
        from .models import ActiveLearningRule
        from .scientific_eval import build_stratified_folds, load_benchmark_dataset, run_scientific_benchmark
        from .services import invalidate_learned_boosts_cache

        cases = load_benchmark_dataset()
        folds = build_stratified_folds(cases, n_splits=5, seed=42)
        self.assertEqual([len(f) for f in folds], [12, 12, 12, 12, 12])

        report = run_scientific_benchmark(force_refresh=True)
        self.assertEqual(report["dataset_size"], 60)
        self.assertEqual(report["n_folds"], 5)
        self.assertTrue(report["nb_out_of_fold"])
        self.assertFalse(report["rules_held_out"])
        self.assertLess(report["max_intra_class_jaccard"], 0.35)
        self.assertEqual(report["coverage_actions"], "10/21")
        self.assertEqual(report["production_nb_classes"], 21)

        for lane in ("baseline", "hybrid"):
            metrics = report[lane]
            for metric_name in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"):
                self.assertGreaterEqual(metrics[metric_name], 0.0)
                self.assertLessEqual(metrics[metric_name], 1.0)
            self.assertLessEqual(metrics["accuracy_ci_low_pct"], metrics["accuracy_pct"])
            self.assertGreaterEqual(metrics["accuracy_ci_high_pct"], metrics["accuracy_pct"])

        rep = report["repeated_cv"]
        self.assertEqual(rep["n_repeats"], 10)
        self.assertEqual(rep["n_splits"], 5)
        self.assertGreaterEqual(rep["accuracy_mean_pct"], rep["accuracy_min_pct"])
        self.assertLessEqual(rep["accuracy_mean_pct"], rep["accuracy_max_pct"])
        self.assertGreater(report["mcnemar_p_value"], 0.0)
        self.assertLessEqual(report["mcnemar_p_value"], 1.0)
        self.assertEqual(len(report["case_audit"]), 60)

        cm = report["confusion_matrix"]
        matrix_total = sum(sum(row) for row in cm["matrix"])
        self.assertEqual(matrix_total, report["dataset_size"])
        self.assertEqual(cm["total"], report["dataset_size"])
        self.assertEqual(sum(r["support"] for r in report["per_class"]), report["dataset_size"])
        self.assertLess(report["elapsed_ms"], 2000.0)
        self.assertEqual(report["regressions_count"], 0)
        self.assertGreaterEqual(report["hybrid"]["macro_f1"], report["baseline"]["macro_f1"])
        self.assertGreaterEqual(report["improved_count"], 1)

        # Invariancia total frente a SQLite: Prompts corregidos y ActiveLearningRule NO alteran el benchmark
        for idx in range(3):
            Prompt.objects.create(
                user=self.user,
                original_text="Automatizar archivos pdf en carpeta",
                improved_text="# Objetivo\nScript.",
                category="Tecnología y programación",
                detected_action="auditar_criticar",
                user_corrected=True,
            )
        ActiveLearningRule.objects.create(
            term="balanza",
            target_action="depurar_error",
            source_z_score=2.5,
            is_active=True,
            created_by=self.user,
        )
        invalidate_learned_boosts_cache()
        report_with_db_noise = run_scientific_benchmark(force_refresh=True)
        self.assertEqual(report_with_db_noise["baseline"]["accuracy"], report["baseline"]["accuracy"])
        self.assertEqual(report_with_db_noise["hybrid"]["accuracy"], report["hybrid"]["accuracy"])
        self.assertEqual(report_with_db_noise["hybrid"]["macro_f1"], report["hybrid"]["macro_f1"])

    def test_evaluate_engine_management_command(self):
        from django.core.management import call_command

        out = io.StringIO()
        call_command("evaluate_engine", stdout=out)
        output = out.getvalue()
        self.assertIn("Baseline v7.2", output)
        self.assertIn("Híbrido v8.0", output)
        self.assertIn("IC 95 % Wilson", output)
        self.assertIn("CV Repetida 10x5", output)
        self.assertIn("McNemar", output)
        self.assertIn("Macro F1", output)
        self.assertIn("Weighted F1", output)
        self.assertIn("Aciertos en diagonal", output)

    def test_learned_correction_boosts_strict_per_user_and_guest_isolation(self):
        from .services import _get_learned_correction_boosts, invalidate_learned_boosts_cache
        from .views import GUEST_SENTINEL_USERNAME

        invalidate_learned_boosts_cache()
        user_a = User.objects.create_user(username="boost_user_a", password="secret123")
        user_b = User.objects.create_user(username="boost_user_b", password="secret123")
        guest = User(username=GUEST_SENTINEL_USERNAME)
        guest.set_unusable_password()
        guest.save()

        sample = "Gestionar pliego municipal con anexos tecnicos"
        for i in range(3):
            Prompt.objects.create(
                user=user_a,
                original_text=f"Revisar pliego municipal lote {i}",
                improved_text="# Rol\nAuditor",
                category="Trámites y documentos",
                detected_action="auditar_criticar",
                user_corrected=True,
            )

        boosts_a = _get_learned_correction_boosts(user=user_a)
        self.assertIn("pliego", boosts_a["actions"])
        self.assertIn("auditar_criticar", boosts_a["actions"]["pliego"])

        # Usuario B, None e invitado_demo jamás reciben boosts de Usuario A
        self.assertEqual(_get_learned_correction_boosts(user=user_b), {"actions": {}, "domains": {}})
        self.assertEqual(_get_learned_correction_boosts(user=None), {"actions": {}, "domains": {}})
        self.assertEqual(_get_learned_correction_boosts(user=guest), {"actions": {}, "domains": {}})

        req_b = parse_request(sample, active_user=user_b, enable_overlay=False)
        self.assertFalse(any(tr.get("stage") == "active_learning" for tr in req_b.trace))

    def test_active_learning_overlay_approve_trace_and_toggle_without_mutating_kb(self):
        from .models import ActiveLearningRule

        kb_path = Path(__file__).resolve().parent / "rules" / "knowledge_base.json"
        kb_before = kb_path.read_bytes()

        sample_text = "Procesar el relevamiento barrial de cuadrillas en los sectores sur"
        base_parsed = parse_request(sample_text, enable_hybrid=False)
        self.assertNotEqual(base_parsed.action, "analizar_datos")

        approve_resp = self.client.post(
            reverse("approve_learning_rule"),
            {
                "term": "relevamiento barrial",
                "target_action": "analizar_datos",
                "source_z_score": "1.85",
            },
        )
        self.assertEqual(approve_resp.status_code, 302)
        self.assertTrue(approve_resp["Location"].endswith("#bloque-aprendizaje"))

        rule = ActiveLearningRule.objects.get(term="relevamiento barrial")
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.target_action, "analizar_datos")

        boosted_parsed = parse_request(sample_text)
        self.assertEqual(boosted_parsed.action, "analizar_datos")
        expected_trace = "Capa Active Learning v8.0: término 'relevamiento barrial' → acción 'analizar_datos'"
        self.assertTrue(any(tr.get("rule") == expected_trace for tr in boosted_parsed.trace))

        gen_res = get_gemini_response(sample_text, level="Completa")
        self.assertEqual(gen_res["detected_action"], "analizar_datos")
        self.assertIn(expected_trace, gen_res["analysis"])

        # Verificar que knowledge_base.json nunca se modificó
        self.assertEqual(kb_path.read_bytes(), kb_before)

        # Desactivar la regla vía POST y verificar reversión 100 % limpia
        toggle_resp = self.client.post(reverse("toggle_learning_rule", args=[rule.id]))
        self.assertEqual(toggle_resp.status_code, 302)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

        reverted_parsed = parse_request(sample_text, enable_hybrid=False)
        self.assertNotEqual(reverted_parsed.action, "analizar_datos")
        self.assertFalse(any(tr.get("stage") == "active_learning_overlay" for tr in reverted_parsed.trace))

    def test_analytics_renders_scientific_evaluation_and_overlay_cleanly(self):
        from .models import ActiveLearningRule

        # 1. Vista con BD vacía
        resp_empty = self.client.get(reverse("analytics"))
        self.assertEqual(resp_empty.status_code, 200)
        body_empty = resp_empty.content.decode("utf-8")
        self.assertIn("Evaluación Científica del Motor NLP (Benchmark 5-Fold Offline)", body_empty)
        self.assertIn("CV repetida 10×5", body_empty)
        self.assertIn("IC 95 % (Wilson)", body_empty)
        self.assertIn("McNemar exacto", body_empty)
        self.assertIn("Alcance y límites declarados", body_empty)
        self.assertIn("Ver Matriz de Confusión y Métricas por Clase", body_empty)
        self.assertIn("Auditar casos del benchmark", body_empty)
        self.assertIn("60 casos curados", body_empty)

        # 2. Vista poblada con prompts repetidos para generar candidatos Log-Odds + regla activa
        for i in range(3):
            Prompt.objects.create(
                user=self.user,
                original_text=f"Revisar relevamiento vecinal urgente lote {i}",
                improved_text="# Rol\nAnalista\n# Objetivo\nRevisar relevamiento vecinal.",
                category="Planificación y productividad",
                detected_action="analizar_datos",
                improvement_level="Completa",
                initial_score=40,
                final_score=90,
                quality_gain=50,
                intent_confidence=0.40,
                n_entities=0,
            )
        ActiveLearningRule.objects.create(
            term="acta municipal",
            target_action="auditar_criticar",
            source_z_score=1.55,
            is_active=True,
            created_by=self.user,
        )

        resp_pop = self.client.get(reverse("analytics"))
        self.assertEqual(resp_pop.status_code, 200)
        body_pop = resp_pop.content.decode("utf-8")
        self.assertIn("Evaluación Científica del Motor NLP (Benchmark 5-Fold Offline)", body_pop)
        self.assertIn("Ver Matriz de Confusión y Métricas por Clase", body_pop)
        self.assertIn("Aprobar en capa", body_pop)
        self.assertIn("Reglas aprobadas por supervisión humana (Capa Overlay)", body_pop)
        self.assertIn("acta municipal", body_pop)
        self.assertIn("Desactivar", body_pop)

        clean_body = body_pop.replace("http://www.w3.org/2000/svg", "")
        self.assertNotIn("http://", clean_body)
        self.assertNotIn("https://", clean_body)
        for cdn in self.EXTERNAL_CDNS:
            self.assertNotIn(cdn, body_pop)
        for term in self.FORBIDDEN_JARGON:
            self.assertNotIn(term, body_pop, f"Jerga cruda '{term}' encontrada en /analitica/")


class PromptLabV80VersioningAndCollectionsTests(TestCase):
    """Pruebas Fase 2 v8.0: Versionado v1->v2->v3, Mis Plantillas Propias y Portabilidad .JSON."""

    EXTERNAL_CDNS = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
    )
    FORBIDDEN_JARGON = (
        "anchor_coverage",
        "noise_ratio",
        "subintent",
        "user_score",
        "final_score",
        "delta",
        "NaN",
    )
    FORBIDDEN_MODES = ("Ligera", "Completa", "Profunda")

    def setUp(self):
        self.client = Client()

    def _register_and_login(self, username: str, password: str = "secret123") -> Client:
        cli = Client()
        resp = cli.post(
            reverse("register"),
            {"username": username, "password": password, "password_confirm": password},
        )
        self.assertEqual(resp.status_code, 302)
        return cli

    def test_iterative_versioning_v1_v2_v3_and_history_evolution(self):
        cli = self._register_and_login("iter_user")

        r1 = cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Explicar regresión logística en python", "level": "Ligera"}),
            content_type="application/json",
        )
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertEqual(d1["version_number"], 1)
        self.assertEqual(d1["root_prompt_id"], d1["prompt_id"])
        self.assertIsNone(d1["parent_prompt_id"])

        r2 = cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({
                "text": "Explicar regresión logística en python con ejemplos cotidianos",
                "level": "Completa",
                "parent_prompt_id": d1["prompt_id"],
                "version_note": "Pasé a modo Guiado con ejemplos cotidianos",
            }),
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertEqual(d2["version_number"], 2)
        self.assertEqual(d2["root_prompt_id"], d1["prompt_id"])
        self.assertEqual(d2["parent_prompt_id"], d1["prompt_id"])
        self.assertEqual(d2["version_note"], "Pasé a modo Guiado con ejemplos cotidianos")

        r3 = cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({
                "text": "Explicar regresión logística en python para principiantes sin fórmulas",
                "level": "Profunda",
                "parent_prompt_id": d2["prompt_id"],
                "version_note": "Agregué casos borde y restricción sin fórmulas",
            }),
            content_type="application/json",
        )
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertEqual(d3["version_number"], 3)
        self.assertEqual(d3["root_prompt_id"], d1["prompt_id"])
        self.assertEqual(d3["parent_prompt_id"], d2["prompt_id"])

        p1 = Prompt.objects.get(id=d1["prompt_id"])
        p2 = Prompt.objects.get(id=d2["prompt_id"])
        p3 = Prompt.objects.get(id=d3["prompt_id"])
        self.assertIsNone(p1.root_prompt)
        self.assertEqual(p2.root_prompt_id, p1.id)
        self.assertEqual(p3.root_prompt_id, p1.id)

        hist_resp = cli.get(reverse("history"))
        self.assertEqual(hist_resp.status_code, 200)
        hist_body = hist_resp.content.decode("utf-8")
        self.assertIn("Ver evolución (3 versiones)", hist_body)
        self.assertIn("v1", hist_body)
        self.assertIn("v2", hist_body)
        self.assertIn("v3", hist_body)
        self.assertIn("Pasé a modo Guiado con ejemplos cotidianos", hist_body)
        self.assertIn("Agregué casos borde y restricción sin fórmulas", hist_body)

        ws_iter = cli.get(reverse("workspace") + f"?load={p2.id}&iterate=1")
        self.assertEqual(ws_iter.status_code, 200)
        self.assertContains(ws_iter, "Iterar nueva versión")
        self.assertContains(ws_iter, "Guardar como plantilla")

    def test_versioning_strict_user_isolation(self):
        cli_a = self._register_and_login("ver_owner_a")
        cli_b = self._register_and_login("ver_other_b")

        res_a = cli_a.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Armar script en Python para facturación", "level": "Completa"}),
            content_type="application/json",
        )
        self.assertEqual(res_a.status_code, 200)
        prompt_a_id = res_a.json()["prompt_id"]

        res_b = cli_b.post(
            reverse("improve_prompt_api"),
            data=json.dumps({
                "text": "Intento de iterar prompt ajeno",
                "level": "Completa",
                "parent_prompt_id": prompt_a_id,
                "version_note": "Nota intrusa",
            }),
            content_type="application/json",
        )
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        self.assertEqual(data_b["version_number"], 1)
        self.assertIsNone(data_b["parent_prompt_id"])
        self.assertEqual(data_b["root_prompt_id"], data_b["prompt_id"])
        self.assertEqual(data_b["version_note"], "")

        saved_b = Prompt.objects.get(id=data_b["prompt_id"])
        self.assertIsNone(saved_b.parent_prompt)
        self.assertIsNone(saved_b.root_prompt)

    def test_custom_user_templates_crud_isolation_and_curated_intact(self):
        from .models import UserTemplate

        cli_a = self._register_and_login("tpl_user_a")
        cli_b = self._register_and_login("tpl_user_b")

        create_resp = cli_a.post(
            reverse("create_user_template"),
            {
                "title": "Planilla semanal de reparto",
                "category": "Negocios y comercio",
                "recommended_mode": "pro",
                "prompt_body": "Armame una hoja de reparto para [zona] con [cantidad] pedidos.",
                "why_it_works": "Ordena horarios y zonas sin omitir entregas.",
            },
        )
        self.assertEqual(create_resp.status_code, 302)
        ut = UserTemplate.objects.get(title="Planilla semanal de reparto")
        self.assertEqual(ut.recommended_mode, "pro")

        # En /plantillas/ de A aparece su plantilla y las 18 curadas quedan intactas
        gal_a = cli_a.get(reverse("templates_gallery"))
        self.assertEqual(gal_a.status_code, 200)
        self.assertContains(gal_a, "Mis Plantillas guardadas (1)")
        self.assertContains(gal_a, "Planilla semanal de reparto")
        self.assertContains(gal_a, "Mostrando 18 de 18 plantillas")

        # Usuario B no ve la plantilla de A y recibe 404 al intentar borrarla
        gal_b = cli_b.get(reverse("templates_gallery"))
        self.assertEqual(gal_b.status_code, 200)
        self.assertContains(gal_b, "Mis Plantillas guardadas (0)")
        self.assertNotContains(gal_b, "Planilla semanal de reparto")

        self.assertEqual(cli_b.post(reverse("delete_user_template", args=[ut.id])).status_code, 404)
        self.assertTrue(UserTemplate.objects.filter(id=ut.id).exists())

        # Carga en workspace con ?user_tpl=<id> aislada por usuario
        ws_a = cli_a.get(reverse("workspace") + f"?user_tpl={ut.id}")
        self.assertEqual(ws_a.status_code, 200)
        self.assertContains(ws_a, "Armame una hoja de reparto para [zona]")

        ws_b = cli_b.get(reverse("workspace") + f"?user_tpl={ut.id}")
        self.assertEqual(ws_b.status_code, 200)
        self.assertNotContains(ws_b, "Armame una hoja de reparto para [zona]")

        # GET a eliminar debe devolver 405; POST de A elimina correctamente
        self.assertEqual(cli_a.get(reverse("delete_user_template", args=[ut.id])).status_code, 405)
        del_a = cli_a.post(reverse("delete_user_template", args=[ut.id]))
        self.assertEqual(del_a.status_code, 302)
        self.assertFalse(UserTemplate.objects.filter(id=ut.id).exists())

    def test_json_collection_export_import_dedup_validation_and_afip_safe_pii(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import UserTemplate

        cli_a = self._register_and_login("export_user_a")
        cli_b = self._register_and_login("import_user_b")

        cli_a.post(
            reverse("create_user_template"),
            data=json.dumps({
                "title": "Nota social con resguardo",
                "category": "Trámites y documentos",
                "recommended_mode": "guiado",
                "prompt_body": (
                    "Redactar nota para Ana Ruiz CUIL 27-34567890-4 cel 3884123456 "
                    "mail ana@ejemplo.com por comprobante AFIP 0004-00018291 en [organismo]."
                ),
                "why_it_works": "Estructura formal verificable.",
            }),
            content_type="application/json",
        )

        exp_resp = cli_a.get(reverse("export_user_templates_json"))
        self.assertEqual(exp_resp.status_code, 200)
        exported = json.loads(exp_resp.content.decode("utf-8"))
        self.assertEqual(exported["schema_version"], "promptlab-collection-v1")
        self.assertEqual(exported["count"], 1)
        self.assertEqual(len(exported["templates"]), 1)

        # Importar en Usuario B -> anonimiza PII argentino y preserva AFIP 0004-00018291
        upload_1 = SimpleUploadedFile(
            "coleccion.json",
            exp_resp.content,
            content_type="application/json",
        )
        imp_1 = cli_b.post(reverse("import_user_templates_json"), {"collection_file": upload_1})
        self.assertEqual(imp_1.status_code, 302)

        user_b = User.objects.get(username="import_user_b")
        imported_tpls = list(UserTemplate.objects.filter(user=user_b))
        self.assertEqual(len(imported_tpls), 1)
        body_b = imported_tpls[0].prompt_body
        self.assertIn("[DNI_CUIL_OCULTO]", body_b)
        self.assertIn("[TELEFONO_OCULTO]", body_b)
        self.assertIn("[EMAIL_OCULTO]", body_b)
        self.assertIn("0004-00018291", body_b)
        self.assertNotIn("27-34567890-4", body_b)
        self.assertNotIn("3884123456", body_b)
        self.assertNotIn("ana@ejemplo.com", body_b)

        # Re-importar el mismo archivo no debe duplicar
        upload_2 = SimpleUploadedFile(
            "coleccion.json",
            exp_resp.content,
            content_type="application/json",
        )
        imp_2 = cli_b.post(reverse("import_user_templates_json"), {"collection_file": upload_2})
        self.assertEqual(imp_2.status_code, 302)
        self.assertEqual(UserTemplate.objects.filter(user=user_b).count(), 1)

        # JSON malformado y schema inválido devuelven 400 con mensaje claro
        bad_json_file = SimpleUploadedFile("bad.json", b"{invalid json", content_type="application/json")
        bad_resp = cli_b.post(reverse("import_user_templates_json"), {"collection_file": bad_json_file})
        self.assertEqual(bad_resp.status_code, 400)
        self.assertContains(bad_resp, "malformado", status_code=400)

        bad_schema_file = SimpleUploadedFile(
            "bad_schema.json",
            json.dumps({"schema_version": "desconocida", "templates": []}).encode("utf-8"),
            content_type="application/json",
        )
        bad_schema_resp = cli_b.post(reverse("import_user_templates_json"), {"collection_file": bad_schema_file})
        self.assertEqual(bad_schema_resp.status_code, 400)
        self.assertContains(bad_schema_resp, "Esquema inválido", status_code=400)

    def test_no_cdns_or_forbidden_jargon_across_updated_views(self):
        cli = self._register_and_login("coherence_v80_p2")
        r1 = cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Explicar SQL JOIN para principiantes", "level": "Ligera"}),
            content_type="application/json",
        ).json()
        cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({
                "text": "Explicar SQL JOIN para principiantes con ejemplos",
                "level": "Completa",
                "parent_prompt_id": r1["prompt_id"],
                "version_note": "Sumé ejemplos de tablas",
            }),
            content_type="application/json",
        )
        cli.post(
            reverse("create_user_template"),
            {
                "title": "Plantilla limpia sin jerga",
                "category": "Estudio y academia",
                "recommended_mode": "express",
                "prompt_body": "Explicame [tema] con un ejemplo simple.",
                "why_it_works": "Directa y clara.",
            },
        )

        for route_name in ("workspace", "history", "favorites", "templates_gallery", "analytics"):
            resp = cli.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode("utf-8")
            clean_body = body.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", clean_body)
            self.assertNotIn("https://", clean_body)
            for cdn in self.EXTERNAL_CDNS:
                self.assertNotIn(cdn, body)
            for term in self.FORBIDDEN_JARGON:
                self.assertNotIn(term, body, f"Jerga cruda '{term}' encontrada en {route_name}")
            if route_name != "workspace":
                for mode_w in self.FORBIDDEN_MODES:
                    self.assertNotIn(mode_w, body, f"Modo interno '{mode_w}' encontrado en {route_name}")


class PromptLabV801SecurityAndAuditFixesTests(TestCase):
    """Pruebas de blindaje v8.0.1 (Pasada 1): autorización Overlay, invitado seguro, CSRF, PII y demo fixes."""

    def setUp(self):
        from .scientific_eval import invalidate_scientific_cache
        from .services import invalidate_learned_boosts_cache

        invalidate_scientific_cache()
        invalidate_learned_boosts_cache()
        self.client = Client()

    def test_overlay_requires_staff_and_rejects_pii_terms(self):
        from .models import ActiveLearningRule

        regular_user = User.objects.create_user(username="user_regular", password="secret123", is_staff=False)
        staff_user = User.objects.create_user(username="admin_staff", password="secret123", is_staff=True)
        rule = ActiveLearningRule.objects.create(
            term="pliego municipal",
            target_action="auditar_criticar",
            source_z_score=1.4,
            is_active=True,
            created_by=staff_user,
        )

        # 1. Visitante anónimo -> 403 en approve y toggle + botones ocultos en /analitica/
        self.assertEqual(
            self.client.post(
                reverse("approve_learning_rule"),
                {"term": "expediente", "target_action": "auditar_criticar", "source_z_score": "1.5"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("toggle_learning_rule", args=[rule.id])).status_code,
            403,
        )

        # 2. Usuario común autenticado (is_staff=False) -> 403 y sin botones en /analitica/
        cli_reg = Client()
        cli_reg.force_login(regular_user)
        Prompt.objects.create(
            user=regular_user,
            original_text="Revisar expediente administrativo lote 1",
            improved_text="# Rol\nAuditor\n# Objetivo\nRevisar expediente.",
            category="Trámites y documentos",
            detected_action="auditar_criticar",
            improvement_level="Completa",
            initial_score=40,
            final_score=90,
            quality_gain=50,
            intent_confidence=0.40,
        )
        Prompt.objects.create(
            user=regular_user,
            original_text="Revisar expediente administrativo lote 2",
            improved_text="# Rol\nAuditor\n# Objetivo\nRevisar expediente.",
            category="Trámites y documentos",
            detected_action="auditar_criticar",
            improvement_level="Completa",
            initial_score=40,
            final_score=90,
            quality_gain=50,
            intent_confidence=0.40,
        )
        Prompt.objects.create(
            user=regular_user,
            original_text="Revisar expediente administrativo lote 3",
            improved_text="# Rol\nAuditor\n# Objetivo\nRevisar expediente.",
            category="Trámites y documentos",
            detected_action="auditar_criticar",
            improvement_level="Completa",
            initial_score=40,
            final_score=90,
            quality_gain=50,
            intent_confidence=0.40,
        )
        self.assertEqual(
            cli_reg.post(
                reverse("approve_learning_rule"),
                json.dumps({"term": "expediente", "target_action": "auditar_criticar"}),
                content_type="application/json",
            ).status_code,
            403,
        )
        self.assertEqual(cli_reg.post(reverse("toggle_learning_rule", args=[rule.id])).status_code, 403)
        an_reg = cli_reg.get(reverse("analytics")).content.decode("utf-8")
        self.assertIn("Solo cuentas administradoras", an_reg)
        self.assertNotIn("Aprobar en capa", an_reg)
        self.assertNotIn('name="target_action"', an_reg)

        # 3. Administrador staff (is_staff=True) -> rechaza PII / término corto con 400, aprueba válido con 302
        cli_staff = Client()
        cli_staff.force_login(staff_user)
        pii_resp = cli_staff.post(
            reverse("approve_learning_rule"),
            {"term": "dni 33.456.789", "target_action": "analizar_datos", "source_z_score": "1.2"},
        )
        self.assertEqual(pii_resp.status_code, 400)
        short_resp = cli_staff.post(
            reverse("approve_learning_rule"),
            {"term": "a!", "target_action": "analizar_datos", "source_z_score": "1.2"},
        )
        self.assertEqual(short_resp.status_code, 400)
        ok_resp = cli_staff.post(
            reverse("approve_learning_rule"),
            {"term": "expediente", "target_action": "auditar_criticar", "source_z_score": "1.6"},
        )
        self.assertEqual(ok_resp.status_code, 302)
        self.assertTrue(ActiveLearningRule.objects.filter(term="expediente", is_active=True).exists())
        tog_resp = cli_staff.post(reverse("toggle_learning_rule", args=[rule.id]))
        self.assertEqual(tog_resp.status_code, 302)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_guest_sentinel_unusable_password_reserved_username_and_no_first_user_leak(self):
        from .views import GUEST_SENTINEL_USERNAME

        registered = User.objects.create_user(username="usuario_registrado", password="clave_real_123")
        Prompt.objects.create(
            user=registered,
            original_text="Prompt estrictamente privado de usuario_registrado",
            improved_text="# Objetivo\nPrivado.",
            category="General",
        )

        # Visitante anónimo sin invitado_demo previo NO debe caer en registered
        guest_cli = Client()
        hist_resp = guest_cli.get(reverse("history"))
        self.assertEqual(hist_resp.status_code, 200)
        self.assertNotContains(hist_resp, "Prompt estrictamente privado de usuario_registrado")

        guest_user = User.objects.get(username=GUEST_SENTINEL_USERNAME)
        self.assertFalse(guest_user.has_usable_password())

        # No puede iniciar sesión con invitado_demo ni registrar ese nombre reservado
        login_resp = guest_cli.post(
            reverse("login"),
            {"username": GUEST_SENTINEL_USERNAME, "password": "123"},
        )
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, "no son correctos")

        reg_reserved = guest_cli.post(
            reverse("register"),
            {"username": "Invitado_Demo", "password": "password123", "password_confirm": "password123"},
        )
        self.assertEqual(reg_reserved.status_code, 200)
        self.assertContains(reg_reserved, "reservado")

    def test_csrf_enforced_and_input_length_cap_on_apis(self):
        csrf_cli = Client(enforce_csrf_checks=True)

        # GET / garantiza cookie CSRF
        ws_resp = csrf_cli.get(reverse("workspace"))
        self.assertEqual(ws_resp.status_code, 200)
        self.assertIn("csrftoken", csrf_cli.cookies)
        token = csrf_cli.cookies["csrftoken"].value

        # POST sin CSRF debe devolver 403
        no_csrf_imp = csrf_cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Explicar qué es SQL paso a paso"}),
            content_type="application/json",
        )
        self.assertEqual(no_csrf_imp.status_code, 403)

        no_csrf_live = csrf_cli.post(
            reverse("analyze_live_api"),
            data=json.dumps({"text": "Explicar qué es SQL paso a paso"}),
            content_type="application/json",
        )
        self.assertEqual(no_csrf_live.status_code, 403)

        # Con X-CSRFToken funciona 200
        with_csrf = csrf_cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": "Explicar qué es SQL paso a paso", "level": "Ligera"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(with_csrf.status_code, 200)

        # Texto > 15.000 chars devuelve 400
        too_long = "a" * 15001
        long_imp = csrf_cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({"text": too_long}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(long_imp.status_code, 400)
        long_live = csrf_cli.post(
            reverse("analyze_live_api"),
            data=json.dumps({"text": too_long}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(long_live.status_code, 400)

    def test_hardened_pii_money_cuit_mod11_secondary_fields_and_formal_note_demo_fix(self):
        # 1. Montos de dinero NO se enmascaran como DNI
        money_samples = [
            "Tengo un presupuesto de 1.500.000 pesos para equipamiento",
            "Gasto mensual de $ 1.200.000 en proveedores",
            "Tengo 1200000 de gastos fijos mensuales y margen del 30%",
        ]
        for txt in money_samples:
            masked_m, warn_m = detect_and_mask_pii(txt)
            self.assertEqual(warn_m, [], f"Falso positivo PII en monto: {txt}")
            self.assertNotIn("[DNI_CUIL_OCULTO]", masked_m)

        # 2. CUIT de 11 dígitos sin guiones válido Módulo 11 SÍ se enmascara; inválido NO; AFIP intacto
        masked_ok, warn_ok = detect_and_mask_pii("CUIT 20345678906 comprobante 0004-00018291")
        self.assertIn("[DNI_CUIL_OCULTO]", masked_ok)
        self.assertIn("0004-00018291", masked_ok)
        self.assertEqual({w["type"] for w in warn_ok}, {"dni_cuil"})

        masked_bad, warn_bad = detect_and_mask_pii("Código interno 20345678901 sin guiones")
        self.assertNotIn("[DNI_CUIL_OCULTO]", masked_bad)
        self.assertEqual(warn_bad, [])

        # 3. Alias en prosa con punto y celular argentino con 15
        masked_extra, warn_extra = detect_and_mask_pii(
            "Transferir a alias comercio.jujuy.mp o llamar al 388 15 4123456"
        )
        self.assertIn("alias: [ALIAS_OCULTO]", masked_extra)
        self.assertIn("[TELEFONO_OCULTO]", masked_extra)
        self.assertEqual({w["type"] for w in warn_extra}, {"alias_bancario", "telefono"})

        # 4. PII en user_example y form_data queda protegido con mask_pii=True y por default en /api/improve/
        res_sec = get_gemini_response(
            "Redactame un correo formal de seguimiento",
            level="Completa",
            form_data={"Público": "Titular DNI 33.456.789"},
            user_example="Contacto: maria.gomez@correo.com",
            mask_pii=True,
        )
        self.assertTrue(res_sec["has_pii_masked"])
        self.assertIn("[DNI_CUIL_OCULTO]", res_sec["improved_prompt"])
        self.assertIn("[EMAIL_OCULTO]", res_sec["improved_prompt"])
        self.assertNotIn("33.456.789", res_sec["improved_prompt"])
        self.assertNotIn("maria.gomez@correo.com", res_sec["improved_prompt"])

        cli = Client()
        default_api_resp = cli.post(
            reverse("improve_prompt_api"),
            data=json.dumps({
                "text": "Redactame una nota formal para Juan DNI 33.456.789 con factura 0004-00018291",
                "level": "Completa",
            }),
            content_type="application/json",
        )
        self.assertEqual(default_api_resp.status_code, 200)
        d_api = default_api_resp.json()
        self.assertTrue(d_api["has_pii_masked"])
        self.assertIn("[DNI_CUIL_OCULTO]", d_api["improved_prompt"])
        self.assertIn("0004-00018291", d_api["improved_prompt"])

        # 5. Bug demo: 4.º ejemplo de nota oficial NO debe decir 'Desglose de licencia'
        nota_social = (
            "Redactame una nota formal de seguimiento por una asistencia alimentaria para María Gómez, "
            "CUIL 27-34567890-4, cel 3884123456, mail maria.gomez@correo.com, "
            "adjuntando el comprobante AFIP 0004-00018291, en tono claro y respetuoso."
        )
        res_nota = get_gemini_response(nota_social, level="Completa", mask_pii=True)
        self.assertNotIn("Desglose de licencia", res_nota["improved_prompt"])
        self.assertIn("Desglose de nota formal", res_nota["improved_prompt"])

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        cli = Client()
        user = User.objects.create_user(username="csv_formula_user", password="secret123")
        cli.force_login(user)
        Prompt.objects.create(
            user=user,
            original_text='=HYPERLINK("http://evil.example","Click")',
            improved_text='+SUM(A1:A2)',
            category="Otro / General",
        )
        csv_resp = cli.get(reverse("export_csv"))
        self.assertEqual(csv_resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(csv_resp.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][36], '\'=HYPERLINK("http://evil.example","Click")')
        self.assertEqual(rows[1][37], "'+SUM(A1:A2)")

    def test_delete_root_prompt_promotes_oldest_child_preserving_family(self):
        cli = Client()
        user = User.objects.create_user(username="ver_del_user", password="secret123")
        cli.force_login(user)
        p1 = Prompt.objects.create(
            user=user,
            original_text="Explicar SQL v1",
            improved_text="# Objetivo\nSQL v1.",
            category="Tecnología y Programación",
            version_number=1,
        )
        p2 = Prompt.objects.create(
            user=user,
            original_text="Explicar SQL v2",
            improved_text="# Objetivo\nSQL v2.",
            category="Tecnología y Programación",
            parent_prompt=p1,
            root_prompt=p1,
            version_number=2,
        )
        p3 = Prompt.objects.create(
            user=user,
            original_text="Explicar SQL v3",
            improved_text="# Objetivo\nSQL v3.",
            category="Tecnología y Programación",
            parent_prompt=p2,
            root_prompt=p1,
            version_number=3,
        )

        del_resp = cli.post(reverse("delete_prompt", args=[p1.id]))
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(Prompt.objects.filter(id=p1.id).exists())

        p2.refresh_from_db()
        p3.refresh_from_db()
        self.assertIsNone(p2.root_prompt)
        self.assertIsNone(p2.parent_prompt)
        self.assertEqual(p3.root_prompt_id, p2.id)
        self.assertEqual(p3.parent_prompt_id, p2.id)

        hist_body = cli.get(reverse("history")).content.decode("utf-8")
        self.assertIn("Ver evolución (2 versiones)", hist_body)


