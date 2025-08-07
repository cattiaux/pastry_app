import pytest, math
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from pastry_app.utils_new import *
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient, RecipeStep, SubRecipe, Category
from pastry_app.tests.base_api_test import api_client, base_url
import importlib
from pastry_app.views import *
import pastry_app.views
importlib.reload(pastry_app.views)

pytestmark = pytest.mark.django_db

### fixtures 

User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def target_pan(db):
    return Pan.objects.create(pan_name="Moule carré", pan_type="RECTANGLE", length=20, width=20, rect_height=5, volume_cm3_cache=2000) 

@pytest.fixture
def recipe(db):
    ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    pan = Pan.objects.create(pan_name="Rond", pan_type="ROUND", diameter=20, height=5)
    recipe = Recipe.objects.create(recipe_name="Fondant", chef_name="Chef Choco", servings_min=4, servings_max=6, pan=pan, total_recipe_quantity=600, visibility="public")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=200, unit="g")
    RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
    return recipe

@pytest.fixture
def reference_recipe(db):
    """ Recette de référence pour tester le scaling par poids. """
    ingredient = Ingredient.objects.create(ingredient_name="Noisette")
    pan = Pan.objects.create(pan_name="Rond_15", pan_type="ROUND", diameter=15, height=4)
    recipe = Recipe.objects.create(recipe_name="Crème Noisette", chef_name="Chef Noisette", pan=pan, total_recipe_quantity=1200, visibility="public")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=200, unit="g")
    RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
    return recipe

### Test services 

@pytest.mark.parametrize(
    "has_pan, has_servings, use_reference, expect_mode, should_raise_error",
    [
        (True, False, False, "pan", False),
        (False, True, False, "servings", False),
        (False, False, True, "reference_recipe", False),
        (False, False, False, None, True),
    ]
)
def test_scaling_mode_and_multiplier(recipe, target_pan, reference_recipe, has_pan, has_servings, use_reference, expect_mode, should_raise_error):
    """
    Vérifie la priorité d'adaptation : pan > servings > recette de référence.
    - Si pan renseigné, priorité pan.
    - Si pas de pan mais servings, priorité servings.
    - Si rien d'autre, fallback sur la référence.
    - si pas de quantité total, erreur
    """
    # On ajuste le recipe selon le scénario
    if not has_pan:
        recipe.pan = None
    if not has_servings:
        recipe.servings_min = None
        recipe.servings_max = None
    recipe.save()
    # Appel de la fonction selon le mode
    kwargs = {}
    if has_pan:
        kwargs['target_pan'] = target_pan
    if has_servings:
        kwargs['target_servings'] = 12  # arbitraire
    if use_reference:
        kwargs['reference_recipe'] = reference_recipe

    if should_raise_error:
        with pytest.raises(ValueError):
            get_scaling_multiplier(recipe, **kwargs)
    else :
        multiplier, mode = get_scaling_multiplier(recipe, **kwargs)
        assert mode == expect_mode
        data = scale_recipe_globally(recipe, multiplier)
        assert abs(data["scaling_multiplier"] - multiplier) < 0.01

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

    m, mode = get_scaling_multiplier(recipe, target_pan=target_pan)
    assert abs(m - multiplier) < 0.01
    assert mode == "pan"
    result = scale_recipe_globally(recipe, m)

    adapted_ingredient = result["ingredients"][0]
    assert abs(adapted_ingredient["quantity"] - round(original_quantity * multiplier, 2)) < 0.1

