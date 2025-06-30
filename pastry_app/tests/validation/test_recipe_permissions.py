import pytest
from django.contrib.auth import get_user_model
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.models import Recipe, Ingredient
from rest_framework import status
from pastry_app.tests.utils import normalize_case

User = get_user_model()

model_name = "recipes"
pytestmark = pytest.mark.django_db

# Helpers
def base_recipe_data(**overrides):
    """Données minimales valides pour créer une recette (avec au moins un ingrédient)."""
    ingredient = Ingredient.objects.get_or_create(ingredient_name="Pommes")[0]
    data = {
        "recipe_name": "Test Recette",
        "chef_name": "Test Chef",
        "recipe_type": "BASE",
        "servings_min": 2,
        "servings_max": 4,
        "steps": [{"step_number": 1, "instruction": "Test step"}],
        "ingredients": [{"ingredient": ingredient.pk, "quantity": 300, "unit": "g"}],
        "pan_quantity": 1,
        "visibility": "private",
    }
    data.update(overrides)
    return data

@pytest.fixture
def guest_id():
    return "test-guest-id-123"

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def other_user():
    return User.objects.create_user(username="user2", password="testpass456")

# --- TESTS GUEST (invité) ---

def test_guest_can_create_recipe(api_client, base_url, guest_id):
    data = base_recipe_data()
    url = base_url(model_name)
    response = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["guest_id"] == guest_id
    assert response.json()["user"] is None

def test_guest_can_modify_own_recipe(api_client, base_url, guest_id):
    url = base_url(model_name)
    # Création
    response = api_client.post(url, base_recipe_data(), format="json", HTTP_X_GUEST_ID=guest_id)
    recipe_id = response.json()["id"]
    patch_url = f"{url}{recipe_id}/"
    # Modification par le même guest_id
    response2 = api_client.patch(patch_url, {"recipe_name": "Modif Invité"}, format="json", HTTP_X_GUEST_ID=guest_id)
    assert response2.status_code == 200
    assert response2.json()["recipe_name"] == normalize_case("Modif Invité")

def test_guest_cannot_modify_others_recipe(api_client, base_url, guest_id):
    url = base_url(model_name)
    # Création (invité A)
    response = api_client.post(url, base_recipe_data(), format="json", HTTP_X_GUEST_ID=guest_id)
    recipe_id = response.json()["id"]
    patch_url = f"{url}{recipe_id}/"
    # Tentative (invité B)
    response2 = api_client.patch(patch_url, {"recipe_name": "Hack"}, format="json", HTTP_X_GUEST_ID="another-guest-id")
    print(response2.json())
    # En cas de tentative de modification d'une recette appartenant à un autre guest,
    # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
    assert response2.status_code in [403, 404]

def test_guest_can_delete_own_recipe(api_client, base_url, guest_id):
    url = base_url(model_name)
    response = api_client.post(url, base_recipe_data(), format="json", HTTP_X_GUEST_ID=guest_id)
    recipe_id = response.json()["id"]
    del_url = f"{url}{recipe_id}/"
    response2 = api_client.delete(del_url, HTTP_X_GUEST_ID=guest_id)
    assert response2.status_code in [204, 200, 202]

def test_guest_cannot_delete_others_recipe(api_client, base_url, guest_id):
    url = base_url(model_name)
    response = api_client.post(url, base_recipe_data(), format="json", HTTP_X_GUEST_ID=guest_id)
    recipe_id = response.json()["id"]
    del_url = f"{url}{recipe_id}/"
    response2 = api_client.delete(del_url, HTTP_X_GUEST_ID="other-guest")
    # En cas de tentative de modification d'une recette appartenant à un autre guest,
    # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
    assert response2.status_code in [403, 404]

def test_guest_sees_public_and_default_recipes(api_client, base_url, user):
    url = base_url(model_name)
    # Créer une recette publique et une privée via user
    api_client.force_authenticate(user=user)
    api_client.post(url, base_recipe_data(recipe_name="Publique", visibility="public"), format="json")
    api_client.post(url, base_recipe_data(recipe_name="Privée", visibility="private"), format="json")
    # Créer une recette de base (is_default) en direct
    Recipe.objects.create(recipe_name="RecetteBase", chef_name="Chef", recipe_type="BASE", servings_min=2, servings_max=2, 
                          pan_quantity=1, visibility="public", is_default=True)
    api_client.force_authenticate(user=None)
    # L'invité consulte la liste
    response = api_client.get(url)
    names = [r["recipe_name"] for r in response.json()]
    assert normalize_case("Publique") in names
    assert normalize_case("RecetteBase") in names
    assert normalize_case("Privée") not in names

