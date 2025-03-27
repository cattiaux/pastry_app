import pytest, json
from rest_framework import status
from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from pastry_app.tests.base_api_test import api_client, base_url, update_object
from pastry_app.tests.utils import *

# Définir model_name pour les tests de RecipeIngredient
model_name = "recipe_ingredients"

@pytest.fixture
def recipe(db):
    """ Crée une recette de test """
    return Recipe.objects.create(recipe_name="Tarte aux pommes", chef_name="Martin")

@pytest.fixture
def ingredient(db):
    """ Crée un ingrédient de test """
    return Ingredient.objects.create(ingredient_name="Sucre")

@pytest.fixture
def recipe_ingredient(db, recipe, ingredient):
    """ Crée un `RecipeIngredient` de test """
    return RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=100, unit="g")

@pytest.mark.django_db
def test_create_recipeingredient_api(api_client, base_url, recipe, ingredient):
    """ Vérifie qu'on peut créer un `RecipeIngredient` via l'API """
    valid_data = {"recipe": recipe.id, "ingredient": ingredient.id, "quantity": 200, "unit": "g"}
    response = api_client.post(base_url(model_name), data=json.dumps(valid_data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["recipe"] == recipe.id
    assert response.json()["ingredient"] == ingredient.id
    assert response.json()["quantity"] == 200
    assert response.json()["unit"] == "g"

@pytest.mark.django_db
def test_get_recipeingredient_api(api_client, base_url, recipe_ingredient):
    """ Vérifie qu'on peut récupérer un `RecipeIngredient` via l'API """
    response = api_client.get(base_url(model_name) + f"{recipe_ingredient.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == recipe_ingredient.id
    assert response.json()["recipe"] == recipe_ingredient.recipe.id
    assert response.json()["ingredient"] == recipe_ingredient.ingredient.id

@pytest.mark.django_db
def test_list_recipeingredient_api(api_client, base_url, recipe_ingredient):
    """ Vérifie qu'on peut récupérer la liste des `RecipeIngredient`. """
    ingredient2 = Ingredient.objects.create(ingredient_name="Farine")  # Création d'un 2ème ingrédient
    RecipeIngredient.objects.create(recipe=recipe_ingredient.recipe, ingredient=ingredient2, quantity=400, unit="g")  # Ajout d'un nouvel ingrédient
    url = base_url(model_name) + f"{recipe_ingredient.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 1  # Vérifie qu'on récupère bien des données

@pytest.mark.django_db
def test_partial_update_recipeingredient_api(api_client, base_url, recipe_ingredient):
    """ Vérifie qu'on peut modifier un `RecipeIngredient` via l'API """
    url = base_url(model_name) + f"{recipe_ingredient.id}/"
    update_data = {"quantity": 500, "unit": "kg"}
    response = api_client.patch(url, data=update_data, format="json")
    # response = update_object(api_client, base_url, recipe_ingredient.id, update_data)
    print(response.json())
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["quantity"] == 500
    assert response.json()["unit"] == "kg"


@pytest.mark.django_db
def test_delete_recipeingredient_api(api_client, base_url, recipe_ingredient):
    """ Vérifie qu'on peut supprimer un `RecipeIngredient` via l'API si d'autres ingrédients existent """
    url = base_url(model_name) + f"{recipe_ingredient.id}/"
    # Création d'un 2ème ingrédient pour éviter l'erreur de suppression du dernier élément
    ingredient2 = Ingredient.objects.create(ingredient_name="Farine")
    RecipeIngredient.objects.create(recipe=recipe_ingredient.recipe, ingredient=ingredient2, quantity=200, unit="kg")
    response = api_client.delete(url)  # delete du premier ingrédient
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not RecipeIngredient.objects.filter(id=recipe_ingredient.id).exists()  # Vérifier que l'ingrédient a bien été supprimé

@pytest.mark.django_db
def test_delete_nonexistent_recipeingredient_api(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une RecipeIngredient qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_get_nonexistent_recipeingredient_api(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une RecipeIngredient qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND
