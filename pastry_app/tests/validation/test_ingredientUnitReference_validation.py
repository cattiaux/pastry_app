import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import IngredientUnitReference, Ingredient
from django.contrib.auth.models import User

# Définir model_name pour les tests de ingredientUnitReference
model_name = "ingredient_unit_references"

pytestmark = pytest.mark.django_db

User = get_user_model()

@pytest.fixture
def guest_id():
    return "test-guest-id-123"

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def ingredient():
    obj = Ingredient.objects.create(ingredient_name="blanC d'œuf")
    # obj.full_clean() # pas nécessaire car full_clean est appelé dans le save()
    obj.save()
    return obj

@pytest.fixture
def reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50)

@pytest.mark.parametrize("field_name", ["ingredient", "unit", "weight_in_grams"])
def test_required_fields_reference_api(api_client, base_url, ingredient, field_name, user):
    """Vérifie que les champs obligatoires sont requis via l'API."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    valid_data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 40}
    # Enlève le champ à tester
    valid_data.pop(field_name)
    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()

def test_unique_constraint_reference_api(api_client, base_url, ingredient, reference, user):
    """Vérifie l'unicité ingrédient+unité via l'API."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": reference.unit, "weight_in_grams": 45}
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json() or "ingredient" in response.json()

@pytest.mark.parametrize("weight", [0, -5])
def test_weight_must_be_strictly_positive_api(api_client, base_url, ingredient, weight, user):
    """Vérifie que le poids doit être strictement positif (API)."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": weight}
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "weight_in_grams" in response.json()

### NO MORE VALID
# def test_non_admin_cannot_create_reference(api_client, base_url, ingredient):
#     """Vérifie qu'un non-admin ne peut pas créer de référence."""
#     url = base_url(model_name)
#     data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 50}
#     response = api_client.post(url, data, format="json")
#     assert response.status_code == status.HTTP_403_FORBIDDEN

def test_guest_can_create_reference(api_client, base_url, guest_id, ingredient):
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 42}
    response = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
    assert response.status_code == status.HTTP_201_CREATED
    ref = IngredientUnitReference.objects.get(id=response.data['id'])
    assert ref.guest_id == guest_id
    assert ref.user is None

def test_user_can_create_reference(api_client, base_url, ingredient, user):
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 43}
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    ref = IngredientUnitReference.objects.get(id=response.data['id'])
    assert ref.user == user
    assert ref.guest_id is None

def test_user_and_guest_can_have_same_ref(api_client, base_url, ingredient, user, guest_id):
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 10}
    # Création user
    api_client.force_authenticate(user=user)
    resp_user = api_client.post(url, data, format="json")
    # Création guest
    api_client.force_authenticate(user=None)
    resp_guest = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
    assert resp_user.status_code == status.HTTP_201_CREATED
    assert resp_guest.status_code == status.HTTP_201_CREATED
    assert resp_user.data["id"] != resp_guest.data["id"]

def test_user_cannot_duplicate_ref(api_client, base_url, ingredient, user):
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 22}
    api_client.post(url, data, format="json")
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_guest_cannot_duplicate_ref(api_client, base_url, ingredient, guest_id):
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 22}
    resp1 = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
    assert resp1.status_code == 201
    resp2 = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST

