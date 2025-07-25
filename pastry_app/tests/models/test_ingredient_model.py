import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from pastry_app.models import Ingredient, Category, Label
from pastry_app.tests.utils import normalize_case

"""Tests unitaires du modèle Ingredient"""

# Création
# test_ingredient_creation → Vérifie qu'on peut créer un objet Ingredient.
# test_ingredient_name_cannot_be_empty → Vérifie qu'on ne peut PAS créer un ingrédient avec un ingredient_name vide.

# Lecture
# test_ingredient_str_method → Vérifie que __str__() retourne bien ingredient_name.

# Mise à jour
# test_ingredient_update → Vérifie qu'on peut modifier un ingrédient.

# Suppression
# test_ingredient_deletion → Vérifie qu'on peut supprimer un ingrédient.

# Contraintes Spécifiques
# test_ingredient_can_have_categories → Vérifie qu'un ingrédient peut être associé à des catégories.
# test_ingredient_can_have_labels → Vérifie qu'un ingrédient peut être associé à des labels.

# Définir model_name pour les tests de Ingredient
model_name = "ingredients"

pytestmark = pytest.mark.django_db
User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def ingredient(db):
    """Création d’un ingredient avant chaque test"""
    return Ingredient.objects.create(ingredient_name="Test ingredient")

def test_ingredient_creation(ingredient):
    """ Vérifie que l'on peut créer un objet Ingredient"""
    assert isinstance(ingredient, Ingredient)
    assert ingredient.ingredient_name == normalize_case("Test Ingredient")

def test_ingredient_str_method(ingredient):
    """ Vérifie que `__str__()` retourne bien le `ingredient_name`"""
    assert str(ingredient) == normalize_case(ingredient.ingredient_name)

def test_ingredient_update(ingredient):
    """ Vérifie que l'on peut modifier un ingrédient"""
    ingredient_update_name = "Updated Ingredient"
    ingredient.ingredient_name = ingredient_update_name
    ingredient.save()
    ingredient.refresh_from_db()
    assert ingredient.ingredient_name == normalize_case(ingredient_update_name)

def test_ingredient_deletion(ingredient):
    """ Vérifie que l'on peut supprimer un ingrédient"""
    ingredient_id = ingredient.id
    ingredient.delete()
    assert not Ingredient.objects.filter(id=ingredient_id).exists()

def test_ingredient_can_have_categories(ingredient):
    """ Vérifie qu'un ingrédient peut être associé à des catégories."""
    category = Category.objects.create(category_name="TestCaté", category_type='recipe') 
    ingredient.categories.add(category)  # Assigner une catégorie
    assert category in ingredient.categories.all()  # Vérifier l’association

def test_ingredient_can_have_labels(ingredient):
    """ Vérifie qu'un ingrédient peut être associé à des labels."""
    label = Label.objects.create(label_name="Bio", label_type='recipe')
    ingredient.labels.add(label)  # Assigner un label
    assert label in ingredient.labels.all()  # Vérifier l’association

def test_ingredient_name_cannot_be_null():
    """ Vérifie qu'on ne peut pas enregistrer un ingrédient sans `ingredient_name` en base (contrainte Django). """
    with pytest.raises(ValidationError) as excinfo:
        Ingredient.objects.create(ingredient_name=None)
    assert 'ingredient_name' in str(excinfo.value)
    assert 'cannot be null' in str(excinfo.value)

def test_ingredient_cannot_have_recipe_only_category():
    # Création des catégories
    cat_ingredient = Category.objects.create(category_name="Cat Ingredient", category_type="ingredient")
    cat_both = Category.objects.create(category_name="Cat Both", category_type="both")
    cat_recipe = Category.objects.create(category_name="Cat Recipe", category_type="recipe")

    # Création de l'ingrédient
    ing = Ingredient.objects.create(ingredient_name="My Ingredient")
    ing.categories.add(cat_ingredient, cat_both)
    ing.full_clean()  # Doit passer sans erreur

    # Test avec une catégorie "recipe" (interdit)
    ing.categories.add(cat_recipe)
    with pytest.raises(ValidationError) as excinfo:
        ing.full_clean()
    assert "n'est pas valide pour un ingrédient" in str(excinfo.value)

@pytest.mark.parametrize(
    "with_user, with_guest_id, should_raise",
    [
        (True,  True,  True),   # Les deux → doit lever une erreur
        (True,  False, False),  # Uniquement user → ok
        (False, True,  False),  # Uniquement guest → ok
        (False, False, False),  # Aucun → ok
    ]
)
def test_ingredient_user_and_guest_id(user, with_user, with_guest_id, should_raise):
    user_instance = user if with_user else None
    guest_value = "guestid-xyz" if with_guest_id else None
    ingredient = Ingredient(ingredient_name="citron", user=user_instance, guest_id=guest_value)
    if should_raise:
        with pytest.raises(ValidationError):
            ingredient.full_clean()
    else:
        ingredient.full_clean()
