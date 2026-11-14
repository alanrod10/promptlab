from django.urls import path
from . import views

urlpatterns = [
    path('', views.workspace, name='workspace'),
    path('historial/', views.history, name='history'),
    path('favoritos/', views.favorites, name='favorites'),
    path('historial/favorito/<int:prompt_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('historial/eliminar/<int:prompt_id>/', views.delete_prompt, name='delete_prompt'),
    path('plantillas/', views.templates_gallery, name='templates_gallery'),
    path('analitica/', views.analytics_dashboard, name='analytics'),
    path('analitica/exportar-csv/', views.export_dataset_csv, name='export_csv'),
    path('api/improve/', views.improve_prompt_api, name='improve_prompt_api'),
]
