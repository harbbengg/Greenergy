from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Region, Envelope, Document

# 1. Define a custom Admin class for your User
class CustomUserAdmin(UserAdmin):
    model = User
    
    # Add 'department' to the "Edit User" page
    # UserAdmin.fieldsets already contains the Password, Username, Permissions, etc.
    # We just add your custom field to the bottom.
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Info', {'fields': ('department',)}),
    )

    # Add 'department' to the "Add User" page (when creating a new user)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Info', {'fields': ('department',)}),
    )

# 2. Register User with the new configuration
admin.site.register(User, CustomUserAdmin)

# 3. Register the other models normally
admin.site.register(Region)
admin.site.register(Envelope)
admin.site.register(Document)