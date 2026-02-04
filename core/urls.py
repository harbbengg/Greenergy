from django.urls import path
from . import views

urlpatterns = [
    # 1. Main Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # 2. Signup
    path('signup/', views.signup_view, name='signup'),
    
    # 3. THESE ARE MISSING - Add them exactly like this:
    path('delete/<int:id>/', views.delete_envelope, name='delete_envelope'),
    path('edit/<int:id>/', views.edit_envelope, name='edit_envelope'),

    path('region/edit/<int:id>/', views.edit_region, name='edit_region'),
    path('region/delete/<int:id>/', views.delete_region, name='delete_region'),
]