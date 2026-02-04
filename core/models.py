from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Custom User to store Department info
class User(AbstractUser):
    department = models.CharField(max_length=100, blank=True, null=True)

# 2. Region (Category for the sidebar)
class Region(models.Model):
    name = models.CharField(max_length=100, unique=True) # e.g., "Region I"

    def __str__(self):
        return self.name

# 3. Envelope (The Physical Folder)
class Envelope(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    title = models.CharField(max_length=200) # e.g., "Greenergy 2026"
    created_at = models.DateTimeField(auto_now_add=True)
    project_entity = models.CharField(max_length=200, blank=True, null=True)
    procuring_entity = models.CharField(max_length=200, blank=True, null=True)
    sales_name = models.CharField(max_length=200, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.region.name})"

# 4. Document (The actual content inside the folder)
class Document(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=200)  # The specific file name
    content_context = models.TextField()      # "Context" from your screenshot
    num_pages = models.IntegerField(default=1)
    date_notarized = models.DateField(null=True, blank=True)
    
    # Optional: If you want to actually upload a real file later
    file_upload = models.FileField(upload_to='docs/', blank=True, null=True)

    def __str__(self):
        return self.content_context
    
# ... (Your existing User, Region, Envelope, Document models)

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255) # e.g., "Deleted Folder", "Added Folder"
    details = models.TextField(blank=True, null=True) # e.g., "Deleted 'Tagalog' folder"
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"