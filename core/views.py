import csv
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db.models import Count
from .services import get_gemini_response, calculate_rubric_score
from .models import Prompt

TEMPLATES_CATALOG = {
    "analisis-datos-pandas": {
        "title": "Análisis Exploratorio de Datos (Pandas)",
        "category": "Investigar y analizar",
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
        "category": "Aprender y enseñar",
        "technique": "Pedagógico",
        "level": "Completa",
        "description": "Explica cualquier tema complejo desde cero usando analogías sencillas y preguntas de repaso para exámenes.",
        "text": "Explicar los conceptos fundamentales de regresión lineal y logística para estudiantes de ciencia de datos desde cero"
    },
    "control-comercial-stock": {
        "title": "Plan de Control de Inventario y Ventas",
        "category": "Trabajo y productividad",
        "technique": "Paso a Paso",
        "level": "Completa",
        "description": "Diseña un plan práctico para organizar stock, controlar vencimientos y mejorar la rentabilidad de un comercio.",
        "text": "Armar un plan paso a paso para controlar el stock, vencimientos y reposición de mercadería en un comercio minorista"
    },
    "comparativa-tecnica": {
        "title": "Tabla Comparativa de Tecnologías",
        "category": "Tecnología y programación",
        "technique": "Con Ejemplos",
        "level": "Completa",
        "description": "Compara dos herramientas, lenguajes o motores de bases de datos en una tabla clara con ventajas y casos de uso.",
        "text": "Comparar SQLite vs PostgreSQL en una tabla clara indicando ventajas, límites y cuándo conviene usar cada uno"
    },
    "redaccion-profesional": {
        "title": "Redacción de Correo o Propuesta Profesional",
        "category": "Crear y comunicar",
        "technique": "Estándar",
        "level": "Completa",
        "description": "Estructura mensajes formales, claros y persuasivos para clientes, proveedores o presentaciones académicas.",
        "text": "Redactar una respuesta profesional para este correo presentando una propuesta de trabajo clara y cordial"
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

            result = get_gemini_response(user_text, category, form_data, level, technique)

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
                    improvement_level=level,
                    technique=result.get('technique', technique),
                    initial_score=result.get('initial_score', 25),
                    final_score=result.get('final_score', 90),
                    quality_gain=result.get('quality_gain', 65)
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
    tech_stats = {}

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

        tech_name = p.technique or 'Estándar'
        if tech_name not in tech_stats:
            tech_stats[tech_name] = {'init': [], 'final': []}
        tech_stats[tech_name]['init'].append(i_score)
        tech_stats[tech_name]['final'].append(f_score)

    avg_orig_words = round(sum(orig_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_imp_words = round(sum(imp_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_expansion_ratio = round(sum(ratios) / total_prompts, 2) if total_prompts > 0 else 0.0
    avg_initial_score = round(sum(init_scores) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_final_score = round(sum(final_scores) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_quality_gain = round(sum(gains) / total_prompts, 1) if total_prompts > 0 else 0.0

    cat_qs = Prompt.objects.values('category').annotate(total=Count('id')).order_by('-total')
    cat_labels = [item['category'] or 'General' for item in cat_qs]
    cat_counts = [item['total'] for item in cat_qs]

    tech_qs = Prompt.objects.values('technique').annotate(total=Count('id')).order_by('-total')
    tech_labels = [item['technique'] or 'Estándar' for item in tech_qs]
    tech_counts = [item['total'] for item in tech_qs]

    tech_score_labels = list(tech_stats.keys())
    tech_init_avg = [round(sum(v['init']) / len(v['init']), 1) for v in tech_stats.values()]
    tech_final_avg = [round(sum(v['final']) / len(v['final']), 1) for v in tech_stats.values()]

    context = {
        'total_prompts': total_prompts,
        'favorites_count': favorites_count,
        'approval_rate': approval_rate,
        'avg_orig_words': avg_orig_words,
        'avg_imp_words': avg_imp_words,
        'avg_expansion_ratio': avg_expansion_ratio,
        'avg_initial_score': avg_initial_score,
        'avg_final_score': avg_final_score,
        'avg_quality_gain': avg_quality_gain,
        'cat_labels_json': json.dumps(cat_labels),
        'cat_counts_json': json.dumps(cat_counts),
        'tech_labels_json': json.dumps(tech_labels),
        'tech_counts_json': json.dumps(tech_counts),
        'tech_score_labels_json': json.dumps(tech_score_labels),
        'tech_init_avg_json': json.dumps(tech_init_avg),
        'tech_final_avg_json': json.dumps(tech_final_avg),
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
        'categoria',
        'nivel_mejora',
        'tecnica_aplicada',
        'puntaje_inicial',
        'puntaje_final',
        'ganancia_calidad_pts',
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

        writer.writerow([
            p.id,
            p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            p.category or 'General',
            p.improvement_level,
            p.technique or 'Estándar',
            p.initial_score,
            p.final_score,
            p.quality_gain,
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