def test_adapt_recipe_servings_to_volume(recipe):
    """
    Vérifie que la recette est bien adaptée à un nombre de portions cible (volume calculé),
    en l'absence de pan d'origine (mode scaling = 'servings').
    """
    target_servings = 10
    recipe.pan = None  # Force le scaling par servings
    recipe.save()
    volume_source = ((recipe.servings_min + recipe.servings_max) / 2) * 150
    volume_target = target_servings * 150
    multiplier = volume_target / volume_source

    m, mode = get_scaling_multiplier(recipe, target_servings=target_servings)
    assert abs(m - multiplier) < 0.01
    assert mode == "servings"
    result = scale_recipe_globally(recipe, m)

    # On vérifie les quantités adaptées
    for ing, original in zip(result["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

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

    m, mode = get_scaling_multiplier(recipe, target_servings=target_servings)
    assert abs(m - multiplier) < 0.01
    assert mode == "servings"
    result = scale_recipe_globally(recipe, m)

    for ing, original in zip(result["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(original.quantity * multiplier, 2)) < 0.1

def test_adapt_recipe_reference_to_reference(recipe, reference_recipe):
    """
    Vérifie que l'adaptation d'une recette via une recette de référence (scaling par poids)
    fonctionne correctement sur toutes les quantités, y compris dans les sous-recettes, et ne modifie pas la base.

    - Le scaling_multiplier doit être le ratio des poids totaux.
    - Toutes les quantités sont multipliées par ce ratio.
    - La base de données n'est jamais modifiée.
    """
    # Préparation du contexte : 
    # On retire pan et servings pour forcer le fallback sur le scaling par référence
    recipe.pan = None
    recipe.servings_min = None
    recipe.servings_max = None
    recipe.total_recipe_quantity = 300
    recipe.save()
    reference_recipe.total_recipe_quantity = 1200
    reference_recipe.save()

    # On ajoute une sous-recette
    ingr2 = Ingredient.objects.create(ingredient_name="Beurre")
    sub_recipe = Recipe.objects.create(recipe_name="Sous-crème", chef_name="Chef Sous", total_recipe_quantity=50)
    RecipeIngredient.objects.create(recipe=sub_recipe, ingredient=ingr2, quantity=10, unit="g")
    SubRecipe.objects.create(recipe=recipe, sub_recipe=sub_recipe, quantity=25, unit="g")

    # 1. Calcul du multiplicateur attendu
    expected_multiplier = reference_recipe.total_recipe_quantity / recipe.total_recipe_quantity

    # 2. Appel du scaling
    multiplier, mode = get_scaling_multiplier(recipe, reference_recipe=reference_recipe)
    assert mode == "reference_recipe"
    assert abs(multiplier - expected_multiplier) < 0.01

    data = scale_recipe_globally(recipe, multiplier)
    assert abs(data["scaling_multiplier"] - expected_multiplier) < 0.01

    # 3. Vérification que toutes les quantités d'ingrédients ont bien été multipliées
    for ing, orig in zip(data["ingredients"], recipe.recipe_ingredients.all()):
        assert abs(ing["quantity"] - round(orig.quantity * multiplier, 2)) < 0.1

    # 4. Vérification des sous-recettes
    if data["subrecipes"]:
        for sub_data, sub_instance in zip(data["subrecipes"], recipe.used_in_recipes.all()):
            # Quantité de la sous-recette
            assert abs(sub_data["quantity"] - round(sub_instance.quantity * expected_multiplier, 2)) < 0.1
            # Vérification des ingrédients de la sous-recette
            for ing_sub_data, ing_orig in zip(sub_data["ingredients"], sub_instance.sub_recipe.recipe_ingredients.all()):
                assert abs(ing_sub_data["quantity"] - round(ing_orig.quantity * expected_multiplier, 2)) < 0.1
            # (si sous-sous-recette, boucle récursive possible ici)
            if sub_data.get("subrecipes"):
                for subsub_data, subsub_instance in zip(sub_data["subrecipes"], sub_instance.sub_recipe.subrecipes.all()):
                    assert abs(subsub_data["quantity"] - round(subsub_instance.quantity * expected_multiplier, 2)) < 0.1
                    for ing_subsub_data, ing_orig2 in zip(subsub_data["ingredients"], subsub_instance.sub_recipe.recipe_ingredients.all()):
                        assert abs(ing_subsub_data["quantity"] - round(ing_orig2.quantity * expected_multiplier, 2)) < 0.1
    else:
        # Aucun subrecipe, rien à vérifier ici
        assert recipe.subrecipes.count() == 1  # 1 sous-recette présente

    # 5. Vérification que la base de données n'est pas modifiée (idempotence)
    for orig in recipe.recipe_ingredients.all():
        db_ri = RecipeIngredient.objects.get(pk=orig.pk)
        assert db_ri.quantity == orig.quantity

    # 6. S'assure que la recette d'origine n'est pas modifiée côté poids
    recipe.refresh_from_db()
    assert recipe.total_recipe_quantity == 300

    # 7. S'assure aussi que la recette de référence n'est pas modifiée
    reference_recipe.refresh_from_db()
    assert reference_recipe.total_recipe_quantity == 1200

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

    # Test avec un nombre élevé
    result_high = suggest_pans_for_servings(target_servings=50)
    # assert result_high["target_volume_cm3"] == 50 * 150
    assert isinstance(result_high, list)
    assert all("id" in pan for pan in result_high)

    # Gestion des erreurs
    with pytest.raises(ValueError):
        suggest_pans_for_servings(target_servings=0)

def test_suggest_reference_on_category(recipe, reference_recipe):
    """ Vérifie qu'une suggestion de recette de référence trouve d'abord la même catégorie (ou parent si non trouvée). """
    parent = Category.objects.create(category_name="Bases", category_type="recipe")
    sub = Category.objects.create(category_name="Crèmes", category_type="recipe", parent_category=parent)
    recipe.categories.set([sub])
    recipe.save()
    reference_recipe.categories.set([sub])
    reference_recipe.save()
    suggestions = Recipe.objects.exclude(pk=recipe.pk).filter(categories=sub)
    assert reference_recipe in suggestions
    # Remove from sub, put only parent
    recipe.categories.set([parent])
    recipe.save()
    reference_recipe.categories.set([parent])
    reference_recipe.save()
    suggestions2 = Recipe.objects.exclude(pk=recipe.pk).filter(categories=parent)
    assert reference_recipe in suggestions2

def test_adapt_recipe_by_ingredients_constraints(recipe):
    """
    Vérifie que la recette est bien adaptée en fonction des quantités disponibles
    pour un ou plusieurs ingrédients.
    """
    ingredient = recipe.recipe_ingredients.first().ingredient
    constraints = {ingredient.id: 100}  # Quantité disponible

    multiplier, limiting_ingredient_id = get_limiting_multiplier(recipe, constraints)
    result = scale_recipe_globally(recipe, multiplier)

    expected_multiplier = 100 / recipe.recipe_ingredients.first().quantity

    assert result["scaling_multiplier"] == expected_multiplier
    assert abs(result["ingredients"][0]["quantity"] - 100) < 0.01

@pytest.mark.parametrize("scaling_mode", ["servings", "pan", "ingredient_limit", "reference_recipe"])
def test_scaling_global_propagation(scaling_mode):
    """
    Vérifie que le scaling global est appliqué partout dans la hiérarchie
    (ingrédients et sous-recettes imbriquées), peu importe les champs présents dans les sous-recettes.
    """
    # Prépare une structure : recette principale → sous-recette → sous-sous-recette
    ingr1 = Ingredient.objects.create(ingredient_name="Sucre")
    ingr2 = Ingredient.objects.create(ingredient_name="Farine")
    ingr3 = Ingredient.objects.create(ingredient_name="Beurre")

    sub_sub_recipe = Recipe.objects.create(recipe_name="Crème", chef_name="Chef Choco")
    RecipeIngredient.objects.create(recipe=sub_sub_recipe, ingredient=ingr1, quantity=50, unit="g")
    RecipeStep.objects.create(recipe=sub_sub_recipe, step_number=1, instruction="Mélanger les ingrédients")

    sub_recipe = Recipe.objects.create(recipe_name="Garniture", chef_name="Chef Choco")
    RecipeIngredient.objects.create(recipe=sub_recipe, ingredient=ingr2, quantity=30, unit="g")
    SubRecipe.objects.create(recipe=sub_recipe, sub_recipe=sub_sub_recipe, quantity=100, unit="g")
    RecipeStep.objects.create(recipe=sub_recipe, step_number=1, instruction="Mélanger les ingrédients")

    main_recipe = Recipe.objects.create(recipe_name="Tarte", chef_name="Chef Choco")
    RecipeIngredient.objects.create(recipe=main_recipe, ingredient=ingr3, quantity=20, unit="g")
    SubRecipe.objects.create(recipe=main_recipe, sub_recipe=sub_recipe, quantity=200, unit="g")
    RecipeStep.objects.create(recipe=main_recipe, step_number=1, instruction="Mélanger les ingrédients")

    # Calcul du multiplicateur selon le mode choisi
    reference_recipe = None
    if scaling_mode == "reference_recipe":
        reference_recipe = Recipe.objects.create(recipe_name="Réf", chef_name="XXX", total_recipe_quantity=1000)
        main_recipe.total_recipe_quantity = 200
        main_recipe.save()
        expected_multiplier = reference_recipe.total_recipe_quantity / main_recipe.total_recipe_quantity
        multiplier = expected_multiplier
    elif scaling_mode == "servings":
        multiplier = 2.0  # Ex : on veut doubler le nombre de parts
    elif scaling_mode == "pan":
        multiplier = 3.0  # Ex : moule 3x plus grand
    elif scaling_mode == "ingredient_limit":
        # Imite un scaling par ingrédient limitant (ex : il ne reste que 10g de sucre sur 50g)
        multiplier = 0.2

    # Appel la méthode
    data = scale_recipe_globally(main_recipe, multiplier)

    # Vérifie que toutes les quantités ont bien été multipliées
    assert abs(data["scaling_multiplier"] - multiplier) < 0.01

    ingr_main = data["ingredients"][0]
    assert abs(ingr_main["quantity"] - (20 * multiplier)) < 0.01

    sub = data["subrecipes"][0]
    assert abs(sub["quantity"] - (200 * multiplier)) < 0.01

    ingr_sub = sub["ingredients"][0]
    assert abs(ingr_sub["quantity"] - (30 * multiplier)) < 0.01

    subsub = sub["subrecipes"][0]
    assert abs(subsub["quantity"] - (100 * multiplier)) < 0.01
    ingr_subsub = subsub["ingredients"][0]
    assert abs(ingr_subsub["quantity"] - (50 * multiplier)) < 0.01

    # Vérifie aussi dans le cas référence que le mode aurait pu être récupéré
    if scaling_mode == "reference_recipe":
        assert abs(multiplier - (reference_recipe.total_recipe_quantity / main_recipe.total_recipe_quantity)) < 0.01

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

    # Sous-recettes
    for sub in data["subrecipes"]:
        assert "ingredients" in sub and isinstance(sub["ingredients"], list)

def test_recipe_adaptation_api_reference_recipe(api_client, recipe, user, reference_recipe):
    """
    Teste l’adaptation d’une recette via le endpoint /recipes-adapt/ avec reference_recipe_id,
    vérifie que les quantités sont correctes et que la base n’est pas modifiée.
    """
    api_client.force_authenticate(user=user)
    url = reverse("adapt-recipe")

    # On prépare une recette sans pan ni servings
    recipe.pan = None
    recipe.servings_min = None
    recipe.servings_max = None
    recipe.total_recipe_quantity = 100
    recipe.save()
    reference_recipe.total_recipe_quantity = 400
    reference_recipe.save()

    data = {"recipe_id": recipe.id, "reference_recipe_id": reference_recipe.id}
    response = api_client.post(url, data, format="json")
    assert response.status_code == 200
    assert response.data["scaling_mode"] == "reference_recipe"
    multiplier = reference_recipe.total_recipe_quantity / recipe.total_recipe_quantity
    assert abs(response.data["scaling_multiplier"] - multiplier) < 0.01
    # Vérification quantités adaptées
    for ing in response.data["ingredients"]:
        orig = recipe.recipe_ingredients.get(ingredient__ingredient_name=ing["ingredient_name"])
        assert abs(ing["quantity"] - orig.quantity * multiplier) < 0.1

    # Vérification de l’idempotence
    for orig in recipe.recipe_ingredients.all():
        db_ri = RecipeIngredient.objects.get(pk=orig.pk)
        assert db_ri.quantity == orig.quantity

def test_recipe_adaptation_api_reference_recipe_error(api_client, recipe, user, reference_recipe):
    """ Vérifie que le endpoint lève une erreur claire si la recette de référence n'a pas de total_recipe_quantity. """
    api_client.force_authenticate(user=user)
    url = reverse("adapt-recipe")
    recipe.pan = None
    recipe.servings_min = None
    recipe.servings_max = None
    recipe.total_recipe_quantity = 100
    recipe.save()
    reference_recipe.total_recipe_quantity = None
    reference_recipe.save()
    data = {"recipe_id": recipe.id, "reference_recipe_id": reference_recipe.id}
    response = api_client.post(url, data, format="json")
    print(response.data)
    assert response.status_code == 400
    assert "quantité totale" in response.data["error"]

@pytest.mark.parametrize("adapt_mode", [
    "pan_to_pan",
    "servings_to_pan",
    "servings_to_servings",
    "servings_to_volume",
    "reference_recipe",
])
@pytest.mark.parametrize("recursive", [False, True])
def test_recipe_adaptation_api_all_modes(api_client, adapt_mode, recursive):
    """
    Teste l'adaptation d'une recette via l'API pour tous les modes principaux,
    et vérifie la récursivité (scaling correct dans toutes les sous-recettes).
    """
    # ---------- Préparation des ingrédients et recettes ----------
    # Ingrédients
    ingr_main = Ingredient.objects.create(ingredient_name="Oeuf")
    ingr_extra = Ingredient.objects.create(ingredient_name="Sucre")

    # Pans de test (pan rond et pan rectangle)
    pan_rond = Pan.objects.create(pan_name="Rond", pan_type="ROUND", diameter=10, height=4, volume_cm3_cache=math.pi * (10/2)**2 * 4)
    pan_rect = Pan.objects.create(pan_name="Rect", pan_type="RECTANGLE", length=10, width=5, rect_height=4, volume_cm3_cache=10*5*4)

    # ---------- Création de la structure recette ----------
    if recursive:
        # Sous-sous-recette
        sub_sub_recipe = Recipe.objects.create(recipe_name="Crème", chef_name="Chef Choco")
        RecipeStep.objects.create(recipe=sub_sub_recipe, step_number=1, instruction="Mélanger les ingrédients")
        RecipeIngredient.objects.create(recipe=sub_sub_recipe, ingredient=ingr_extra, quantity=50, unit="g")
        # Facultatif : pan/servings pour sub_sub_recipe selon adapt_mode
        if adapt_mode in ("pan_to_pan", "servings_to_volume"):
            sub_sub_recipe.pan = Pan.objects.create(pan_name="SSRect", pan_type="RECTANGLE", length=5, width=5, rect_height=2, volume_cm3_cache=50)
            sub_sub_recipe.save()
        elif adapt_mode in ("servings_to_servings", "servings_to_pan"):
            sub_sub_recipe.servings_min = sub_sub_recipe.servings_max = 2
            sub_sub_recipe.save()

        # Sous-recette
        sub_recipe = Recipe.objects.create(recipe_name="Fourrage", chef_name="Chef Choco")
        RecipeStep.objects.create(recipe=sub_recipe, step_number=1, instruction="Mélanger les ingrédients")
        SubRecipe.objects.create(recipe=sub_recipe, sub_recipe=sub_sub_recipe, quantity=100, unit="g")
        RecipeIngredient.objects.create(recipe=sub_recipe, ingredient=ingr_main, quantity=20, unit="unit")
        # Pan/servings pour sub_recipe
        if adapt_mode in ("pan_to_pan", "servings_to_volume"):
            sub_recipe.pan = Pan.objects.create(pan_name="SRect", pan_type="RECTANGLE", length=10, width=5, rect_height=2, volume_cm3_cache=100)
            sub_recipe.save()
        elif adapt_mode in ("servings_to_servings", "servings_to_pan"):
            sub_recipe.servings_min = sub_recipe.servings_max = 2
            sub_recipe.save()

        # Recette principale
        recipe = Recipe.objects.create(recipe_name="Gâteau", chef_name="Chef Choco")
        RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
        SubRecipe.objects.create(recipe=recipe, sub_recipe=sub_recipe, quantity=200, unit="g")
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ingr_main, quantity=2, unit="unit")

    else:
        # Recette plate (simple)
        recipe = Recipe.objects.create(recipe_name="Cake", chef_name="Chef Choco")
        RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger les ingrédients")
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ingr_main, quantity=2, unit="unit")
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ingr_extra, quantity=50, unit="g")

    # ---------- Ajout du pan/servings sur la recette principale ----------
    reference_recipe = None
    if adapt_mode == "pan_to_pan":
        recipe.pan = pan_rond
        recipe.save()
        target_pan = pan_rect
    elif adapt_mode == "servings_to_pan":
        recipe.pan = None
        recipe.servings_min = recipe.servings_max = 4
        recipe.save()
        target_pan = pan_rect
    elif adapt_mode == "servings_to_volume":
        recipe.pan = pan_rect
        recipe.servings_min = recipe.servings_max = 4
        recipe.save()
        target_pan = None
    elif adapt_mode == "servings_to_servings":
        recipe.pan = None
        recipe.servings_min = 4
        recipe.servings_max = 6
        recipe.save()
        target_pan = None
    elif adapt_mode == "reference_recipe":
        # On force une recette sans pan ni servings, et prépare une recette référente
        recipe.pan = None
        recipe.servings_min = None
        recipe.servings_max = None
        recipe.total_recipe_quantity = 100
        recipe.save()
        reference_recipe = Recipe.objects.create(recipe_name="Référence", chef_name="Chef Ref", total_recipe_quantity=400)
        target_pan = None  # Pas utilisé

    # ---------- Préparation des paramètres API ----------
    url = reverse("adapt-recipe")
    params = {"recipe_id": recipe.id}

    if adapt_mode == "pan_to_pan":
        params["source_pan_id"] = recipe.pan.id
        params["target_pan_id"] = target_pan.id
        source_volume = pan_rond.volume_cm3_cache
        target_volume = pan_rect.volume_cm3_cache
        multiplier = target_volume / source_volume
    elif adapt_mode == "servings_to_pan":
        params["target_pan_id"] = target_pan.id
        servings = recipe.servings_min
        source_volume = servings * 150
        target_volume = pan_rect.volume_cm3_cache
        multiplier = target_volume / source_volume
    elif adapt_mode == "servings_to_volume":
        params["source_pan_id"] = recipe.pan.id
        params["target_servings"] = 8
        source_volume = recipe.pan.volume_cm3_cache
        target_volume = 8 * 150
        multiplier = target_volume / source_volume
    elif adapt_mode == "servings_to_servings":
        params["target_servings"] = 8
        source_volume = ((recipe.servings_min + recipe.servings_max) / 2) * 150
        target_volume = 8 * 150
        multiplier = target_volume / source_volume
    elif adapt_mode == "reference_recipe":
        params["reference_recipe_id"] = reference_recipe.id
        multiplier = reference_recipe.total_recipe_quantity / recipe.total_recipe_quantity

    # ---------- Appel API et vérifs génériques ----------
    response = api_client.post(url, params, format="json")
    assert response.status_code == status.HTTP_200_OK, response.content
    data = response.json()

    # Vérif structure principale
    assert "recipe_id" in data and data["recipe_id"] == recipe.id
    assert "scaling_multiplier" in data
    assert abs(data["scaling_multiplier"] - multiplier) < 0.01
    assert "ingredients" in data and isinstance(data["ingredients"], list)
    assert "subrecipes" in data and isinstance(data["subrecipes"], list)

    # Vérifie les ingrédients directs scalés
    ingredients_orig = list(recipe.recipe_ingredients.all())
    for ing in data["ingredients"]:
        # Cherche la correspondance par id
        orig = next((ri for ri in ingredients_orig if ri.ingredient.id == ing["ingredient_id"]), None)
        assert orig is not None
        expected_qty = round(orig.quantity * multiplier, 2)
        assert abs(ing["quantity"] - expected_qty) < 0.1
        assert "ingredient_name" in ing and ing["ingredient_name"] == orig.ingredient.ingredient_name
        assert "unit" in ing and ing["unit"] == orig.unit

    # ---------- Vérifs récursivité : chaque sous-recette est bien adaptée ----------
    def check_subrecipes(subs, model_subs, local_multiplier):
        """
        Vérifie récursivement le scaling des sous-recettes et de leurs ingrédients.
        """
        assert len(subs) == model_subs.count()
        for subdata, model_sub in zip(subs, model_subs.all()):
            # Quantité utilisée de la sous-recette (doit être scalée)
            expected_qty = model_sub.quantity * local_multiplier
            assert abs(subdata["quantity"] - expected_qty) < 0.1

            # Vérif des ingrédients dans la sous-recette
            ingr_orig = list(model_sub.sub_recipe.recipe_ingredients.all())
            for ing in subdata["ingredients"]:
                orig = next((ri for ri in ingr_orig if ri.ingredient.id == ing["ingredient_id"]), None)
                if orig:
                    exp_qty = round(orig.quantity * local_multiplier, 2)
                    assert abs(ing["quantity"] - exp_qty) < 0.1

            # Vérif récursif pour sous-sous-recettes si existant
            if "subrecipes" in subdata and model_sub.sub_recipe.main_recipes.exists():
                check_subrecipes(subdata["subrecipes"], model_sub.sub_recipe.main_recipes, local_multiplier)

    check_subrecipes(data["subrecipes"], recipe.main_recipes, multiplier)

    # ---------- Vérifie qu'aucune donnée n'a été modifiée en base ----------
    for original in ingredients_orig:
        db_ri = RecipeIngredient.objects.get(pk=original.pk)
        assert db_ri.quantity == original.quantity

    # pour le mode référence, vérifie bien le champ scaling_mode
    if adapt_mode == "reference_recipe":
        assert data["scaling_mode"] == "reference_recipe"

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

def test_recipe_adaptation_by_ingredient_api_flat(api_client, recipe):
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

def test_recipe_adaptation_by_ingredient_api_recursive(api_client):
    """
    Vérifie que l’API adapte correctement une recette complexe (avec sous-recettes)
    en fonction de la quantité d’un ingrédient limitant présent dans une sous-recette.
    """
    # Création de l'ingrédient limitant partagé par toutes les couches
    chocolat = Ingredient.objects.create(ingredient_name="Chocolat")

    # Sous-sous-recette
    sub_sub_recipe = Recipe.objects.create(recipe_name="Crème Chocolat", chef_name="Chef Choco")
    RecipeIngredient.objects.create(recipe=sub_sub_recipe, ingredient=chocolat, quantity=40, unit="g")
    RecipeStep.objects.create(recipe=sub_sub_recipe, step_number=1, instruction="Préparer la crème")

    # Sous-recette qui inclut la sous-sous-recette
    sub_recipe = Recipe.objects.create(recipe_name="Fourrage", chef_name="Chef Choco")
    SubRecipe.objects.create(recipe=sub_recipe, sub_recipe=sub_sub_recipe, quantity=100, unit="g")
    noisette = Ingredient.objects.create(ingredient_name="Noisette")
    RecipeIngredient.objects.create(recipe=sub_recipe, ingredient=noisette, quantity=60, unit="g")

    # Recette principale
    main_recipe = Recipe.objects.create(recipe_name="Gâteau", chef_name="Chef Choco")
    SubRecipe.objects.create(recipe=main_recipe, sub_recipe=sub_recipe, quantity=100, unit="g")
    oeuf = Ingredient.objects.create(ingredient_name="Oeuf")
    RecipeIngredient.objects.create(recipe=main_recipe, ingredient=oeuf, quantity=2, unit="unit")
    RecipeStep.objects.create(recipe=main_recipe, step_number=1, instruction="Assembler le gâteau")

    # Appel API avec une contrainte sur le chocolat (limite à 10g)
    url = reverse("adapt-recipe-by-ingredient")
    print("ID Chocolat attendu :", chocolat.id)
    for rec in [main_recipe, sub_recipe, sub_sub_recipe]:
        print("Dans recette", rec.recipe_name, "ids ingrédients :", [i.ingredient.id for i in rec.recipe_ingredients.all()])
    response = api_client.post(url, {"recipe_id": main_recipe.id, "ingredient_constraints": {str(chocolat.id): 10}}, format="json")
    print(response.json())  # Pour débogage
    assert response.status_code == 200
    data = response.json()
    assert data["recipe_id"] == main_recipe.id
    assert data["limiting_ingredient_id"] == chocolat.id
    assert abs(data["multiplier"] - 0.25) < 0.01

    # Vérifie la quantité de chocolat dans la sous-sous-recette (crème chocolat)
    sub_level = data["subrecipes"][0]
    subsub_level = sub_level["subrecipes"][0]
    choco_qty = next(i for i in subsub_level["ingredients"] if i["ingredient_name"] == "Chocolat")["quantity"]
    assert abs(choco_qty - 10) < 0.01

    # Vérifie que les autres ingrédients sont bien scalés aussi
    noisette_qty = next(i for i in sub_level["ingredients"] if i["ingredient_name"] == "Noisette")["quantity"]
    assert abs(noisette_qty - (60 * 0.25)) < 0.01
    oeuf_qty = data["ingredients"][0]["quantity"]
    assert abs(oeuf_qty - (2 * 0.25)) < 0.01

#  POST /recipes/<id>/reference-suggestions/

@pytest.mark.parametrize(
    "use_direct_match, use_parent_fallback",
    [
        (True, False),   # Match direct sur la même catégorie
        (False, True),   # Pas de match direct, mais fallback parent_category
    ]
)
def test_reference_suggestions_api_returns_expected_reference(api_client, recipe, reference_recipe, use_direct_match, use_parent_fallback):
    """
    Teste que l’API /api/recipes/<pk>/reference-suggestions/ retourne la bonne recette de référence :
    - Cas 1 : même catégorie => match direct
    - Cas 2 : pas de match direct mais la recette de référence partage le même parent_category
    """
    # Création des catégories
    cat_main = Category.objects.create(category_name="Entremets", category_type="recipe")
    cat_parent = Category.objects.create(category_name="Desserts", category_type="recipe")
    recipe.categories.set([])  # Nettoie d'abord
    reference_recipe.categories.set([])

    # Cas 1 : matching direct
    if use_direct_match:
        recipe.categories.add(cat_main)
        reference_recipe.categories.add(cat_main)
    # Cas 2 : pas de match direct, fallback sur parent_category
    elif use_parent_fallback:
        # La recette cible a une sous-catégorie dont le parent est le même que la catégorie de référence
        subcat = Category.objects.create(category_name="Entremets Fruits", category_type="recipe", parent_category=cat_parent)
        recipe.categories.add(subcat)
        reference_recipe.categories.add(cat_parent)

    url = reverse("recipe-reference-suggestions", kwargs={"pk": recipe.id})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # La clé "reference_recipes" doit toujours exister et être une liste
    assert "reference_recipes" in data
    assert isinstance(data["reference_recipes"], list)
    assert len(data["reference_recipes"]) >= 1

    # Doit suggérer la bonne recette de référence
    ids = [ref["id"] for ref in data["reference_recipes"]]
    assert reference_recipe.id in ids

def test_reference_suggestions_api_no_suggestion(api_client, recipe):
    """
    Teste que l’API /api/recipes/<pk>/reference-suggestions/ retourne une liste vide
    s’il n’existe aucune recette de référence compatible (pas de catégorie partagée, ni parent commun).
    """
    # Création d'une catégorie sans aucune recette de référence associée
    cat = Category.objects.create(category_name="Viennoiseries", category_type="recipe")
    recipe.categories.set([cat])

    url = reverse("recipe-reference-suggestions", kwargs={"pk": recipe.id})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "reference_recipes" in data
    # Aucun résultat attendu
    assert data["reference_recipes"] == []

