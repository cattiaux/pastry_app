import pytest, json
from rest_framework import status
from pastry_app.models import IngredientUnitReference, Ingredient
from pastry_app.tests.base_api_test import api_client, base_url, update_object
from django.contrib.auth.models import User

# Définir model_name pour les tests de ingredientUnitReference
model_name = "ingredient_unit_references"

pytestmark = pytest.mark.django_db

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)  # Authentifie le client API avec l'admin
    return api_client

@pytest.fixture
def ingredient():
    return Ingredient.objects.create(ingredient_name=f"jaune d'oeuf")

@pytest.fixture
def setup_reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50)

def test_create_reference(admin_client, base_url, ingredient):
    """Test de création d'une référence via l'API."""
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 51}
    response = admin_client.post(url, data=json.dumps(data), content_type="application/json")
    print(response.json())
    assert response.status_code == status.HTTP_201_CREATED
    assert IngredientUnitReference.objects.filter(ingredient=ingredient, unit="unit").exists()

def test_get_reference(api_client, base_url, setup_reference):
    """Test de récupération d'une référence."""
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("weight_in_grams") == setup_reference.weight_in_grams

def test_list_references(api_client, base_url, setup_reference):
    """Test que l'API retourne bien la liste des références."""
    url = base_url(model_name)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0

def test_update_reference(admin_client, base_url, setup_reference, ingredient):
    """Test de mise à jour d'une référence."""
    url = base_url(model_name)
    ref_id = setup_reference.id
    data = {"weight_in_grams": 52}
    response = update_object(admin_client, url, ref_id, data=json.dumps(data))
    assert response.status_code in (200, 201)
    setup_reference.refresh_from_db()
    assert setup_reference.weight_in_grams == 52

def test_delete_reference(admin_client, base_url, setup_reference):
    """Test de suppression d'une référence."""
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not IngredientUnitReference.objects.filter(id=setup_reference.id).exists()

def test_get_nonexistent_reference(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 sur une référence inexistante."""
    url = base_url(model_name) + "9999/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_nonexistent_reference(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 à la suppression d'une référence inexistante."""
    url = base_url(model_name) + "9999/"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_non_admin_cannot_delete_reference(api_client, base_url, setup_reference):
    """Vérifie qu'un non-admin ne peut pas supprimer une référence."""
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
