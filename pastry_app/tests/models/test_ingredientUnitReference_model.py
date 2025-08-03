import pytest
from pastry_app.models import IngredientUnitReference, Ingredient
from pastry_app.tests.utils import *

pytestmark = pytest.mark.django_db

@pytest.fixture()
def ingredient():
    return Ingredient.objects.create(ingredient_name="Œuf")

@pytest.fixture()
def reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50, notes="Valeur moyenne")

def test_reference_creation(reference, ingredient):
    """Vérifie la création d'une référence."""
    assert isinstance(reference, IngredientUnitReference)
    assert reference.ingredient == ingredient
    assert reference.unit == "unit"
    assert reference.weight_in_grams == 50

def test_reference_str_method(reference):
    """Vérifie la méthode __str__"""
    assert str(reference) == f"{reference.ingredient.ingredient_name} ({reference.unit}) : {reference.weight_in_grams} g"

def test_update_reference(reference):
    """Vérifie la mise à jour du poids."""
    reference.weight_in_grams = 52
    reference.save()
    reference.refresh_from_db()
    assert reference.weight_in_grams == 52

def test_unique_constraint_model(ingredient, reference):
    """Vérifie que l'unicité ingrédient + unité est bien imposée."""
    with pytest.raises(ValidationError):
        IngredientUnitReference(ingredient=ingredient, unit="unit", weight_in_grams=49).full_clean()

def test_weight_strictly_positive(ingredient):
    """Vérifie qu'on refuse un poids négatif ou nul."""
    for value in [0, -1]:
        ref = IngredientUnitReference(ingredient=ingredient, unit="unit", weight_in_grams=value)
        with pytest.raises(ValidationError):
            ref.full_clean()

def test_required_fields_model(ingredient):
    """Vérifie que les champs obligatoires sont requis."""
    # Pas utile de tester ingredient=None, Django bloque avant clean()
    # ref = IngredientUnitReference(ingredient=None, unit="unit", weight_in_grams=50)
    # with pytest.raises(ValidationError):
    #     ref.full_clean()

    ref = IngredientUnitReference(ingredient=ingredient, unit="", weight_in_grams=50)
    with pytest.raises(ValidationError):
        ref.full_clean()

def test_delete_reference(reference):
    """Vérifie la suppression d'une référence."""
    ref_id = reference.id
    reference.delete()
    assert not IngredientUnitReference.objects.filter(id=ref_id).exists()

