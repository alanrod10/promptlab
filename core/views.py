import csv
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db.models import Count
from .services import get_gemini_response, calculate_rubric_score, analyze_live_preview
from .universal_engine import mine_long_tail_candidates
from .models import Prompt

TEMPLATES_CATALOG = {
    "analisis-datos-pandas": {
        "title": "Análisis Exploratorio de Datos (Pandas)",
        "category": "Ciencia de Datos e IA",
        "technique": "Paso a Paso",
        "level": "Profunda",
        "description": "Estructura un flujo completo en Python y Pandas para limpiar datos, detectar valores nulos y obtener conclusiones estadísticas.",
        "text": "Analizar este dataset en Python con Pandas para limpiar valores nulos, calcular estadísticas descriptivas y encontrar patrones clave"
    },
    "programacion-debug": {
        "title": "Depuración y Corrección de Código",
        "category": "Tecnología y programación",
        "technique": "Verificación",
        "level": "Completa",
        "description": "Ideal para encontrar la causa raíz de un error en Python, SQL o JavaScript y obtener el código corregido.",
        "text": "Depurar este error en mi script de Python explicando la causa del problema y cómo solucionarlo paso a paso"
    },
    "estudio-pedagogico": {
        "title": "Guía de Estudio con Ejemplos y Autoevaluación",
        "category": "Estudio y academia",
        "technique": "Pedagógico",
        "level": "Completa",
        "description": "Explica cualquier tema complejo desde cero usando analogías sencillas y preguntas de repaso para exámenes.",
        "text": "Explicar los conceptos fundamentales de regresión lineal y logística para estudiantes de ciencia de datos desde cero"
    },
    "control-comercial-stock": {
        "title": "Plan de Control de Inventario y Ventas",
        "category": "Negocios y comercio",
        "technique": "Paso a Paso",
        "level": "Completa",
        "description": "Diseña un plan práctico para organizar stock, controlar vencimientos y mejorar la rentabilidad de un comercio.",
        "text": "Armar un plan paso a paso para controlar el stock, vencimientos y reposición de mercadería en un comercio minorista"
    },
    "redaccion-profesional": {
        "title": "Redacción de Correo o Propuesta Profesional",
        "category": "Redacción y comunicación",
        "technique": "Estándar",
        "level": "Completa",
        "description": "Estructura mensajes formales, claros y persuasivos para clientes, proveedores o presentaciones académicas.",
        "text": "Redactar una respuesta profesional para este correo presentando una propuesta de trabajo clara y cordial"
    },
    "tramites-nota-formal": {
        "title": "Nota Formal o Reclamo Administrativo",
        "category": "Trámites y documentos",
        "technique": "Verificación",
        "level": "Completa",
        "description": "Redacta reclamos formales, descargos o solicitudes administrativas con estructura clara y marcadores seguros.",
        "text": "Redactame una nota formal de reclamo por demora en la entrega de un servicio indicando hechos, plazos y solicitud concreta"
    },
    "planificacion-roadmap": {
        "title": "Hoja de Ruta y Cronograma de Proyecto",
        "category": "Planificación y productividad",
        "technique": "Paso a Paso",
        "level": "Completa",
        "description": "Divide metas complejas en hitos semanales, prioridades y entregables concretos.",
        "text": "Planificar un cronograma de 4 semanas con hitos, prioridades y entregables para lanzar una aplicación web"
    },
    "decision-comparativa": {
        "title": "Matriz de Decisión y Comparativa",
        "category": "Toma de decisiones",
        "technique": "Con Ejemplos",
        "level": "Completa",
        "description": "Evalúa alternativas con criterios ponderados, ventajas, riesgos y recomendación fundamentada.",
        "text": "Comparar SQLite vs PostgreSQL en una tabla clara indicando ventajas, límites y cuándo conviene elegir cada uno"
    }
}

def workspace(request):
    prompt_id = request.GET.get('load')
    preset_slug = request.GET.get('preset')
    loaded_prompt = None
    preset_data = None
    loaded_rubric_json = 'null'

    if prompt_id:
        loaded_prompt = Prompt.objects.filter(id=prompt_id).first()
        if loaded_prompt:
            rubric = calculate_rubric_score(loaded_prompt.improved_text)
            loaded_rubric_json = json.dumps(rubric['breakdown'])
    elif preset_slug and preset_slug in TEMPLATES_CATALOG:
        preset_data = TEMPLATES_CATALOG[preset_slug]

    return render(request, 'core/workspace.html', {
        'loaded_prompt': loaded_prompt,
        'preset_data': preset_data,
        'loaded_rubric_json': loaded_rubric_json,
    })

