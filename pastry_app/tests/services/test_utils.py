import pytest, math
from django.urls import reverse
from rest_framework import status
from pastry_app.utils import adapt_recipe_pan_to_pan, adapt_recipe_servings_to_volume, adapt_recipe_servings_to_servings
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient, RecipeStep
from pastry_app.tests.base_api_test import api_client, base_url
import importlib
import pastry_app.views
importlib.reload(pastry_app.views)

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

@pytest.mark.django_db
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

@pytest.mark.django_db
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

@pytest.mark.django_db
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

### Test d’intégration de l’endpoint POST /recipes/adapt/

@pytest.mark.django_db
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

@pytest.mark.django_db
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

@pytest.mark.django_db
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

@pytest.mark.django_db
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


