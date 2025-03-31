import pytest, math
from django.urls import reverse
from rest_framework import status
from pastry_app.utils import adapt_recipe_pan_to_pan
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient
from pastry_app.tests.base_api_test import api_client, base_url

### fixtures 

@pytest.fixture
def pan(db):
    return Pan.objects.create(pan_name="Cercle 18x4", pan_type="ROUND", diameter=18, height=4, volume_cm3_cache=1000)  # volume simulé pour le test

@pytest.fixture
def target_pan(db):
    return Pan.objects.create(pan_name="Moule carré", pan_type="RECTANGLE", length=20, width=20, rect_height=5, volume_cm3_cache=1500)  # volume simulé

@pytest.fixture
def ingredient(db):
    return Ingredient.objects.create(ingredient_name="Chocolat")

@pytest.fixture
def recipe(db, pan):
    return Recipe.objects.create(recipe_name="Fondant", chef_name="Chef Choco", pan=pan)

@pytest.fixture
def recipe_ingredient(db, recipe, ingredient):
    return RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=200, unit="g")

### Test services 

@pytest.mark.django_db
def test_adapt_recipe_pan_to_pan_creates_correct_multiplier(recipe, target_pan, recipe_ingredient):
    """
    Vérifie que les ingrédients sont bien adaptés avec le bon multiplicateur
    quand on change de moule, et que le volume est bien calculé.
    """
    original_quantity = recipe_ingredient.quantity

    # Calcul manuel des volumes attendus
    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height
    multiplier = target_volume / source_volume
    servings = target_volume / 150

    result = adapt_recipe_pan_to_pan(recipe, target_pan)

    assert abs(result["source_volume"] - source_volume) < 0.1
    assert abs(result["target_volume"] - target_volume) < 0.1
    assert abs(result["multiplier"] - multiplier) < 0.01

    # Intervalle de portions estimé
    assert abs(result["estimated_servings"] - round(servings)) <= 1
    assert result["estimated_servings_min"] < result["estimated_servings"]
    assert result["estimated_servings_max"] > result["estimated_servings"]

    adapted_ingredient = result["ingredients"][0]
    assert adapted_ingredient["original_quantity"] == original_quantity
    assert abs(adapted_ingredient["scaled_quantity"] - round(original_quantity * multiplier, 2)) < 0.1

### Test d’intégration de l’endpoint POST /recipes/adapt/

@pytest.mark.django_db
def test_recipe_adaptation_api_pan_to_pan(api_client, recipe, target_pan, recipe_ingredient):
    """
    Vérifie que l’API retourne les bonnes données lors de l’adaptation d’une recette à un nouveau moule,
    et que les volumes sont cohérents avec les dimensions.
    """
    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "source_pan_id": recipe.pan.id, "target_pan_id": target_pan.id}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height
    multiplier = target_volume / source_volume
    servings = target_volume / 150

    assert abs(data["source_volume"] - source_volume) < 0.1
    assert abs(data["target_volume"] - target_volume) < 0.1
    assert abs(data["multiplier"] - multiplier) < 0.01
    assert abs(data["estimated_servings"] - round(servings)) <= 1
    assert data["estimated_servings_min"] < data["estimated_servings"]
    assert data["estimated_servings_max"] > data["estimated_servings"]
    ingredient = data["ingredients"][0]
    assert ingredient["original_quantity"] == 200
    assert abs(ingredient["scaled_quantity"] - round(200 * multiplier, 2)) < 0.1
    assert ingredient["unit"] == "g"