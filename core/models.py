from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Custom User
class User(AbstractUser):
    department = models.TextField(blank=True, null=True)

# 2. Region
class Region(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

# 3. Envelope (Parent Folder)
class Envelope(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    title = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True)
    # NEW FIELD: Tracks if printed
    is_printed = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.title} ({self.region.name})"

# 4. Envelope Meta (Child)
class EnvelopeMeta(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name='meta_details')
    project_entity = models.TextField(blank=True, null=True)
    procuring_entity = models.TextField(blank=True, null=True)
    sales_name = models.TextField(blank=True, null=True)
    door_number = models.TextField(blank=True, null=True)

# 5. Documents
class Document(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name='documents')
    title = models.TextField(blank=True)
    content_context = models.TextField()
    num_pages = models.IntegerField(default=1)
    date_notarized = models.DateField(null=True, blank=True)
    file_upload = models.FileField(upload_to='docs/', blank=True, null=True)

    def __str__(self):
        return self.content_context

# 6. Document Types (For Suggestions)
class DocumentType(models.Model):
    name = models.TextField(unique=True) 

    def __str__(self):
        return self.name

# 7. Audit Log
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.TextField()
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"