import pytest, math
from django.urls import reverse
from rest_framework import status
from pastry_app.utils_new import *
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient, RecipeStep, SubRecipe
from pastry_app.tests.base_api_test import api_client, base_url
import importlib
import pastry_app.views
importlib.reload(pastry_app.views)

pytestmark = pytest.mark.django_db

### fixtures 

@pytest.fixture
def target_pan(db):
    return Pan.objects.create(pan_name="Moule carré", pan_type="RECTANGLE", length=20, width=20, rect_height=5, volume_cm3_cache=2000) 

@pytest.fixture
def recipe(db):
    ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    pan = Pan.objects.create(pan_name="Rond", pan_type="ROUND", diameter=20, height=5)
    recipe = Recipe.objects.create(recipe_name="Fondant", chef_name="Chef Choco", servings_min=4, servings_max=6, pan=pan)
    RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=200, unit="g")
    RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
    return recipe

### Test services 

def test_scaling_mode_is_correct(recipe, target_pan):
    """
    Vérifie que le champ scaling_mode est correct selon la logique métier.
    """
    # Cas pan d'origine : scaling_mode doit être "pan"
    result = scale_recipe_recursively(recipe, target_pan=target_pan)
    assert result["scaling_mode"] == "pan"

    # Cas sans pan, avec servings : scaling_mode doit être "servings"
    recipe.pan = None
    recipe.servings_min = 8
    recipe.servings_max = 8
    recipe.save()
    result2 = scale_recipe_recursively(recipe, target_pan=target_pan)
    assert result2["scaling_mode"] == "servings"

def test_adapt_recipe_pan_to_pan_creates_correct_multiplier(recipe, target_pan):
    """
    Vérifie que les ingrédients sont bien adaptés avec le bon multiplicateur
    quand on change de moule, et que le scaling est correct.
    """
    recipe_ingredient = recipe.recipe_ingredients.first()
    original_quantity = recipe_ingredient.quantity

    # Calcul manuel des volumes attendus
    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height
    multiplier = target_volume / source_volume
    servings = target_volume / 150

    # result = adapt_recipe_pan_to_pan(recipe, target_pan)
    result = scale_recipe_recursively(recipe, target_pan=target_pan)

    assert abs(result["scaling_multiplier"] - multiplier) < 0.01
    adapted_ingredient = result["ingredients"][0]
    assert abs(adapted_ingredient["quantity"] - round(original_quantity * multiplier, 2)) < 0.1

    # assert abs(result["source_volume"] - source_volume) < 0.1
    # assert abs(result["target_volume"] - target_volume) < 0.1
    # assert abs(result["multiplier"] - multiplier) < 0.01

    # # Intervalle de portions estimé
    # assert abs(result["estimated_servings"] - round(servings)) <= 1
    # assert result["estimated_servings_min"] < result["estimated_servings"]
    # assert result["estimated_servings_max"] > result["estimated_servings"]

    # adapted_ingredient = result["ingredients"][0]
    # assert adapted_ingredient["original_quantity"] == original_quantity
    # assert abs(adapted_ingredient["scaled_quantity"] - round(original_quantity * multiplier, 2)) < 0.1

