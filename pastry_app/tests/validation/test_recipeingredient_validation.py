import pytest, json
from rest_framework import status
from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *

# Définir model_name pour les tests de RecipeIngredient
model_name = "recipe_ingredients"
pytestmark = pytest.mark.django_db

@pytest.fixture
def recipe(db):
    """ Crée une recette de test """
    return Recipe.objects.create(recipe_name="Tarte aux pommes", chef_name="Martin")

@pytest.fixture
def ingredient(db):
    """ Crée un ingrédient de test """
    return Ingredient.objects.create(ingredient_name="Sucre")

@pytest.fixture()
def recipe_ingredient(recipe, ingredient):
    """ Crée une recette et un ingrédient pour les tests """
    return RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=100.0, unit="g")

@pytest.mark.parametrize("field_name", ["quantity", "unit"])
def test_required_fields_recipeingredient_api(api_client, base_url, recipe, ingredient, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null."]
    valid_data = {"recipe": recipe.id, "ingredient": ingredient.id, "quantity": 100, "unit": "g"}
    del valid_data[field_name]  # Supprimer le champ à tester
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **valid_data)

@pytest.mark.parametrize("invalid_quantity", [0, -50])
def test_quantity_must_be_positive_api(api_client, base_url, recipe, ingredient, invalid_quantity):
    """ Vérifie que la quantité doit être strictement positive via l'API """
    expected_errors = ["Ensure this value is greater than or equal to 0.","Quantity must be a positive number."]
    valid_data = {"recipe": recipe.id, "ingredient": ingredient.id, "quantity": invalid_quantity, "unit": "g"}
    validate_constraint_api(api_client, base_url, model_name, "quantity", expected_errors, **valid_data)

@pytest.mark.parametrize("invalid_unit", ["invalid", "XYZ"])
def test_unit_must_be_valid_choice_api(api_client, base_url, recipe, ingredient, invalid_unit):
    """ Vérifie qu'une unité invalide génère une erreur via l'API """
    expected_errors = ["is not a valid choice."]
    valid_data = {"recipe": recipe.id, "ingredient": ingredient.id, "quantity": 100, "unit": invalid_unit}
    validate_constraint_api(api_client, base_url, model_name, "unit", expected_errors, **valid_data)

def test_suffix_increment_on_duplicate_ingredient(api_client, base_url, recipe_ingredient):
    """ Vérifie que l'API ajoute bien un suffixe incrémental si un ingrédient est ajouté plusieurs fois """
    url = base_url(model_name)

    # Création du deuxième "Sucre" → Doit avoir "Sucre 2"
    response2 = api_client.post(url, data=json.dumps({"recipe": recipe_ingredient.recipe.id, "ingredient": recipe_ingredient.ingredient.id, 
                                                      "quantity": 50, "unit": "g"}), content_type="application/json")
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["display_name"] == "sucre 2"

    # Création du troisième "Sucre" → Doit avoir "Sucre 3"
    response3 = api_client.post(url, data={"recipe": recipe_ingredient.recipe.id, "ingredient": recipe_ingredient.ingredient.id, 
                                           "quantity": 30, "unit": "g"}, format="json")
    assert response3.status_code == status.HTTP_201_CREATED
    assert response3.json()["display_name"] == "sucre 3"

def test_suffix_increment_and_reassignment_on_deletion_api(api_client, base_url, recipe_ingredient):
    """ Vérifie que la suppression d'un `RecipeIngredient` réattribue bien les suffixes """
    url = base_url(model_name)

    # Création de 2 "Sucre" supplémentaires avec suffixes
    response2 = api_client.post(url, data={"recipe": recipe_ingredient.recipe.id, "ingredient": recipe_ingredient.ingredient.id, 
                                           "quantity": 50, "unit": "g"}, format="json")
    assert response2.status_code == status.HTTP_201_CREATED
    id2 = response2.json()["id"]

    response3 = api_client.post(url, data={"recipe": recipe_ingredient.recipe.id, "ingredient": recipe_ingredient.ingredient.id, 
                                           "quantity": 30, "unit": "g"}, format="json")
    assert response3.status_code == status.HTTP_201_CREATED
    id3 = response3.json()["id"]

    # Vérifier les suffixes initiaux
    assert response2.json()["display_name"] == "sucre 2"
    assert response3.json()["display_name"] == "sucre 3"

    # Suppression de "Sucre 2"
    delete_response = api_client.delete(url + f"{id2}/")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Vérification que "Sucre 3" est devenu "Sucre 2"
    response_get_3 = api_client.get(url + f"{id3}/")
    assert response_get_3.status_code == status.HTTP_200_OK
    assert response_get_3.json()["display_name"] == "sucre 2"

def test_cannot_delete_last_recipeingredient_api(api_client, base_url, recipe_ingredient):
    """ Vérifie qu'on ne peut pas supprimer le dernier `RecipeIngredient` d'une recette """
    url = base_url(model_name)
    ingredient_id = recipe_ingredient.id  # Récupération de l'id du seul ingrédient de la recette
    delete_response = api_client.delete(url + f"{ingredient_id}/")  # Tentative de suppression du dernier ingrédient
    assert delete_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Une recette doit contenir au moins un ingrédient ou une sous-recette." in delete_response.json()["error"]
