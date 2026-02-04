from django.contrib import admin
from django.urls import path, include  # <--- Make sure 'include' is here

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This line connects your 'core' app to the main project
    path('', include('core.urls')), 
    
    path('accounts/', include('django.contrib.auth.urls')),
]