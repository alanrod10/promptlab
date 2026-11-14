from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
import json
from .services import get_gemini_response
from .models import Prompt

def workspace(request):
    prompt_id = request.GET.get('load')
    loaded_prompt = None
    if prompt_id:
        loaded_prompt = Prompt.objects.filter(id=prompt_id).first()
    return render(request, 'core/workspace.html', {'loaded_prompt': loaded_prompt})

def history(request):
    prompts = Prompt.objects.all().order_by('-created_at')
    return render(request, 'core/history.html', {'prompts': prompts})

def delete_prompt(request, prompt_id):
    prompt = get_object_or_404(Prompt, id=prompt_id)
    prompt.delete()
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
