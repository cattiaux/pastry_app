import pytest
from django.db import IntegrityError
from django.core.exceptions import ValidationError
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