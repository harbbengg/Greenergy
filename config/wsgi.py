import os
import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

# Run migrations automatically on startup
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
try:
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        from django.core.management import call_command
        call_command('migrate', '--noinput')
except Exception as e:
    print(f"Migration error: {e}")

application = get_wsgi_application()