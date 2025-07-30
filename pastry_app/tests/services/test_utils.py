import pytest, math
from django.urls import reverse
from rest_framework import status
from pastry_app.utils import (adapt_recipe_pan_to_pan, adapt_recipe_servings_to_volume, adapt_recipe_servings_to_servings, 
                              estimate_servings_from_pan, suggest_pans_for_servings, adapt_recipe_by_ingredients_constraints)
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient, RecipeStep
from pastry_app.tests.base_api_test import api_client, base_url
import importlib
import pastry_app.views
importlib.reload(pastry_app.views)

pytestmark = pytest.mark.django_db

### fixtures 

@pytest.fixture
def target_pan(db):
    return Pan.objects.create(pan_name="Moule carré", pan_type="RECTANGLE", length=20, width=20, rect_height=5, volume_cm3_cache=1500)  # volume simulé

@pytest.fixture
def recipe(db):
    ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    pan = Pan.objects.create(pan_name="Rond", pan_type="ROUND", diameter=20, height=5)
    recipe = Recipe.objects.create(recipe_name="Fondant", chef_name="Chef Choco", servings_min=4, servings_max=6, pan=pan)
    RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=200, unit="g")
    RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
    return recipe

### Test services 

def test_adapt_recipe_pan_to_pan_creates_correct_multiplier(recipe, target_pan):
    """
    Vérifie que les ingrédients sont bien adaptés avec le bon multiplicateur
    quand on change de moule, et que le volume est bien calculé.
    """
    recipe_ingredient = recipe.recipe_ingredients.first()
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

def test_adapt_recipe_servings_to_volume(recipe):
    """
    Vérifie que la recette est bien adaptée à un nombre de portions cible (volume calculé).
    Et que les moules proposés sont bien compatibles avec ces servings.
    """
    target_servings = 10
    volume_source = recipe.pan.volume_cm3_cache
    volume_target = target_servings * 150
    multiplier = volume_target / volume_source

    result = adapt_recipe_servings_to_volume(recipe, target_servings)

    assert abs(result["source_volume"] - volume_source) < 0.1
    assert abs(result["target_volume"] - volume_target) < 0.1
    assert abs(result["multiplier"] - multiplier) < 0.01
    assert result["estimated_servings"] == target_servings
    assert result["estimated_servings_min"] < target_servings
    assert result["estimated_servings_max"] > target_servings
    # Vérifie que suggested_pans est présent et bien structuré
    assert "suggested_pans" in result
    assert isinstance(result["suggested_pans"], list)

    # Vérifie que tous les moules proposés contiennent le nombre de portions visé
    for pan in result["suggested_pans"]:
        assert pan["servings_min"] <= target_servings <= pan["servings_max"]
        assert volume_target * 0.95 <= pan["volume_cm3_cache"] <= volume_target * 1.05

def test_adapt_recipe_servings_to_servings(recipe):
    """
    Vérifie que la recette est bien adaptée d’un nombre de portions d’origine
    (basé sur servings_min/max) vers un nombre de portions cible.
    Et que les moules proposés sont compatibles avec ces servings.
    """
    recipe.servings_min = 6
    recipe.servings_max = 8
    recipe.pan = None  # On retire le pan pour simuler une recette sans moule
    recipe.save()

    target_servings = 12
    volume_target = target_servings * 150
    volume_source = ((recipe.servings_min + recipe.servings_max) / 2) * 150
    multiplier = volume_target / volume_source

    result = adapt_recipe_servings_to_servings(recipe, target_servings)

    assert abs(result["source_volume"] - volume_source) < 0.1
    assert abs(result["target_volume"] - volume_target) < 0.1
    assert abs(result["multiplier"] - multiplier) < 0.01
    assert result["estimated_servings"] == target_servings
    assert result["source_servings"] == 7  # moyenne de 6 et 8
    assert "suggested_pans" in result  # Vérifie les suggestions de moules
    assert isinstance(result["suggested_pans"], list)

