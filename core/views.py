from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Count
import csv
import json
from .services import get_gemini_response
from .models import Prompt

TEMPLATES_CATALOG = [
    {
        "slug": "programacion-debug",
        "title": "Programación y Debug",
        "category": "Tecnología y programación",
        "icon": "bi-bug-fill",
        "color": "primary",
        "description": "Encuentra la causa raíz de un error en tu código y obtén una solución limpia y probada.",
        "prompt_text": "Analiza este código, identifica la causa raíz del error que impide su ejecución y propón una versión corregida con buenas prácticas."
    },
    {
        "slug": "ciencia-datos-pandas",
        "title": "Ciencia de Datos / Pandas",
        "category": "Tecnología y programación",
        "icon": "bi-bar-chart-line-fill",
        "color": "info",
        "description": "Genera scripts en Python y Pandas para limpiar, transformar y analizar conjuntos de datos.",
        "prompt_text": "Escribe un script en Python usando Pandas para limpiar valores nulos, agrupar estos datos por categoría y generar un resumen estadístico."
    },
    {
        "slug": "plan-estudio",
        "title": "Plan de Estudio",
        "category": "Aprender y enseñar",
        "icon": "bi-mortarboard-fill",
        "color": "success",
        "description": "Crea una ruta de aprendizaje paso a paso adaptada a tu nivel y tiempo disponible.",
        "prompt_text": "Diseña un plan de estudio paso a paso de 4 semanas para aprender fundamentos de bases de datos SQL desde cero, con ejercicios prácticos."
    },
    {
        "slug": "estrategia-comercial",
        "title": "Estrategia Comercial",
        "category": "Trabajo y productividad",
        "icon": "bi-graph-up-arrow",
        "color": "warning",
        "description": "Define acciones concretas, KPIs y propuestas de valor para impulsar ventas o proyectos.",
        "prompt_text": "Elabora una estrategia comercial en formato tabla para aumentar la retención de clientes recurrentes en un negocio minorista durante el próximo trimestre."
    },
    {
        "slug": "resumen-ejecutivo",
        "title": "Resumen Ejecutivo",
        "category": "Investigar y analizar",
        "icon": "bi-file-earmark-text-fill",
        "color": "secondary",
        "description": "Sintetiza documentos extensos en puntos clave accionables y conclusiones directas.",
        "prompt_text": "Resume este texto en un informe ejecutivo breve con las 5 ideas principales, riesgos detectados y recomendaciones accionables."
    },
    {
        "slug": "redaccion-profesional",
        "title": "Redacción Profesional",
        "category": "Crear y comunicar",
        "icon": "bi-envelope-paper-fill",
        "color": "danger",
        "description": "Redacta correos, comunicados o publicaciones persuasivas adaptadas a tu audiencia.",
        "prompt_text": "Redacta un correo profesional y empático dirigido a un cliente para informar el estado de su proyecto y coordinar una reunión de seguimiento."
    },
]


def workspace(request):
    prompt_id = request.GET.get('load')
    preset_slug = request.GET.get('preset')
    template_text = request.GET.get('template_text', '')

    loaded_prompt = None
    preset_text = ''
    preset_category = ''

    if prompt_id:
        loaded_prompt = Prompt.objects.filter(id=prompt_id).first()
    elif preset_slug:
        matched = next((t for t in TEMPLATES_CATALOG if t['slug'] == preset_slug), None)
        if matched:
            preset_text = matched['prompt_text']
            preset_category = matched['category']
    elif template_text:
        preset_text = template_text

    return render(request, 'core/workspace.html', {
        'loaded_prompt': loaded_prompt,
        'preset_text': preset_text,
        'preset_category': preset_category,
    })


def history(request):
    prompts = Prompt.objects.all().order_by('-created_at')
    return render(request, 'core/history.html', {'prompts': prompts, 'only_favorites': False})


def favorites(request):
    prompts = Prompt.objects.filter(is_favorite=True).order_by('-created_at')
    return render(request, 'core/history.html', {'prompts': prompts, 'only_favorites': True})


