import pytest
from django.contrib.auth import get_user_model
from pastry_app.models import IngredientUnitReference, Ingredient
from pastry_app.tests.utils import *

pytestmark = pytest.mark.django_db

User = get_user_model()

@pytest.fixture()
def ingredient():
    return Ingredient.objects.create(ingredient_name="Œuf")

@pytest.fixture()
def reference(ingredient):
    return IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50, notes="Valeur moyenne")

@pytest.fixture()
def user():
    return User.objects.create_user(username="user1", password="pass")

@pytest.fixture()
def guest_id():
    return "guest123"

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

def test_unique_user_guest_global(ingredient, user, guest_id):
    # 1. Référence globale
    global_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=42)
    # 2. Référence user
    user_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=43, user=user)
    # 3. Référence guest
    guest_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=44, guest_id=guest_id)
    # 4. Les trois coexistent sans collision
    assert IngredientUnitReference.objects.count() == 3
    # 5. Mais pas de doublon pour le même user/guest
    with pytest.raises(ValidationError):
        IngredientUnitReference(ingredient=ingredient, unit="unit", weight_in_grams=45, user=user).full_clean()
    with pytest.raises(ValidationError):
        IngredientUnitReference(ingredient=ingredient, unit="unit", weight_in_grams=45, guest_id=guest_id).full_clean()

def test_user_override_global(ingredient, user):
    global_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50)
    user_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=55, user=user)
    assert user_ref.weight_in_grams != global_ref.weight_in_grams

def test_guest_override_global(ingredient, guest_id):
    global_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=50)
    guest_ref = IngredientUnitReference.objects.create(ingredient=ingredient, unit="unit", weight_in_grams=56, guest_id=guest_id)
    assert guest_ref.weight_in_grams != global_ref.weight_in_grams