def history(request):
    prompts = Prompt.objects.all().order_by('-created_at')
    categories = sorted({p.category or 'General' for p in prompts})
    techniques = sorted({p.technique or 'Estándar' for p in prompts})
    return render(request, 'core/history.html', {
        'prompts': prompts,
        'only_favorites': False,
        'categories': categories,
        'techniques': techniques,
    })

def favorites(request):
    prompts = Prompt.objects.filter(is_favorite=True).order_by('-created_at')
    categories = sorted({p.category or 'General' for p in prompts})
    techniques = sorted({p.technique or 'Estándar' for p in prompts})
    return render(request, 'core/history.html', {
        'prompts': prompts,
        'only_favorites': True,
        'categories': categories,
        'techniques': techniques,
    })

@require_POST
def toggle_favorite(request, prompt_id):
    prompt = get_object_or_404(Prompt, id=prompt_id)
    prompt.is_favorite = not prompt.is_favorite
    prompt.save()
    next_url = request.POST.get('next') or request.GET.get('next') or 'history'
    if next_url not in ('history', 'favorites'):
        next_url = 'history'
    return redirect(next_url)

@require_POST
def delete_prompt(request, prompt_id):
    prompt = get_object_or_404(Prompt, id=prompt_id)
    prompt.delete()
    next_url = request.POST.get('next') or request.GET.get('next') or 'history'
    if next_url not in ('history', 'favorites'):
        next_url = 'history'
    return redirect(next_url)

def templates_gallery(request):
    return render(request, 'core/templates_gallery.html', {'templates': TEMPLATES_CATALOG})

@csrf_exempt
def analyze_live_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                return JsonResponse({"error": "Formato JSON inválido: se esperaba un objeto."}, status=400)

            user_text = data.get('text', '')
            if not isinstance(user_text, str):
                return JsonResponse({"error": "El campo 'text' debe ser una cadena de texto."}, status=400)

            category = data.get('category', '')
            form_data = data.get('form_data', {})
            if not isinstance(form_data, dict):
                form_data = {}
            technique = data.get('technique', 'Estándar')
            override_domain = data.get('override_domain', '') or ''
            override_action = data.get('override_action', '') or ''
            override_deliverable = data.get('override_deliverable', '') or ''
            negative_constraints = data.get('negative_constraints', [])
            if not isinstance(negative_constraints, list):
                negative_constraints = []

            result = analyze_live_preview(
                text=user_text,
                category=category,
                form_data=form_data,
                technique=technique,
                override_domain=override_domain,
                override_action=override_action,
                override_deliverable=override_deliverable,
                negative_constraints=negative_constraints,
            )
            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON malformado en la solicitud."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
def improve_prompt_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                return JsonResponse({"error": "Formato JSON inválido: se esperaba un objeto."}, status=400)

            user_text = data.get('text', '')
            if not isinstance(user_text, str):
                return JsonResponse({"error": "El campo 'text' debe ser una cadena de texto."}, status=400)

            category = data.get('category', 'Otro / No sé')
            form_data = data.get('form_data', {})
            if not isinstance(form_data, dict):
                form_data = {}
            level = data.get('level', 'Completa')
            if level not in ('Ligera', 'Completa', 'Profunda'):
                level = 'Completa'
            technique = data.get('technique', 'Estándar')

            override_domain = data.get('override_domain', '') or ''
            override_action = data.get('override_action', '') or ''
            override_deliverable = data.get('override_deliverable', '') or ''
            negative_constraints = data.get('negative_constraints', [])
            if not isinstance(negative_constraints, list):
                negative_constraints = []
            user_example = data.get('user_example', '') or ''
            mask_pii = bool(data.get('mask_pii', False))

            result = get_gemini_response(
                user_text=user_text,
                category=category,
                form_data=form_data,
                level=level,
                technique=technique,
                override_domain=override_domain,
                override_action=override_action,
                override_deliverable=override_deliverable,
                negative_constraints=negative_constraints,
                user_example=user_example,
                mask_pii=mask_pii,
            )

            if 'improved_prompt' in result:
                user = request.user if request.user.is_authenticated else User.objects.first()
                if not user:
                    user = User.objects.create_user(username='alan', password='123')

                resolved_cat = result.get('category') or category or 'General'
                raw_orig = result.get('raw_objective') or user_text
                Prompt.objects.create(
                    user=user,
                    original_text=raw_orig,
                    improved_text=result['improved_prompt'],
                    category=resolved_cat,
                    detected_action=result.get('detected_action', 'explicar_concepto'),
                    detected_deliverable=result.get('detected_deliverable', 'informe estructurado'),
                    subintent=result.get('subintent', 'general'),
                    improvement_level=level,
                    technique=result.get('technique', technique),
                    engine_version=result.get('engine_version', 'v6.0'),
                    initial_score=result.get('initial_score', 25),
                    information_gain=result.get('information_gain', 0),
                    final_score=result.get('final_score', 90),
                    quality_gain=result.get('quality_gain', 65),
                    intent_confidence=result.get('intent_confidence', 0.85),
                    intent_margin=result.get('intent_margin', 0.30),
                    n_intents=result.get('n_intents', 1),
                    n_entities=result.get('n_entities', 0),
                    n_neg_constraints=result.get('n_neg_constraints', 0),
                    n_slots_used=result.get('n_slots_used', 0),
                    info_density=result.get('info_density', 0.0),
                    noise_ratio=result.get('noise_ratio', 0.04),
                    anchor_coverage=result.get('anchor_coverage', 0.95),
                    payload_kind=result.get('payload_kind', 'sin_insumo'),
                    roles_filled=result.get('roles_filled', 0.80),
                    verifiable_ratio=result.get('verifiable_ratio', 0.85),
                    user_corrected=result.get('user_corrected', False),
                    has_pii_masked=result.get('has_pii_masked', False),
                )

            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON malformado en la solicitud."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)