def test_estimate_servings_from_pan(recipe, target_pan):
    """
    Vérifie le calcul d’estimation de servings à partir d’un pan existant
    ou de dimensions fournies.
    """
    # Avec pan existant
    result = estimate_servings_from_pan(pan=target_pan)
    assert "volume_cm3" in result
    assert result["estimated_servings_standard"] > 0
    assert result["estimated_servings_min"] <= result["estimated_servings_standard"]
    assert result["estimated_servings_max"] >= result["estimated_servings_standard"]

    # Avec dimensions ROUND
    result_round = estimate_servings_from_pan(pan_type="ROUND", diameter=20, height=5)
    assert "volume_cm3" in result_round
    assert result_round["estimated_servings_standard"] > 0

    # Avec dimensions RECTANGLE
    result_rect = estimate_servings_from_pan(pan_type="RECTANGLE", length=30, width=20, rect_height=5)
    assert "volume_cm3" in result_rect
    assert result_rect["estimated_servings_standard"] > 0

    # Avec volume brut
    result_raw = estimate_servings_from_pan(pan_type="OTHER", volume_raw=2000)
    assert result_raw["estimated_servings_standard"] == round(2000 / 150)

    # Test des erreurs
    with pytest.raises(ValueError):
        estimate_servings_from_pan()

def test_suggest_pans_for_servings(target_pan):
    """
    Vérifie la suggestion de moules pour un nombre de portions donné.
    """
    result = suggest_pans_for_servings(target_servings=10)

    assert "target_volume_cm3" in result
    assert "suggested_pans" in result
    assert isinstance(result["suggested_pans"], list)

    for pan in result["suggested_pans"]:
        assert "id" in pan
        assert "pan_name" in pan
        assert "volume_cm3_cache" in pan
        assert "estimated_servings_standard" in pan

    # Test avec un nombre élevé
    result_high = suggest_pans_for_servings(target_servings=50)
    assert result_high["target_volume_cm3"] == 50 * 150
    assert isinstance(result_high["suggested_pans"], list)

    # Gestion des erreurs
    with pytest.raises(ValueError):
        suggest_pans_for_servings(target_servings=0)

def test_adapt_recipe_by_ingredients_constraints(recipe):
    """
    Vérifie que la recette est bien adaptée en fonction des quantités disponibles
    pour un ou plusieurs ingrédients.
    """
    ingredient = recipe.recipe_ingredients.first().ingredient
    constraints = {ingredient.id: 100}  # Quantité disponible

    result = adapt_recipe_by_ingredients_constraints(recipe, constraints)

    expected_multiplier = 100 / recipe.recipe_ingredients.first().quantity

    assert result["multiplier"] == expected_multiplier
    assert result["limiting_ingredient_id"] == ingredient.id
    assert abs(result["ingredients"][0]["scaled_quantity"] - 100) < 0.01

### Test d’intégration des endpoints API

#  POST /recipes-adapt/

def test_recipe_adaptation_api_pan_to_pan(api_client, recipe, target_pan):
    """
    Vérifie que l’API adapte correctement une recette d’un moule source vers un moule cible,
    et que les calculs de volume, multiplicateur et portions sont cohérents.
    """
    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height  # Calcul manuel du volume du pan source (rond) : π × r² × h
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height  # Volume du pan cible (rectangle) : L × l × h
    multiplier = target_volume / source_volume  # Multiplicateur attendu pour les quantités
    servings = target_volume / 150  # Portions estimées : volume / 150 ml

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "source_pan_id": recipe.pan.id, "target_pan_id": target_pan.id}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Vérifications mathématiques
    assert abs(data["source_volume"] - source_volume) < 0.1
    assert abs(data["target_volume"] - target_volume) < 0.1
    assert abs(data["multiplier"] - multiplier) < 0.01
    assert abs(data["estimated_servings"] - round(servings)) <= 1
    assert data["estimated_servings_min"] < data["estimated_servings"]
    assert data["estimated_servings_max"] > data["estimated_servings"]

    ingredient = data["ingredients"][0]  # Vérifie que les ingrédients sont bien adaptés
    assert data["recipe_id"] == recipe.id
    assert ingredient["original_quantity"] == 200
    assert abs(ingredient["scaled_quantity"] - round(200 * multiplier, 2)) < 0.1
    assert ingredient["unit"] == "g"