def test_guest_does_not_see_private_user_recipes(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    api_client.post(url, base_recipe_data(recipe_name="PriveeUser", visibility="private"), format="json")
    api_client.force_authenticate(user=None)
    response = api_client.get(url)
    names = [r["recipe_name"] for r in response.json()]
    assert normalize_case("PriveeUser") not in names

# --- TESTS USER AUTH ---

def test_user_can_create_recipe(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    response = api_client.post(url, data, format="json")
    assert response.status_code == 201
    assert response.json()["user"] == user.id
    assert response.json()["guest_id"] is None

def test_user_can_modify_own_recipe(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    recipe_id = api_client.post(url, base_recipe_data(), format="json").json()["id"]
    patch_url = f"{url}{recipe_id}/"
    response = api_client.patch(patch_url, {"recipe_name": "New Name"}, format="json")
    assert response.status_code == 200
    assert response.json()["recipe_name"] == normalize_case("New Name")

def test_user_cannot_modify_others_recipe(api_client, base_url, user, other_user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    recipe_id = api_client.post(url, base_recipe_data(), format="json").json()["id"]
    patch_url = f"{url}{recipe_id}/"
    api_client.force_authenticate(user=other_user)
    response = api_client.patch(patch_url, {"recipe_name": "Hack"}, format="json")
    # En cas de tentative de modification d'une recette appartenant à un autre guest,
    # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
    assert response.status_code in [403, 404]

def test_user_can_delete_own_recipe(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    recipe_id = api_client.post(url, base_recipe_data(), format="json").json()["id"]
    del_url = f"{url}{recipe_id}/"
    response = api_client.delete(del_url)
    assert response.status_code in [204, 200, 202]

def test_user_cannot_delete_others_recipe(api_client, base_url, user, other_user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    recipe_id = api_client.post(url, base_recipe_data(), format="json").json()["id"]
    del_url = f"{url}{recipe_id}/"
    api_client.force_authenticate(user=other_user)
    response = api_client.delete(del_url)
    # En cas de tentative de modification d'une recette appartenant à un autre guest,
    # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
    assert response.status_code in [403, 404]

def test_user_sees_public_and_default_and_own_recipes(api_client, base_url, user, other_user):
    url = base_url(model_name)
    # User crée une publique et une privée
    api_client.force_authenticate(user=user)
    api_client.post(url, base_recipe_data(recipe_name="PubliqueU", visibility="public"), format="json")
    api_client.post(url, base_recipe_data(recipe_name="PriveeU", visibility="private"), format="json")
    # Other user crée une privée
    api_client.force_authenticate(user=other_user)
    api_client.post(url, base_recipe_data(recipe_name="PriveeOther", visibility="private"), format="json")
    # Recette de base
    Recipe.objects.create(recipe_name="DefautU", chef_name="Chef", recipe_type="BASE", servings_min=2, servings_max=2, 
                          pan_quantity=1, visibility="public", is_default=True)
    # User consulte
    api_client.force_authenticate(user=user)
    response = api_client.get(url)
    names = [r["recipe_name"] for r in response.json()]
    assert normalize_case("PubliqueU") in names
    assert normalize_case("PriveeU") in names
    assert normalize_case("DefautU") in names
    assert normalize_case("PriveeOther") not in names

def test_user_does_not_see_private_others_recipes(api_client, base_url, user, other_user):
    url = base_url(model_name)
    api_client.force_authenticate(user=other_user)
    api_client.post(url, base_recipe_data(recipe_name="PriveeOther", visibility="private"), format="json")
    api_client.force_authenticate(user=user)
    response = api_client.get(url)
    names = [r["recipe_name"] for r in response.json()]
    assert normalize_case("PriveeOther") not in names

# --- TESTS RECETTES DE BASE (is_default) ---

@pytest.fixture
def default_recipe(db):
    # Direct en base (admin, script, etc)
    return Recipe.objects.create(
        recipe_name="RecetteBase",
        chef_name="Chef",
        recipe_type="BASE",
        servings_min=2,
        servings_max=2,
        pan_quantity=1,
        visibility="public",
        is_default=True,
    )

def test_default_recipe_is_readonly(api_client, base_url, default_recipe, user):
    url = base_url(model_name) + f"{default_recipe.id}/"
    response = api_client.patch(url, {"recipe_name": "NOPE"})
    assert response.status_code == 403
    api_client.force_authenticate(user=user)
    response2 = api_client.patch(url, {"recipe_name": "NOPE2"})
    assert response2.status_code == 403

def test_default_recipe_is_visible(api_client, base_url, default_recipe):
    url = base_url(model_name)
    response = api_client.get(url)
    assert any(r["recipe_name"] == normalize_case("RecetteBase") for r in response.json())

# --- TESTS VISIBILITY ---

def test_guest_can_create_public_recipe(api_client, base_url, guest_id):
    url = base_url(model_name)
    response = api_client.post(url, base_recipe_data(visibility="public"), format="json", HTTP_X_GUEST_ID=guest_id)
    assert response.status_code == 201
    assert response.json()["visibility"] == "public"

def test_user_can_create_public_recipe(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    response = api_client.post(url, base_recipe_data(visibility="public"), format="json")
    assert response.status_code == 201
    assert response.json()["visibility"] == "public"
