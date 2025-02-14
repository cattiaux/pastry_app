import os
import django
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))  # Ajoute le projet au PYTHONPATH

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "enchante.settings")  # Vérifie que "enchante" est correct
django.setup()
