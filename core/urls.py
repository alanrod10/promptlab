from django.urls import path
from . import views

urlpatterns = [
    path('', views.workspace, name='workspace'),
    path('historial/', views.history, name='history'),
    path('historial/eliminar/<int:prompt_id>/', views.delete_prompt, name='delete_prompt'),
    path('api/improve/', views.improve_prompt_api, name='improve_prompt_api'),
]
