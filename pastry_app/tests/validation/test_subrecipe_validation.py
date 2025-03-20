import pytest
import json
from rest_framework import status
from pastry_app.models import Recipe, SubRecipe
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import validate_constraint_api

# Définir model_name pour les tests de SubRecipe
model_name = "sub_recipes"

@pytest.fixture
def subrecipe():
    """ Crée une sous-recette d'une recette"""
    recipe1 = Recipe.objects.create(recipe_name="Tarte aux pommes")
    recipe2 = Recipe.objects.create(recipe_name="Crème pâtissière")
    return SubRecipe.objects.create(recipe=recipe1, sub_recipe=recipe2, quantity=200, unit="g")

@pytest.mark.parametrize("field_name", ["recipe", "sub_recipe", "quantity", "unit"])
@pytest.mark.django_db
def test_required_fields_subrecipe_api(api_client, base_url, subrecipe, field_name):
    """ Vérifie que `quantity` et `unit` sont obligatoires via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank."]
    valid_data = {"recipe": subrecipe.recipe.id, "sub_recipe": subrecipe.sub_recipe.id, "quantity": 200, "unit": "g"}
    del valid_data[field_name]  # Supprimer le champ testé
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **valid_data)

@pytest.mark.parametrize("invalid_quantity", [0, -50])
@pytest.mark.django_db
def test_quantity_must_be_positive_api(api_client, base_url, subrecipe, invalid_quantity):
    """ Vérifie que la quantité doit être strictement positive via l'API """
    expected_errors = ["Ensure this value is greater than or equal to 0."]
    valid_data = {"recipe": subrecipe.recipe.id, "sub_recipe": subrecipe.sub_recipe.id, "quantity": invalid_quantity, "unit": "g"}
    validate_constraint_api(api_client, base_url, model_name, "quantity", expected_errors, **valid_data)

@pytest.mark.parametrize("invalid_unit", ["invalid", "XYZ"])
@pytest.mark.django_db
def test_unit_must_be_valid_choice_api(api_client, base_url, subrecipe, invalid_unit):
    """ Vérifie qu'une unité invalide génère une erreur via l'API """
    expected_errors = ["is not a valid choice."]
    valid_data = {"recipe": subrecipe.recipe.id, "sub_recipe": subrecipe.sub_recipe.id, "quantity": 100, "unit": invalid_unit}
    validate_constraint_api(api_client, base_url, model_name, "unit", expected_errors, **valid_data)

@pytest.mark.django_db
def test_cannot_set_recipe_as_its_own_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'une recette ne peut pas être sa propre sous-recette via l'API """
    valid_data = {"recipe": subrecipe.recipe.id, "sub_recipe": subrecipe.recipe.id, "quantity": 100, "unit": "g"}
    response = api_client.post(base_url(model_name), data=json.dumps(valid_data), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "sub_recipe" in response.json()

@pytest.mark.django_db
def test_patch_cannot_set_recipe_as_its_own_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on ne peut pas modifier une sous-recette pour pointer vers elle-même via `PATCH` """
    url = base_url(model_name) + f"{subrecipe.id}/"
    response = api_client.patch(url, data={"sub_recipe": subrecipe.recipe.id}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "sub_recipe" in response.json()

@pytest.mark.django_db
def test_cannot_delete_recipe_used_as_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on ne peut pas supprimer une recette utilisée comme sous-recette via l'API """
    url = base_url("recipes") + f"{subrecipe.sub_recipe.id}/"
    delete_response = api_client.delete(url)
    assert delete_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot delete" in delete_response.json()["error"]

@pytest.mark.django_db
def test_cannot_patch_recipe_field_in_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie que `recipe` est `read_only` et ne peut pas être modifié via `PATCH` """
    url = base_url(model_name) + f"{subrecipe.id}/"
    new_recipe = Recipe.objects.create(recipe_name="Tarte aux pommes 2")
    response = api_client.patch(url, data={"recipe": new_recipe.id}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "recipe" in response.json()