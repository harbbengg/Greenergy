#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install Requirements
pip install -r requirements.txt

# 2. Collect Static Files
python manage.py collectstatic --noinput

# 3. Migrate Database
python manage.py migrate

# 4. Create Superuser Automatically (if not exists)
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin / admin123')
else:
    print('Superuser already exists')
"