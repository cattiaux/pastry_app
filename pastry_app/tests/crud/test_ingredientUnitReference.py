import pytest, json
from django.contrib.auth import get_user_model
from rest_framework import status
from pastry_app.models import IngredientUnitReference, Ingredient
from pastry_app.tests.base_api_test import api_client, base_url, update_object

# Définir model_name pour les tests de ingredientUnitReference
model_name = "ingredient_unit_references"

pytestmark = pytest.mark.django_db

User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user2", password="testpass456")

@pytest.fixture
def guest_id():
    return "test-guest-id-456"

@pytest.fixture
def ingredient():
    return Ingredient.objects.create(ingredient_name=f"jaune d'oeuf")

@pytest.fixture
def setup_reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=100)

def test_create_reference(api_client, base_url, ingredient, user):
    """Test de création d'une référence via l'API."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "unit": "unit", "weight_in_grams": 51}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
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

def test_update_reference(api_client, base_url, setup_reference, ingredient, user):
    """Test de mise à jour d'une référence."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)
    ref_id = setup_reference.id
    data = {"weight_in_grams": 52}
    response = update_object(api_client, url, ref_id, data=json.dumps(data))
    assert response.status_code in (200, 201)
    setup_reference.refresh_from_db()
    # 1. La globale n'a pas changé
    assert setup_reference.weight_in_grams == 100
    # 2. La référence privée existe et a la bonne valeur
    user_private = IngredientUnitReference.objects.get(ingredient=ingredient, unit="unit", user=user)
    assert user_private.weight_in_grams == 52
    # 3. L'API renvoie la nouvelle ref privée
    assert response.data["id"] == user_private.id

def test_delete_reference(api_client, base_url, ingredient, setup_reference, user):
    """Test de suppression d'une référence."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # 1. La globale existe toujours en base
    assert IngredientUnitReference.objects.filter(id=setup_reference.id).exists()

    # 2. Une ref privée 'tombstone' a été créée pour ce user, avec is_hidden=True
    user_hidden = IngredientUnitReference.objects.filter(ingredient=ingredient, unit=setup_reference.unit, user=user, is_hidden=True).first()
    assert user_hidden is not None

    # 3. La ref privée a bien les bonnes valeurs (optionnel, pour auditer)
    assert user_hidden.ingredient == ingredient
    assert user_hidden.unit == setup_reference.unit
    assert user_hidden.is_hidden is True
    assert not setup_reference.is_hidden

    # 4. Pour ce user, le get_queryset métier (filtré sur is_hidden=False) ne renverra PAS la globale
    visible_refs = IngredientUnitReference.objects.filter(ingredient=ingredient, unit=setup_reference.unit, user=user, is_hidden=False)
    assert not visible_refs.exists()

def test_get_nonexistent_reference(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 sur une référence inexistante."""
    url = base_url(model_name) + "9999/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_nonexistent_reference(api_client, base_url, user):
    """Vérifie qu'on obtient une erreur 404 à la suppression d'une référence inexistante."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + "9999/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_anonymous_cannot_delete_reference(api_client, base_url, setup_reference):
    """Vérifie qu'un non-admin ne peut pas supprimer une référence."""
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_user_fork_update(api_client, base_url, ingredient, user, setup_reference):
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_reference.id}/"
    data = {"weight_in_grams": 77}
    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code in (200, 201)
    setup_reference.refresh_from_db()
    assert setup_reference.weight_in_grams == 100
    user_private = IngredientUnitReference.objects.get(ingredient=ingredient, unit="unit", user=user)
    assert user_private.weight_in_grams == 77

def test_guest_fork_update(api_client, base_url, ingredient, guest_id, setup_reference):
    url = base_url(model_name) + f"{setup_reference.id}/"
    data = {"weight_in_grams": 66}
    response = api_client.patch(url, data=json.dumps(data), content_type="application/json", HTTP_X_GUEST_ID=guest_id)
    print(response.json())
    assert response.status_code in (200, 201)
    setup_reference.refresh_from_db()
    assert setup_reference.weight_in_grams == 100
    guest_private = IngredientUnitReference.objects.get(ingredient=ingredient, unit="unit", guest_id=guest_id)
    assert guest_private.weight_in_grams == 66

def test_user_fork_delete(api_client, base_url, ingredient, user, setup_reference):
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    setup_reference.refresh_from_db()
    assert setup_reference.weight_in_grams == 100
    user_private = IngredientUnitReference.objects.filter(ingredient=ingredient, unit="unit", user=user).first()
    assert user_private is not None

def test_guest_fork_delete(api_client, base_url, ingredient, guest_id, setup_reference):
    url = base_url(model_name) + f"{setup_reference.id}/"
    response = api_client.delete(url, HTTP_X_GUEST_ID=guest_id)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    setup_reference.refresh_from_db()
    assert setup_reference.weight_in_grams == 100
    guest_private = IngredientUnitReference.objects.filter(ingredient=ingredient, unit="unit", guest_id=guest_id).first()
    assert guest_private is not None

def test_isolation_between_users(api_client, ingredient, setup_reference, user, guest_id, base_url):
    url = base_url(model_name) + f"{setup_reference.id}/"
    # User update
    api_client.force_authenticate(user=user)
    user_data = {"weight_in_grams": 10}
    api_client.patch(url, data=json.dumps(user_data), content_type="application/json")
    # Guest update
    api_client.force_authenticate(user=None)
    guest_data = {"weight_in_grams": 20}
    api_client.patch(url, data=json.dumps(guest_data), content_type="application/json", HTTP_X_GUEST_ID=guest_id)
    user_private = IngredientUnitReference.objects.filter(ingredient=ingredient, unit="unit", user=user).first()
    guest_private = IngredientUnitReference.objects.filter(ingredient=ingredient, unit="unit", guest_id=guest_id).first()
    assert user_private.weight_in_grams == 10
    assert guest_private.weight_in_grams == 20
    assert setup_reference.weight_in_grams == 100
