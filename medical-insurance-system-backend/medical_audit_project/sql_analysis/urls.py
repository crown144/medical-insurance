from django.urls import path

from . import views


urlpatterns = [
    path('sql/rules', views.sql_rule_collection, name='sql_rule_collection'),
    path('sql/rules/<int:pk>', views.sql_rule_item, name='sql_rule_item'),
    path('sql/execute', views.sql_execute, name='sql_execute'),
    path('sql/history', views.sql_history_collection, name='sql_history_collection'),
    path('sql/history/<int:pk>', views.sql_history_item, name='sql_history_item'),
    path('sql/history/<int:pk>/download', views.sql_history_download, name='sql_history_download'),
    path('sql/results/rules', views.sql_result_rule_collection, name='sql_result_rule_collection'),
    path('sql/results/rules/<int:pk>', views.sql_result_rule_item, name='sql_result_rule_item'),
]
