import pytest
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import IngredientUnitReference, Ingredient
from django.contrib.auth.models import User

# Définir model_name pour les tests de ingredientUnitReference
model_name = "ingredient_unit_references"
pytestmark = pytest.mark.django_db

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def ingredient():
    return Ingredient.objects.create(ingredient_name="Œuf")

@pytest.fixture
def reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50)

@pytest.mark.parametrize("field_name", ["ingredient", "unit", "weight_in_grams"])
def test_required_fields_reference_api(admin_client, base_url, ingredient, field_name):
    """Vérifie que les champs obligatoires sont requis via l'API."""
    url = base_url(model_name)
    valid_data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 40}
    # Enlève le champ à tester
    valid_data.pop(field_name)
    response = admin_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()

def test_unique_constraint_reference_api(admin_client, base_url, ingredient, reference):
    """Vérifie l'unicité ingrédient+unité via l'API."""
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": reference.unit, "weight_in_grams": 45}
    response = admin_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json() or "ingredient" in response.json()

@pytest.mark.parametrize("weight", [0, -5])
def test_weight_must_be_strictly_positive_api(admin_client, base_url, ingredient, weight):
    """Vérifie que le poids doit être strictement positif (API)."""
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": weight}
    response = admin_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "weight_in_grams" in response.json()

def test_non_admin_cannot_create_reference(api_client, base_url, ingredient):
    """Vérifie qu'un non-admin ne peut pas créer de référence."""
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 50}
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN