import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from pastry_app.tests.utils import *

@pytest.fixture()
def recipe_ingredient(db):
    """ Crée une recette et un ingrédient pour les tests """
    recipe = Recipe.objects.create(recipe_name="Tarte aux pommes")
    ingredient = Ingredient.objects.create(ingredient_name="Sucre")
    return RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=100.0, unit="g")

@pytest.mark.django_db
def test_recipeingredient_creation_db(recipe_ingredient):
    """ Vérifie que la création d’un RecipeIngredient fonctionne """
    assert isinstance(recipe_ingredient, RecipeIngredient)
    assert recipe_ingredient.quantity == 100
    assert recipe_ingredient.unit == "g"

@pytest.mark.django_db
def test_recipeingredient_update_db(recipe_ingredient):
    """ Vérifie qu’on peut modifier la quantité et l’unité """
    recipe_ingredient.quantity = 200
    recipe_ingredient.unit = "kg"
    recipe_ingredient.save()
    recipe_ingredient.refresh_from_db()
    assert recipe_ingredient.quantity == 200
    assert recipe_ingredient.unit == "kg"

@pytest.mark.django_db
def test_recipeingredient_deletion_db(recipe_ingredient):
    """ Vérifie qu'on peut supprimer un RecipeIngredient sans supprimer l’Ingrédient """
    ingredient = recipe_ingredient.ingredient
    recipe_ingredient.delete()
    assert not RecipeIngredient.objects.filter(id=recipe_ingredient.id).exists()
    assert Ingredient.objects.filter(id=ingredient.id).exists()  # L'ingrédient doit toujours exister

@pytest.mark.django_db
def test_recipe_deletion_cascades_to_recipeingredient(recipe_ingredient):
    """ Vérifie que la suppression d'une recette supprime les RecipeIngredient associés """
    recipe_id = recipe_ingredient.recipe.id
    recipe_ingredient.recipe.delete()
    # Vérifie que RecipeIngredient a bien été supprimé
    assert not RecipeIngredient.objects.filter(recipe_id=recipe_id).exists()

@pytest.mark.django_db
def test_recipeingredient_str_method(recipe_ingredient):
    """ Vérifie que `__str__()` retourne bien une description lisible """
    expected_str = f"{recipe_ingredient.quantity} {recipe_ingredient.unit} de {recipe_ingredient.ingredient.ingredient_name} pour {recipe_ingredient.recipe.recipe_name}"
    assert str(recipe_ingredient) == expected_str

@pytest.mark.django_db
@pytest.mark.parametrize("invalid_quantity", [0, -50])
def test_recipeingredient_quantity_must_be_positive_db(invalid_quantity, recipe_ingredient):
    """ Vérifie que la quantité doit être strictement positive """
    recipe_ingredient.quantity = invalid_quantity
    with pytest.raises(ValidationError, match="Quantity must be a positive number.|Une quantité est obligatoire."):
        recipe_ingredient.full_clean()

@pytest.mark.django_db
def test_recipeingredient_unit_must_be_valid_db(recipe_ingredient):
    """ Vérifie qu’une unité invalide génère une erreur """
    recipe_ingredient.unit = "invalid_unit"
    with pytest.raises(ValidationError, match="L'unité .* n'est pas valide"):
        recipe_ingredient.full_clean()

@pytest.mark.parametrize("field_name", ["quantity", "unit"])
@pytest.mark.django_db
def test_required_fields_recipeingredient_db(field_name, recipe_ingredient):
    """ Vérifie que tous les champs obligatoires sont bien requis """
    expected_errors = ["This field cannot be null", "This field is required.", "This field cannot be blank.", "Une quantité est obligatoire.", "Une unité de mesure est obligatoire."]
    
    for invalid_value in [None, ""]:
        validate_constraint(RecipeIngredient, field_name, invalid_value, expected_errors, 
                            recipe=recipe_ingredient.recipe, ingredient=recipe_ingredient.ingredient, 
                            quantity=recipe_ingredient.quantity, unit=recipe_ingredient.unit)

@pytest.mark.django_db
def test_unit_must_be_valid_db(recipe_ingredient):
    """Vérifie que `unit` doit être parmi `UNIT_CHOICES`."""
    with pytest.raises(ValidationError, match="L'unité .* n'est pas valide"):
        price = RecipeIngredient(recipe=recipe_ingredient.recipe, ingredient=recipe_ingredient.ingredient, quantity=50, unit="INVALID_UNIT")  # Unité invalide
        price.full_clean()

@pytest.mark.django_db
def test_suffix_is_incremented(recipe_ingredient):
    """ Vérifie que les suffixes sont ajoutés correctement lors de l'ajout d'un même ingrédient plusieurs fois """
    recipe = recipe_ingredient.recipe
    ingredient = recipe_ingredient.ingredient

    # Ajout du second "Sucre" → Doit avoir "Sucre 2"
    ing2 = RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=50, unit="g")
    assert ing2.display_name == normalize_case("Sucre 2")

    # Ajout du troisième "Sucre" → Doit avoir "Sucre 3"
    ing3 = RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=30, unit="g")
    assert ing3.display_name == normalize_case("Sucre 3")

@pytest.mark.django_db
def test_suffix_reassignment_on_deletion(recipe_ingredient):
    """ Vérifie que les suffixes sont réattribués après la suppression d'un ingrédient """
    recipe = recipe_ingredient.recipe
    ingredient = recipe_ingredient.ingredient

    # Ajout de trois "Sucre" avec des suffixes
    ing2 = RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=50, unit="g")
    ing3 = RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=30, unit="g")

    ing2.delete() # Suppression du second ingrédient ("Sucre 2")

    # Vérifier que les suffixes ont été réattribués correctement
    recipe_ingredient.refresh_from_db()
    ing3.refresh_from_db()

    assert recipe_ingredient.display_name == normalize_case("Sucre 1")
    assert ing3.display_name == normalize_case("Sucre 2")  # Était "Sucre 3", devient "Sucre 2"

@pytest.mark.django_db
def test_no_suffix_when_ingredient_is_unique(recipe_ingredient):
    """ Vérifie qu'un ingrédient unique ne reçoit pas de suffixe """
    recipe = recipe_ingredient.recipe
    beurre = Ingredient.objects.create(ingredient_name="Beurre")
    ing = RecipeIngredient.objects.create(recipe=recipe, ingredient=beurre, quantity=200, unit="g")
    assert ing.display_name == normalize_case("Beurre")
