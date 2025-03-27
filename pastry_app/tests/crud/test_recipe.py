import pytest, copy
from rest_framework import status
from pastry_app.models import Recipe, Ingredient, SubRecipe
from pastry_app.tests.base_api_test import api_client, base_url

model_name = "recipes"
pytestmark = pytest.mark.django_db

@pytest.fixture
def base_recipe_data():
    """Retourne un dictionnaire de données valides pour une recette."""
    ingredient = Ingredient.objects.get_or_create(ingredient_name="Pommes")[0]
    return {
        "recipe_name": "Tarte Normande",
        "chef_name": "Chef Normand",
        "recipe_type": "BASE",
        "servings_min": 6,
        "servings_max": 6,
        "steps": [{"step_number": 1, "instruction": "Préchauffer le four."}],
        "ingredients": [{"ingredient": ingredient.pk, "quantity": 300, "unit": "g"}],
        "pan_quantity": 1,
    }

def test_create_recipe_api(api_client, base_url, base_recipe_data):
    response = api_client.post(base_url(model_name), data=base_recipe_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["recipe_name"] == "tarte normande"

def test_get_recipe_detail_api(api_client, base_url, base_recipe_data):
    recipe_id = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data["id"]
    response = api_client.get(f"{base_url(model_name)}{recipe_id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == recipe_id

def test_list_recipes_api(api_client, base_url, base_recipe_data):
    api_client.post(base_url(model_name), data=base_recipe_data, format="json")
    base_recipe_data["recipe_name"] = "Tarte aux pommes"
    api_client.post(base_url(model_name), data=base_recipe_data, format="json")
    response = api_client.get(base_url(model_name))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) >= 2

def test_patch_update_recipe_api(api_client, base_url, base_recipe_data):
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    update = {"description": "Version revisitée"}
    response = api_client.patch(f"{base_url(model_name)}{recipe['id']}/", data=update, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["description"] == "Version revisitée"

def test_put_update_recipe_api(api_client, base_url, base_recipe_data):
    recipe_id = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data["id"]
    base_recipe_data["recipe_name"] = "Nouvelle Tarte"
    response = api_client.put(f"{base_url(model_name)}{recipe_id}/", data=base_recipe_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["recipe_name"] == "nouvelle tarte"

def test_delete_recipe_api(api_client, base_url, base_recipe_data):
    recipe_id = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data["id"]
    response = api_client.delete(f"{base_url(model_name)}{recipe_id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Recipe.objects.filter(id=recipe_id).exists()

def test_delete_recipe_used_as_subrecipe(api_client, base_url, base_recipe_data):
    # Crée recette A
    data_a = copy.deepcopy(base_recipe_data)
    data_a["recipe_name"] = "Sous-recette"
    recipe_a = api_client.post(base_url(model_name), data=data_a, format="json").data

    # Crée recette B qui utilise A comme sous-recette
    data_b = copy.deepcopy(base_recipe_data)
    data_b["recipe_name"] = "Tarte en deux parties"
    data_b["sub_recipes"] = [{"sub_recipe": recipe_a["id"], "quantity": 1.0, "unit": "g"}]
    response_b = api_client.post(base_url(model_name), data=data_b, format="json")
    assert response_b.status_code == 201  # vérifie que la sous-recette est bien liée

    # Tente de supprimer A
    response = api_client.delete(base_url(model_name) + f"{recipe_a['id']}/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "used in another recipe" in str(response.data).lower()

def test_get_nonexistent_recipe(api_client, base_url):
    response = api_client.get(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_nonexistent_recipe(api_client, base_url):
    response = api_client.delete(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND