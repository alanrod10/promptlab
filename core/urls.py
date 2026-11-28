from django.urls import path
from . import views

urlpatterns = [
    path('', views.workspace, name='workspace'),
    path('historial/', views.history, name='history'),
    path('favoritos/', views.favorites, name='favorites'),
    path('historial/favorito/<int:prompt_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('historial/eliminar/<int:prompt_id>/', views.delete_prompt, name='delete_prompt'),
    path('plantillas/', views.templates_gallery, name='templates_gallery'),
    path('plantillas/propias/crear/', views.create_user_template, name='create_user_template'),
    path('plantillas/propias/eliminar/<int:template_id>/', views.delete_user_template, name='delete_user_template'),
    path('plantillas/propias/exportar-json/', views.export_user_templates_json, name='export_user_templates_json'),
    path('plantillas/propias/importar-json/', views.import_user_templates_json, name='import_user_templates_json'),
    path('analitica/', views.analytics_dashboard, name='analytics'),
    path('analitica/exportar-csv/', views.export_dataset_csv, name='export_csv'),
    path('analitica/aprendizaje/aprobar/', views.approve_learning_rule, name='approve_learning_rule'),
    path('analitica/aprendizaje/revertir/<int:rule_id>/', views.toggle_learning_rule, name='toggle_learning_rule'),
    path('glosario/', views.glossary_view, name='glossary'),
    path('api/improve/', views.improve_prompt_api, name='improve_prompt_api'),
    path('api/analyze-live/', views.analyze_live_api, name='analyze_live_api'),
    path('ingresar/', views.login_view, name='login'),
    path('registro/', views.register_view, name='register'),
    path('salir/', views.logout_view, name='logout'),
]
