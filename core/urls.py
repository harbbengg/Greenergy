from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Folder Actions
    path('envelope/edit/<int:id>/', views.edit_envelope, name='edit_envelope'),
    path('envelope/delete/<int:id>/', views.delete_envelope, name='delete_envelope'),

    # Region Actions
    path('region/edit/<int:id>/', views.edit_region, name='edit_region'),
    path('region/delete/<int:id>/', views.delete_region, name='delete_region'),

    # AJAX Actions
    path('add-document-type/', views.add_document_type, name='add_document_type'),
    path('delete-document-type/', views.delete_document_type, name='delete_document_type'),
    path('update-print-status/', views.update_print_status, name='update_print_status'), # NEW
    path('bulk-update-door/', views.bulk_update_door, name='bulk_update_door'),
]