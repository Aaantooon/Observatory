import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, '/home/c/ci666774/myenv/lib/python3.10/site-packages')
sys.path.insert(1, BASE_DIR)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()