def toggle_favorite(request, prompt_id):
    prompt = get_object_or_404(Prompt, id=prompt_id)
    prompt.is_favorite = not prompt.is_favorite
    prompt.save()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'is_favorite': prompt.is_favorite})
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('history')


def templates_gallery(request):
    return render(request, 'core/templates_gallery.html', {'templates': TEMPLATES_CATALOG})


def delete_prompt(request, prompt_id):
    prompt = get_object_or_404(Prompt, id=prompt_id)
    prompt.delete()
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('history')


@csrf_exempt
def improve_prompt_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_text = data.get('text', '')
            category = data.get('category', 'Otro / No sé')
            form_data = data.get('form_data', {})
            level = data.get('level', 'Completa')

            result = get_gemini_response(user_text, category, form_data, level)

            if 'improved_prompt' in result:
                user = request.user if request.user.is_authenticated else User.objects.first()
                if not user:
                    user = User.objects.create_user(username='alan', password='123')

                Prompt.objects.create(
                    user=user,
                    original_text=user_text,
                    improved_text=result['improved_prompt'],
                    category=category,
                    improvement_level=level
                )

            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)


def analytics_dashboard(request):
    prompts = Prompt.objects.all()
    total_prompts = prompts.count()
    favorites_count = prompts.filter(is_favorite=True).count()
    approval_rate = round((favorites_count / total_prompts) * 100, 1) if total_prompts > 0 else 0.0

    orig_words_list = []
    imp_words_list = []
    ratios = []

    for p in prompts:
        o_words = max(len(p.original_text.split()), 1)
        i_words = max(len(p.improved_text.split()), 1)
        orig_words_list.append(o_words)
        imp_words_list.append(i_words)
        ratios.append(i_words / o_words)

    avg_orig_words = round(sum(orig_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_imp_words = round(sum(imp_words_list) / total_prompts, 1) if total_prompts > 0 else 0.0
    avg_expansion_ratio = round(sum(ratios) / total_prompts, 2) if total_prompts > 0 else 0.0

    cat_qs = prompts.values('category').annotate(total=Count('id')).order_by('-total')
    cat_labels = [item['category'] or 'Sin categoría' for item in cat_qs]
    cat_counts = [item['total'] for item in cat_qs]

    level_qs = prompts.values('improvement_level').annotate(total=Count('id')).order_by('-total')
    level_labels = [item['improvement_level'] or 'Completa' for item in level_qs]
    level_counts = [item['total'] for item in level_qs]

    context = {
        'total_prompts': total_prompts,
        'favorites_count': favorites_count,
        'approval_rate': approval_rate,
        'avg_orig_words': avg_orig_words,
        'avg_imp_words': avg_imp_words,
        'avg_expansion_ratio': avg_expansion_ratio,
        'cat_labels_json': json.dumps(cat_labels),
        'cat_counts_json': json.dumps(cat_counts),
        'level_labels_json': json.dumps(level_labels),
        'level_counts_json': json.dumps(level_counts),
    }
    return render(request, 'core/analytics.html', context)


def export_dataset_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="promptlab_dataset.csv"'
    response.write('\ufeff')  # BOM UTF-8 para compatibilidad directa con Excel y Pandas

    writer = csv.writer(response)
    writer.writerow([
        'id',
        'created_at',
        'category',
        'improvement_level',
        'is_favorite',
        'original_words',
        'improved_words',
        'expansion_ratio',
        'original_text',
        'improved_text'
    ])

    for p in Prompt.objects.all().order_by('id'):
        o_words = max(len(p.original_text.split()), 1)
        i_words = max(len(p.improved_text.split()), 1)
        ratio = round(i_words / o_words, 2)
        writer.writerow([
            p.id,
            p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            p.category or 'Sin categoría',
            p.improvement_level,
            int(p.is_favorite),
            o_words,
            i_words,
            ratio,
            p.original_text,
            p.improved_text
        ])

    return response
