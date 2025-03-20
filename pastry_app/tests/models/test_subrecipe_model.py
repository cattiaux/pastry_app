import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from pastry_app.models import Recipe, SubRecipe
from pastry_app.tests.utils import validate_constraint

@pytest.fixture
def subrecipe():
    """ Crée une sous-recette d'une recette"""
    recipe1 = Recipe.objects.create(recipe_name="Tarte aux pommes")
    recipe2 = Recipe.objects.create(recipe_name="Crème pâtissière")
    return SubRecipe.objects.create(recipe=recipe1, sub_recipe=recipe2, quantity=200, unit="g")

@pytest.mark.django_db
def test_create_subrecipe(subrecipe):
    """ Vérifie que la création d’une `SubRecipe` fonctionne correctement """
    assert isinstance(subrecipe, SubRecipe)
    assert subrecipe.quantity == 200
    assert subrecipe.unit == "g"

@pytest.mark.django_db
def test_subrecipe_str_method(subrecipe):
    """ Vérifie que `__str__()` retourne un format lisible """
    expected_str = f"{subrecipe.quantity} {subrecipe.unit} de {subrecipe.sub_recipe.recipe_name} dans {subrecipe.recipe.recipe_name}"
    assert str(subrecipe) == expected_str

@pytest.mark.django_db
def test_update_subrecipe_quantity_and_unit_db(subrecipe):
    """ Vérifie qu'on peut modifier la quantité et l’unité d’une `SubRecipe` """
    subrecipe.quantity = 500
    subrecipe.unit = "kg"
    subrecipe.save()
    subrecipe.refresh_from_db()
    assert subrecipe.quantity == 500
    assert subrecipe.unit == "kg"

@pytest.mark.django_db
def test_delete_subrecipe_db(subrecipe):
    """ Vérifie qu'on peut supprimer une `SubRecipe` sans affecter la recette principale """
    subrecipe.delete()
    assert not SubRecipe.objects.filter(id=subrecipe.id).exists()
    assert Recipe.objects.filter(id=subrecipe.recipe.id).exists()  # La recette principale doit toujours exister

@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["quantity", "unit"])
def test_required_fields_subrecipe_db(subrecipe, field_name):
    """ Vérifie que `quantity` et `unit` sont obligatoires (absence, None, vide) """
    expected_errors = [
        "This field cannot be null.",  # Erreur Django niveau DB
        "This field is required.",  # Erreur DRF si non fourni
        "This field cannot be blank.",  # Uniquement pour `CharField` (`unit`)
        "“” value must be a float.",  # Uniquement pour `FloatField` (`quantity`)
        "Une quantité est obligatoire.",
        "Une unité de mesure est obligatoire."]
    for invalid_value in [None, ""]:  # Tester `None` et `""`
        validate_constraint(SubRecipe, field_name, invalid_value, expected_errors, 
                            recipe=subrecipe.recipe, sub_recipe=subrecipe.sub_recipe, 
                            quantity=200, unit="g")
    
    # Tester l'absence du champ (non envoyé)
    valid_data = {"recipe": subrecipe.recipe, "sub_recipe": subrecipe.sub_recipe, "quantity": subrecipe.quantity, "unit": subrecipe.unit}
    del valid_data[field_name]  # Supprimer le champ à tester
    validate_constraint(SubRecipe, field_name, None, expected_errors, **valid_data)

@pytest.mark.django_db
@pytest.mark.parametrize("invalid_quantity", [0, -50])
def test_quantity_must_be_positive_subrecipe_db(subrecipe, invalid_quantity):
    """ Vérifie que la quantité doit être strictement positive """
    with pytest.raises(ValidationError, match="Ensure this value is greater than or equal to 0.|La quantité doit être strictement positive."):
        subrecipe.quantity = invalid_quantity
        subrecipe.full_clean()

@pytest.mark.django_db
def test_unit_must_be_valid_subrecipe_db(subrecipe):
    """ Vérifie qu’une unité invalide génère une erreur """
    with pytest.raises(ValidationError, match="is not a valid choice"):
        subrecipe.unit = "invalid_unit"
        subrecipe.full_clean()

@pytest.mark.django_db
def test_cannot_add_recipe_as_its_own_subrecipe():
    """ Vérifie qu’une recette ne peut pas être sa propre sous-recette """
    with pytest.raises(ValidationError, match="Une recette ne peut pas être sa propre sous-recette."):
        recipe = Recipe.objects.create(recipe_name="Tarte aux pommes")
        subrecipe = SubRecipe(recipe=recipe, sub_recipe=recipe, quantity=100, unit="g")
        subrecipe.full_clean()

@pytest.mark.django_db
def test_cannot_delete_recipe_used_as_subrecipe(subrecipe):
    """ Vérifie qu’on ne peut pas supprimer une recette utilisée comme sous-recette """
    with pytest.raises(ProtectedError, match="Cannot delete some instances of model 'Recipe'"):
        subrecipe.sub_recipe.delete()

