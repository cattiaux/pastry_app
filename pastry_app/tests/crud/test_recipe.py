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

# --- Tests API CRUD imbriqués : RecipeStep via /recipes/<id>/steps/ ---

def test_list_nested_steps_api(api_client, base_url, base_recipe_data):
    """ Vérifie qu'on peut lister les étapes via /recipes/<id>/steps/ """
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    url = f"{base_url(model_name)}{recipe['id']}/steps/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1
    assert response.json()[0]["instruction"] == "Préchauffer le four."

def test_create_nested_step_api(api_client, base_url, base_recipe_data):
    """ Vérifie qu'on peut créer une étape via /recipes/<id>/steps/ """
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    url = f"{base_url(model_name)}{recipe['id']}/steps/"
    new_step = {"step_number": 2, "instruction": "Ajouter les pommes."}
    response = api_client.post(url, data=new_step, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["instruction"] == "Ajouter les pommes."

def test_update_nested_step_api(api_client, base_url, base_recipe_data):
    """ Vérifie qu'on peut modifier une étape via /recipes/<id>/steps/<id>/ """
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    step_id = recipe["steps"][0]["id"]
    url = f"{base_url(model_name)}{recipe['id']}/steps/{step_id}/"
    patch = {"instruction": "Préchauffer le four à 180°C."}
    response = api_client.patch(url, data=patch, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["instruction"] == "Préchauffer le four à 180°C."

def test_delete_nested_step_api(api_client, base_url, base_recipe_data):
    """ Vérifie qu'on peut supprimer une étape via /recipes/<id>/steps/<id>/ """
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data

    # Ajout d'une deuxième étape pour autoriser la suppression d'une
    step_create_url = f"{base_url(model_name)}{recipe['id']}/steps/"
    second_step = {"step_number": 2, "instruction": "Ajouter les pommes."}
    api_client.post(step_create_url, data=second_step, format="json")

    step_id = recipe["steps"][0]["id"]
    delete_url = f"{base_url(model_name)}{recipe['id']}/steps/{step_id}/"
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

# --- Tests API CRUD imbriqués : RecipeIngredient via /recipes/<recipe_id>/ingredients/ ---

def test_list_nested_ingredients_api(api_client, base_url, base_recipe_data):
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    url = f"{base_url(model_name)}{recipe['id']}/ingredients/"
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["quantity"] == 300

def test_create_nested_ingredient_api(api_client, base_url, base_recipe_data):
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    url = f"{base_url(model_name)}{recipe['id']}/ingredients/"
    ingredient_id = Ingredient.objects.get(ingredient_name="Pommes").id
    new_ingredient = {"ingredient": ingredient_id, "quantity": 150, "unit": "g"}
    response = api_client.post(url, data=new_ingredient, format="json")
    assert response.status_code == 201
    assert response.data["quantity"] == 150

def test_update_nested_ingredient_api(api_client, base_url, base_recipe_data):
    recipe = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    ing_id = recipe["ingredients"][0]["id"]
    url = f"{base_url(model_name)}{recipe['id']}/ingredients/{ing_id}/"
    patch = {"quantity": 400}
    response = api_client.patch(url, data=patch, format="json")
    assert response.status_code == 200
    assert response.data["quantity"] == 400

def test_delete_nested_ingredient_api(api_client, base_url, base_recipe_data):
    """Vérifie qu’on peut supprimer un ingrédient via /recipes/<id>/ingredients/<id>/"""
    # Crée une recette avec un ingrédient
    recipe = api_client.post(base_url("recipes"), data=base_recipe_data, format="json").data

    # Ajoute un deuxième ingrédient pour autoriser la suppression
    ingredient_payload = {
        "ingredient": base_recipe_data["ingredients"][0]["ingredient"],
        "quantity": 100,
        "unit": "g"
    }
    ing_create_url = f"{base_url('recipes')}{recipe['id']}/ingredients/"
    api_client.post(ing_create_url, data=ingredient_payload, format="json")

    # Supprime le premier ingrédient
    ing_id = recipe["ingredients"][0]["id"]
    ing_delete_url = f"{base_url('recipes')}{recipe['id']}/ingredients/{ing_id}/"
    response = api_client.delete(ing_delete_url)
    assert response.status_code == 204

# --- Tests API CRUD imbriqués : SubRecipe via /recipes/<recipe_id>/sub-recipes/ ---

def test_create_nested_subrecipe_api(api_client, base_url, base_recipe_data):
    recipe_base = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data

    # Crée une recette source qui sera utilisée comme sous-recette
    sub_data = base_recipe_data.copy()
    sub_data["recipe_name"] = "Sous-recette"
    recipe_sub = api_client.post(base_url(model_name), data=sub_data, format="json").data

    url = f"{base_url(model_name)}{recipe_base['id']}/sub-recipes/"
    sub_recipe_payload = {"sub_recipe": recipe_sub["id"], "quantity": 2.0, "unit": "g"}
    response = api_client.post(url, data=sub_recipe_payload, format="json")
    assert response.status_code == 201
    assert response.data["quantity"] == 2.0

def test_update_nested_subrecipe_api(api_client, base_url, base_recipe_data):
    # Création recette et sous-recette
    recipe_base = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    sub_data = base_recipe_data.copy()
    sub_data["recipe_name"] = "Sous-recette"
    recipe_sub = api_client.post(base_url(model_name), data=sub_data, format="json").data

    # Ajout
    url = f"{base_url(model_name)}{recipe_base['id']}/sub-recipes/"
    sub_recipe_payload = {"sub_recipe": recipe_sub["id"], "quantity": 2.0, "unit": "g"}
    sub = api_client.post(url, data=sub_recipe_payload, format="json").data

    # Patch
    patch_url = f"{url}{sub['id']}/"
    response = api_client.patch(patch_url, {"quantity": 3.0})
    print(response.json())
    assert response.status_code == 200
    assert response.data["quantity"] == 3.0

def test_delete_nested_subrecipe_api(api_client, base_url, base_recipe_data):
    recipe_base = api_client.post(base_url(model_name), data=base_recipe_data, format="json").data
    sub_data = base_recipe_data.copy()
    sub_data["recipe_name"] = "Sous-recette"
    recipe_sub = api_client.post(base_url(model_name), data=sub_data, format="json").data

    sub_url = f"{base_url(model_name)}{recipe_base['id']}/sub-recipes/"
    sub = api_client.post(sub_url, {"sub_recipe": recipe_sub["id"], "quantity": 1.0, "unit": "g"}).data

    response = api_client.delete(f"{sub_url}{sub['id']}/")
    assert response.status_code == 204