def test_recipe_adaptation_api_servings_to_pan(api_client, recipe, target_pan):
    """
    Vérifie que l’API adapte une recette vers un moule cible
    en se basant sur un nombre de portions initial (Cas 2).
    """
    initial_servings = 6
    volume_source = initial_servings * 150
    volume_target = target_pan.volume_cm3_cache
    multiplier = volume_target / volume_source

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "initial_servings": initial_servings, "target_pan_id": target_pan.id}, format="json")
    assert response.status_code == 200
    data = response.json()

    assert abs(data["source_volume"] - volume_source) < 0.1
    assert abs(data["target_volume"] - volume_target) < 0.1
    assert abs(data["multiplier"] - multiplier) < 0.01

    # Vérifie les servings estimés et la suggestion de pans
    assert "estimated_servings" in data
    assert "suggested_pans" in data
    assert isinstance(data["suggested_pans"], list)
    for pan in data["suggested_pans"]:
        assert volume_target * 0.95 <= pan["volume_cm3_cache"] <= volume_target * 1.05

def test_recipe_adaptation_api_servings_to_volume(api_client, recipe):
    """
    Vérifie que l’API adapte une recette à un nombre de portions cible,
    en se basant sur le moule d’origine, et retourne les moules suggérés.
    """
    target_servings = 10
    volume_target = target_servings * 150
    source_volume = recipe.pan.volume_cm3_cache
    multiplier = volume_target / source_volume

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "source_pan_id": recipe.pan.id, "target_servings": target_servings}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Vérifie les volumes et le multiplicateur
    assert abs(data["source_volume"] - source_volume) < 0.1
    assert abs(data["target_volume"] - volume_target) < 0.1
    assert abs(data["multiplier"] - multiplier) < 0.01
    assert data["estimated_servings"] == target_servings

    # Vérifie que suggested_pans est présent et bien structuré
    assert "suggested_pans" in data
    assert isinstance(data["suggested_pans"], list)

    # Vérifie que les volumes proposés sont proches du volume cible
    for pan in data["suggested_pans"]:
        assert volume_target * 0.95 <= pan["volume_cm3_cache"] <= volume_target * 1.05

def test_recipe_adaptation_api_prioritizes_source_pan(api_client, recipe, target_pan):
    """
    Vérifie que l'API donne la priorité à l'adaptation pan → pan si source_pan_id est fourni,
    même si initial_servings est également présent.
    """
    # Cas où source_pan → target_pan => multiplier très grand
    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height
    multiplier = target_volume / source_volume

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "source_pan_id": recipe.pan.id, "target_pan_id": target_pan.id, 
                                     "initial_servings": 42,  # volontairement incohérent pour vérifier la priorité, doit être ignoré
                                    }, format="json")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # On s’assure que c’est bien une adaptation pan → pan, pas par servings
    assert abs(data["source_volume"] - source_volume) < 0.1
    assert abs(data["target_volume"] - target_volume) < 0.1
    assert abs(data["multiplier"] - multiplier) < 0.01
    assert "estimated_servings" in data
    
    # Vérifie que la suggestion de moules (propre aux servings) n’est pas présente ici
    assert "suggested_pans" not in data
    assert data["source_volume"] != 42 * 150  # Surtout pas le volume basé sur initial_servings * 150