def analytics_dashboard(request):
    prompts = list(Prompt.objects.all())
    total_prompts = len(prompts)
    favorites_count = sum(1 for p in prompts if p.is_favorite)
    approval_rate = round((favorites_count / total_prompts) * 100, 1) if total_prompts > 0 else 0.0

    orig_words_list = []
    imp_words_list = []
    ratios = []
    init_scores = []
    final_scores = []
    gains = []
    info_gains = []
    densities = []
    noise_ratios = []
    anchor_coverages = []
    roles_filled_list = []
    verifiable_ratios = []
    confidences = []
    corrected_count = 0
    tech_stats = {}
    action_stats = {}

    for p in prompts:
        o_words = max(len(p.original_text.split()), 1)
        i_words = max(len(p.improved_text.split()), 1)
        orig_words_list.append(o_words)
        imp_words_list.append(i_words)
        ratios.append(i_words / o_words)

        # Cálculo en memoria para registros antiguos sin mutar la BD en una petición GET
        if not p.final_score or p.final_score == 0:
            i_score = calculate_rubric_score(p.original_text)["total"]
            f_score = calculate_rubric_score(p.improved_text)["total"]
            gain = max(f_score - i_score, 0)
        else:
            i_score = p.initial_score
            f_score = p.final_score
            gain = p.quality_gain

        init_scores.append(i_score)
        final_scores.append(f_score)
        gains.append(gain)
        info_gains.append(p.information_gain)
        densities.append(p.info_density)
        noise_ratios.append(p.noise_ratio * 100.0)
        anchor_coverages.append(p.anchor_coverage * 100.0)
        roles_filled_list.append(p.roles_filled * 100.0)
        verifiable_ratios.append(p.verifiable_ratio * 100.0)
        confidences.append(p.intent_confidence * 100.0)
        if p.user_corrected:
            corrected_count += 1

        tech_name = p.technique or 'Estándar'
        if tech_name not in tech_stats:
            tech_stats[tech_name] = {'init': [], 'final': []}
        tech_stats[tech_name]['init'].append(i_score)
        tech_stats[tech_name]['final'].append(f_score)

        act_name = (p.detected_action or 'explicar_concepto').replace('_', ' ').capitalize()
        if act_name not in action_stats:
            action_stats[act_name] = {'init': [], 'final': []}
        action_stats[act_name]['init'].append(i_score)
        action_stats[act_name]['final'].append(f_score)

    avg_orig_words = round(sum(orig_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_imp_words = round(sum(imp_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_expansion_ratio = round(sum(ratios) / total_prompts, 2) if total_prompts > 0 else 0.0
    avg_initial_score = round(sum(init_scores) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_user_score = avg_initial_score
    avg_info_gain = round(sum(info_gains) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_final_score = round(sum(final_scores) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_quality_gain = round(sum(gains) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_info_density = round(sum(densities) / total_prompts, 3) if total_prompts > 0 else 0.0
    avg_noise_ratio = round(sum(noise_ratios) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_anchor_coverage = round(sum(anchor_coverages) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_roles_filled = round(sum(roles_filled_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_verifiable_ratio = round(sum(verifiable_ratios) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_confidence = round(sum(confidences) / total_prompts, 1) if total_prompts > 0 else 0.0
    correction_rate = round((corrected_count / total_prompts) * 100, 1) if total_prompts > 0 else 0.0
    long_tail_candidates = mine_long_tail_candidates(prompts, top_n=8)

    cat_qs = Prompt.objects.values('category').annotate(total=Count('id')).order_by('-total')
    cat_labels = [item['category'] or 'General' for item in cat_qs]
    cat_counts = [item['total'] for item in cat_qs]

    tech_qs = Prompt.objects.values('technique').annotate(total=Count('id')).order_by('-total')
    tech_labels = [item['technique'] or 'Estándar' for item in tech_qs]
    tech_counts = [item['total'] for item in tech_qs]

    tech_score_labels = list(tech_stats.keys())
    tech_init_avg = [round(sum(v['init']) / len(v['init']), 1) for v in tech_stats.values()]
    tech_final_avg = [round(sum(v['final']) / len(v['final']), 1) for v in tech_stats.values()]

    action_labels = list(action_stats.keys())
    action_init_scores = [round(sum(v['init']) / len(v['init']), 1) for v in action_stats.values()]
    action_final_scores = [round(sum(v['final']) / len(v['final']), 1) for v in action_stats.values()]

    context = {
        'total_prompts': total_prompts,
        'favorites_count': favorites_count,
        'approval_rate': approval_rate,
        'avg_orig_words': avg_orig_words,
        'avg_imp_words': avg_imp_words,
        'avg_expansion_ratio': avg_expansion_ratio,
        'avg_initial_score': avg_initial_score,
        'avg_user_score': avg_user_score,
        'avg_info_gain': avg_info_gain,
        'avg_final_score': avg_final_score,
        'avg_quality_gain': avg_quality_gain,
        'avg_info_density': avg_info_density,
        'avg_noise_ratio': avg_noise_ratio,
        'avg_anchor_coverage': avg_anchor_coverage,
        'avg_roles_filled': avg_roles_filled,
        'avg_verifiable_ratio': avg_verifiable_ratio,
        'long_tail_candidates': long_tail_candidates,
        'avg_confidence': avg_confidence,
        'correction_rate': correction_rate,
        'cat_labels_json': json.dumps(cat_labels),
        'cat_counts_json': json.dumps(cat_counts),
        'tech_labels_json': json.dumps(tech_labels),
        'tech_counts_json': json.dumps(tech_counts),
        'tech_score_labels_json': json.dumps(tech_score_labels),
        'tech_init_avg_json': json.dumps(tech_init_avg),
        'tech_final_avg_json': json.dumps(tech_final_avg),
        'action_labels_json': json.dumps(action_labels),
        'action_init_scores_json': json.dumps(action_init_scores),
        'action_final_scores_json': json.dumps(action_final_scores),
    }
    return render(request, 'core/analytics.html', context)

def export_dataset_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="promptlab_dataset.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    writer.writerow([
        'id',
        'fecha_creacion',
        'engine_version',
        'categoria',
        'detected_action',
        'detected_deliverable',
        'subintent',
        'nivel_mejora',
        'tecnica_aplicada',
        'puntaje_inicial',
        'information_gain',
        'puntaje_final',
        'ganancia_calidad_pts',
        'intent_confidence',
        'intent_margin',
        'n_intents',
        'n_entities',
        'n_neg_constraints',
        'n_slots_used',
        'info_density',
        'noise_ratio',
        'anchor_coverage',
        'payload_kind',
        'roles_filled',
        'verifiable_ratio',
        'tiene_criterio_exito',
        'user_corrected',
        'has_pii_masked',
        'es_favorito',
        'palabras_entrada',
        'palabras_salida',
        'caracteres_entrada',
        'caracteres_salida',
        'factor_expansion',
        'bloques_estructura',
        'tiene_delimitadores',
        'texto_original',
        'prompt_mejorado'
    ])

    for p in Prompt.objects.all().order_by('id'):
        o_words = max(len(p.original_text.split()), 1)
        i_words = max(len(p.improved_text.split()), 1)
        o_chars = len(p.original_text)
        i_chars = len(p.improved_text)
        ratio = round(i_words / o_words, 2)
        blocks_count = len(re.findall(r'^#\s+.+', p.improved_text, flags=re.MULTILINE))
        has_delimiters = int('<datos_entrada>' in p.improved_text)
        has_success_criteria = int('# Criterio de éxito' in p.improved_text)

        writer.writerow([
            p.id,
            p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            p.engine_version,
            p.category or 'General',
            p.detected_action,
            p.detected_deliverable,
            p.subintent,
            p.improvement_level,
            p.technique or 'Estándar',
            p.initial_score,
            p.information_gain,
            p.final_score,
            p.quality_gain,
            p.intent_confidence,
            p.intent_margin,
            p.n_intents,
            p.n_entities,
            p.n_neg_constraints,
            p.n_slots_used,
            p.info_density,
            p.noise_ratio,
            p.anchor_coverage,
            p.payload_kind,
            p.roles_filled,
            p.verifiable_ratio,
            has_success_criteria,
            int(p.user_corrected),
            int(p.has_pii_masked),
            int(p.is_favorite),
            o_words,
            i_words,
            o_chars,
            i_chars,
            ratio,
            blocks_count,
            has_delimiters,
            p.original_text,
            p.improved_text
        ])

    return response