def test_adapt_recipe_servings_to_volume(recipe):
    """
    Vérifie que la recette est bien adaptée à un nombre de portions cible (volume calculé).
    """
    target_servings = 10
    volume_source = recipe.pan.volume_cm3_cache
    volume_target = target_servings * 150
    multiplier = volume_target / volume_source

    # result = adapt_recipe_servings_to_volume(recipe, target_servings)
    result = scale_recipe_recursively(recipe, target_servings=target_servings)

    assert abs(result["scaling_multiplier"] - multiplier) < 0.01
    # On vérifie les quantités adaptées
    for ing, original in zip(result["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

    # assert abs(result["source_volume"] - volume_source) < 0.1
    # assert abs(result["target_volume"] - volume_target) < 0.1
    # assert abs(result["multiplier"] - multiplier) < 0.01
    # assert result["estimated_servings"] == target_servings
    # assert result["estimated_servings_min"] < target_servings
    # assert result["estimated_servings_max"] > target_servings
    # # Vérifie que suggested_pans est présent et bien structuré
    # assert "suggested_pans" in result
    # assert isinstance(result["suggested_pans"], list)

    # # Vérifie que tous les moules proposés contiennent le nombre de portions visé
    # for pan in result["suggested_pans"]:
    #     assert pan["servings_min"] <= target_servings <= pan["servings_max"]
    #     assert volume_target * 0.95 <= pan["volume_cm3_cache"] <= volume_target * 1.05

def test_adapt_recipe_servings_to_servings(recipe):
    """
    Vérifie que la recette est bien adaptée d’un nombre de portions d’origine
    (basé sur servings_min/max) vers un nombre de portions cible.
    """
    recipe.servings_min = 6
    recipe.servings_max = 8
    recipe.pan = None  # On retire le pan pour simuler une recette sans moule
    recipe.save()

    target_servings = 12
    volume_target = target_servings * 150
    volume_source = ((recipe.servings_min + recipe.servings_max) / 2) * 150
    multiplier = volume_target / volume_source

    # result = adapt_recipe_servings_to_servings(recipe, target_servings)
    result = scale_recipe_recursively(recipe, target_servings=target_servings)

    assert abs(result["scaling_multiplier"] - multiplier) < 0.01
    for ing, original in zip(result["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

    # assert abs(result["source_volume"] - volume_source) < 0.1
    # assert abs(result["target_volume"] - volume_target) < 0.1
    # assert abs(result["multiplier"] - multiplier) < 0.01
    # assert result["estimated_servings"] == target_servings
    # assert result["source_servings"] == 7  # moyenne de 6 et 8
    # assert "suggested_pans" in result  # Vérifie les suggestions de moules
    # assert isinstance(result["suggested_pans"], list)

def test_estimate_servings_from_pan(target_pan):
    """
    Vérifie le calcul d’estimation de servings à partir d’un pan existant
    """
    # Avec pan existant
    # result = estimate_servings_from_pan(pan=target_pan)
    result = estimate_servings_from_pan(target_pan)
    assert "volume_cm3" in result
    assert result["estimated_servings_standard"] > 0
    assert result["estimated_servings_min"] <= result["estimated_servings_standard"]
    assert result["estimated_servings_max"] >= result["estimated_servings_standard"]

    # # Avec dimensions ROUND
    # result_round = estimate_servings_from_pan(pan_type="ROUND", diameter=20, height=5)
    # assert "volume_cm3" in result_round
    # assert result_round["estimated_servings_standard"] > 0

    # # Avec dimensions RECTANGLE
    # result_rect = estimate_servings_from_pan(pan_type="RECTANGLE", length=30, width=20, rect_height=5)
    # assert "volume_cm3" in result_rect
    # assert result_rect["estimated_servings_standard"] > 0

    # # Avec volume brut
    # result_raw = estimate_servings_from_pan(pan_type="OTHER", volume_raw=2000)
    # assert result_raw["estimated_servings_standard"] == round(2000 / 150)

    # Test des erreurs
    with pytest.raises(ValueError):
        estimate_servings_from_pan(None)

def test_suggest_pans_for_servings():
    """
    Vérifie la suggestion de moules pour un nombre de portions donné.
    """
    result = suggest_pans_for_servings(target_servings=10)

    assert isinstance(result, list)
    for pan in result:
        assert "id" in pan
        assert "pan_name" in pan
        assert "volume_cm3_cache" in pan
        assert "estimated_servings_standard" in pan

    # assert "target_volume_cm3" in result
    # assert "suggested_pans" in result
    # assert isinstance(result["suggested_pans"], list)

    # for pan in result["suggested_pans"]:
    #     assert "id" in pan
    #     assert "pan_name" in pan
    #     assert "volume_cm3_cache" in pan
    #     assert "estimated_servings_standard" in pan

    # Test avec un nombre élevé
    result_high = suggest_pans_for_servings(target_servings=50)
    # assert result_high["target_volume_cm3"] == 50 * 150
    assert isinstance(result_high, list)
    assert all("id" in pan for pan in result_high)

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

def test_scaling_prioritizes_pan_when_servings_are_incoherent(recipe, target_pan):
    """
    Vérifie que la priorité est bien donnée au pan d'origine même si les servings sont incohérents.
    """
    # On donne un pan d'origine petit mais des servings incohérents
    recipe.servings_min = 100
    recipe.servings_max = 100
    recipe.save()
    # Le scaling doit utiliser le volume pan (pas servings)
    result = scale_recipe_recursively(recipe, target_pan=target_pan)
    assert result["scaling_mode"] == "pan"
    # On vérifie que le scaling_multiplier correspond bien à la formule basée sur les volumes des pans
    volume_source = recipe.pan.volume_cm3_cache
    volume_target = target_pan.volume_cm3_cache
    expected_multiplier = volume_target / volume_source
    assert abs(result["scaling_multiplier"] - expected_multiplier) < 0.01

def test_recursive_scaling_on_subrecipes(db):
    """
    Vérifie que le scaling récursif adapte bien tous les ingrédients, y compris dans les sous-recettes imbriquées.
    """
    # Création d'une sous-sous-recette
    ingr_sub_sub = Ingredient.objects.create(ingredient_name="Sucre glace")
    sub_sub_recipe = Recipe.objects.create(recipe_name="Crème", chef_name="Chef Choco", servings_min=2, servings_max=2)
    sub_sub_ingredient = RecipeIngredient.objects.create(recipe=sub_sub_recipe, ingredient=ingr_sub_sub, quantity=50, unit="g")

    # Création d'une sous-recette qui inclut la sous-sous-recette
    ingr_sub = Ingredient.objects.create(ingredient_name="Farine")
    sub_recipe = Recipe.objects.create(recipe_name="Garniture", chef_name="Chef Choco", servings_min=2, servings_max=2)
    sub_ingredient = RecipeIngredient.objects.create(recipe=sub_recipe, ingredient=ingr_sub, quantity=30, unit="g")
    SubRecipe.objects.create(recipe=sub_recipe, sub_recipe=sub_sub_recipe, quantity=123, unit="g")

    # Recette principale qui inclut la sous-recette
    main_ingr = Ingredient.objects.create(ingredient_name="Oeuf")
    main_recipe = Recipe.objects.create(recipe_name="Tarte", chef_name="Chef Choco", servings_min=2, servings_max=2)
    main_ingredient = RecipeIngredient.objects.create(recipe=main_recipe, ingredient=main_ingr, quantity=2, unit="unit")
    SubRecipe.objects.create(recipe=main_recipe, sub_recipe=sub_recipe, quantity=456, unit="g")

    # Adapter la recette pour 4 portions
    data = scale_recipe_recursively(main_recipe, target_servings=4)
    assert data["scaling_multiplier"] == 2.0

    # Vérifie tous les niveaux de sous-recettes et ingrédients
    assert len(data["subrecipes"]) == 1
    sub = data["subrecipes"][0]
    assert len(sub["ingredients"]) == 1
    assert abs(sub["ingredients"][0]["quantity"] - 60) < 0.01
    assert len(sub["subrecipes"]) == 1
    subsub = sub["subrecipes"][0]
    assert abs(subsub["ingredients"][0]["quantity"] - 100) < 0.01

### Test d’intégration des endpoints API

#  POST /recipes-adapt/

def test_recipe_adaptation_api_pan_to_pan(api_client, recipe, target_pan):
    """
    Vérifie que l’API adapte correctement une recette d’un moule source vers un moule cible,
    """
    source_volume = math.pi * (recipe.pan.diameter / 2) ** 2 * recipe.pan.height  # Calcul manuel du volume du pan source (rond) : π × r² × h
    target_volume = target_pan.length * target_pan.width * target_pan.rect_height  # Volume du pan cible (rectangle) : L × l × h
    multiplier = target_volume / source_volume  # Multiplicateur attendu pour les quantités

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "source_pan_id": recipe.pan.id, "target_pan_id": target_pan.id}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Structure générale
    assert "recipe_id" in data and data["recipe_id"] == recipe.id
    assert "scaling_multiplier" in data
    assert "ingredients" in data and isinstance(data["ingredients"], list)
    assert "subrecipes" in data and isinstance(data["subrecipes"], list)

    # Vérifie le scaling
    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    assert len(data["ingredients"]) == recipe.recipe_ingredients.count()

    for i, original in enumerate(recipe.recipe_ingredients.all()):
        ing = data["ingredients"][i]
        assert "ingredient_id" in ing and ing["ingredient_id"] == original.ingredient.id
        assert "ingredient_name" in ing and ing["ingredient_name"] == original.ingredient.ingredient_name
        assert "quantity" in ing and abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1
        assert "unit" in ing and ing["unit"] == original.unit

    # Vérifie que les sous-recettes sont adaptées récursivement (si présentes)
    for sub in data["subrecipes"]:
        assert "sub_recipe_id" in sub
        assert "ingredients" in sub and isinstance(sub["ingredients"], list)
        # Pour chaque ingrédient de sous-recette
        for ing in sub["ingredients"]:
            assert "quantity" in ing and ing["quantity"] >= 0

    # Aucune modification en base (vérifie que l’original n’a pas bougé)
    for original, db_ri in zip(recipe.recipe_ingredients.all(), recipe.recipe_ingredients.all()):
        assert db_ri.quantity == original.quantity

def test_recipe_adaptation_api_servings_to_pan(api_client, recipe, target_pan):
    """
    Vérifie que l’API adapte une recette vers un moule cible
    en se basant sur le nombre de portions renseigné sur la recette (servings_min/max).
    """
    servings = 6
    recipe.pan = None  # On retire le pan pour forcer l’usage des servings comme source
    recipe.servings_min = servings
    recipe.servings_max = servings
    recipe.save()

    volume_source = servings * 150
    volume_target = target_pan.volume_cm3_cache
    multiplier = volume_target / volume_source

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "target_pan_id": target_pan.id}, format="json")
    assert response.status_code == 200
    data = response.json()

    assert "scaling_multiplier" in data
    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    assert len(data["ingredients"]) == recipe.recipe_ingredients.count()

    for i, original in enumerate(recipe.recipe_ingredients.all()):
        ing = data["ingredients"][i]
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

    # Structure des sous-recettes
    for sub in data["subrecipes"]:
        assert isinstance(sub["ingredients"], list)

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

    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    assert "ingredients" in data and len(data["ingredients"]) == recipe.recipe_ingredients.count()
    for ing, original in zip(data["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

    # Check possible keys for clarity
    assert "subrecipes" in data
    for sub in data["subrecipes"]:
        assert "ingredients" in sub and isinstance(sub["ingredients"], list)

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

    assert "suggested_pans" not in data  # Doit être absent en adaptation pan→pan
    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    for i, original in enumerate(recipe.recipe_ingredients.all()):
        ing = data["ingredients"][i]
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

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
    volume_source = 7 * 150  # moyenne de 6 et 8
    multiplier = volume_target / volume_source

    url = reverse("adapt-recipe")
    response = api_client.post(url, {"recipe_id": recipe.id, "target_servings": target_servings}, format="json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    assert "ingredients" in data and len(data["ingredients"]) == recipe.recipe_ingredients.count()
    for ing, original in zip(data["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

    # # Si on expose source_servings alors on peut vérifier
    # assert "source_servings" in data
    # assert data["source_servings"] == 7  # moyenne de 6 et 8
    # assert "source_volume" in data
    # assert data["source_volume"] == 7 * 150

    # Sous-recettes
    for sub in data["subrecipes"]:
        assert "ingredients" in sub and isinstance(sub["ingredients"], list)

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
    round_pan = Pan.objects.create(pan_name="Moule rond", pan_type="ROUND", diameter=24, height=5) 
    response = api_client.post(url, {"pan_id":round_pan.id}, format="json")
    print(response.json())
    assert response.status_code == 200
    data_round = response.json()
    assert data_round["estimated_servings_standard"] > 0

    # Avec dimensions RECTANGLE
    response = api_client.post(url, {"pan_id": target_pan.id}, format="json")
    assert response.status_code == 200
    data_rect = response.json()
    assert data_rect["estimated_servings_standard"] > 0

    # Test erreur si aucun input valide
    response = api_client.post(url, {}, format="json")
    assert response.status_code == 400
    assert "error" in response.json() or "non_field_errors" in response.json()

#  POST /pan-suggestion/

def test_pan_suggestion_api(api_client):
    """
    Vérifie que l’API suggère des moules pour un nombre de portions donné.
    """
    url = reverse("suggest-pans")

    # Création d'un pan pour le test, vérifier qu'il soit suggéré
    pan = Pan.objects.create(pan_name="Test Pan", pan_type="ROUND", diameter=20, height=5, volume_cm3_cache=1550)
    
    response = api_client.post(url, {"target_servings": 10}, format="json")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)  # On attend une liste de pans
    assert len(data) > 0

    for pan in data:
        assert "id" in pan
        assert "pan_name" in pan
        assert "volume_cm3_cache" in pan
        assert "estimated_servings_standard" in pan
        assert abs(pan["estimated_servings_standard"] - 10) <= 2

    # Test erreur avec target_servings manquant
    response = api_client.post(url, {}, format="json")
    assert response.status_code == 400
    assert "target_servings" in response.json() or "error" in response.json()

#  POST /recipes-adapt/by-ingredient/

def test_recipe_adaptation_by_ingredient_api(api_client, recipe):
    """
    Vérifie que l’API adapte correctement une recette en fonction de la quantité d’un ingrédient donné.
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