def test_recipe_adaptation_api_servings_to_servings(api_client, recipe):
    """
    Vérifie que l’API adapte une recette basée sur un nombre de portions d’origine
    vers un nombre de portions cible, même sans moule défini.
    """
    recipe.servings_min = 6
    recipe.servings_max = 8
    recipe.pan = None  # On retire le pan pour forcer l’usage des servings comme source
    recipe.save()

    target_servings = 12
    volume_target = target_servings * 150

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "target_servings": target_servings}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Vérifie que les volumes ont été calculés à partir des servings d’origine
    assert data["estimated_servings"] == target_servings
    assert abs(data["target_volume"] - volume_target) < 0.1
    assert data["source_servings"] == 7  # moyenne de 6 et 8
    assert data["source_volume"] == 7 * 150

    # Vérifie la présence des suggestions de moules
    assert "suggested_pans" in data
    for pan in data["suggested_pans"]:
        assert volume_target * 0.95 <= pan["volume_cm3_cache"] <= volume_target * 1.05

#  POST /pan-estimation/

def test_pan_estimation_api(api_client, target_pan):
    """
    Vérifie que l’API d’estimation retourne bien le volume
    et l’intervalle de portions pour un moule existant ou pour des dimensions fournies.
    """
    url = reverse("estimate-pan")

    # Avec pan existant
    response = api_client.post(url, {"pan_id": target_pan.id}, format="json")
    assert response.status_code == 200
    data = response.json()

    assert "volume_cm3" in data
    assert "estimated_servings_standard" in data
    assert "estimated_servings_min" in data
    assert "estimated_servings_max" in data
    assert data["volume_cm3"] == round(target_pan.volume_cm3_cache, 2)

    # Avec dimensions ROUND
    response = api_client.post(url, {"pan_type": "ROUND", "diameter": 24, "height": 5}, format="json")
    assert response.status_code == 200
    data_round = response.json()
    assert data_round["estimated_servings_standard"] > 0

    # Avec dimensions RECTANGLE
    response = api_client.post(url, {"pan_type": "RECTANGLE", "length": 30, "width": 20, "rect_height": 5}, format="json")
    assert response.status_code == 200
    data_rect = response.json()
    assert data_rect["estimated_servings_standard"] > 0

    # Test erreur si aucun input valide
    response = api_client.post(url, {}, format="json")
    assert response.status_code == 400
    assert "error" in response.json() or "non_field_errors" in response.json()

#  POST /pan-suggestion/

def test_pan_suggestion_api(api_client, target_pan):
    """
    Vérifie que l’API suggère des moules pour un nombre de portions donné.
    """
    url = reverse("suggest-pans")

    response = api_client.post(url, {"target_servings": 10}, format="json")
    assert response.status_code == 200
    data = response.json()

    assert "target_volume_cm3" in data
    assert "suggested_pans" in data
    assert isinstance(data["suggested_pans"], list)

    for pan in data["suggested_pans"]:
        assert "id" in pan
        assert "pan_name" in pan
        assert "volume_cm3_cache" in pan
        assert "estimated_servings_standard" in pan

    # Test erreur avec target_servings manquant
    response = api_client.post(url, {}, format="json")
    assert response.status_code == 400
    assert "target_servings" in response.json()

#  POST /recipes-adapt/by-ingredient/

def test_recipe_adaptation_by_ingredient_api(api_client, recipe):
    """
    Vérifie que l’API adapte correctement une recette en fonction
    de la quantité d’un ingrédient donné.
    """
    ingredient = recipe.recipe_ingredients.first().ingredient
    url = reverse("adapt-recipe-by-ingredient")

    response = api_client.post(url, {"recipe_id": recipe.id, "ingredient_constraints": {str(ingredient.id): 100}}, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["recipe_id"] == recipe.id
    assert data["limiting_ingredient_id"] == ingredient.id
    assert data["multiplier"] > 0
    assert data["ingredients"][0]["ingredient_id"] == ingredient.id

