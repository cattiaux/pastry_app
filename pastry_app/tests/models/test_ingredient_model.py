import pytest
from django.db import IntegrityError, transaction
from pastry_app.models import Ingredient, Category, Label
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import CATEGORY_NAME_CHOICES, LABEL_NAME_CHOICES

"""Tests unitaires du modèle Ingredient"""

# Définir model_name pour les tests de Ingredient
model_name = "ingredients"

@pytest.fixture
def ingredient(db):
    """Création d’un ingredient avant chaque test"""
    return Ingredient.objects.create(ingredient_name="Test ingredient")

@pytest.mark.django_db
def test_ingredient_creation(ingredient):
    """ Vérifie que l'on peut créer un objet Ingredient"""
    assert isinstance(ingredient, Ingredient)
    assert ingredient.ingredient_name == normalize_case("Test Ingredient")

@pytest.mark.django_db
def test_ingredient_str_method(ingredient):
    """ Vérifie que `__str__()` retourne bien le `ingredient_name`"""
    assert str(ingredient) == normalize_case(ingredient.ingredient_name)

@pytest.mark.django_db
def test_ingredient_update(ingredient):
    """ Vérifie que l'on peut modifier un ingrédient"""
    ingredient_update_name = "Updated Ingredient"
    ingredient.ingredient_name = ingredient_update_name
    ingredient.save()
    ingredient.refresh_from_db()
    assert ingredient.ingredient_name == normalize_case(ingredient_update_name)

@pytest.mark.django_db
def test_ingredient_deletion(ingredient):
    """ Vérifie que l'on peut supprimer un ingrédient"""
    ingredient_id = ingredient.id
    ingredient.delete()
    assert not Ingredient.objects.filter(id=ingredient_id).exists()

@pytest.mark.django_db
def test_ingredient_can_have_categories(ingredient):
    """ Vérifie qu'un ingrédient peut être associé à des catégories."""
    valid_category_name = CATEGORY_NAME_CHOICES[0]  # Prendre une catégorie existante
    category = Category.objects.create(category_name=valid_category_name) 
    ingredient.categories.add(category)  # Assigner une catégorie

    assert category in ingredient.categories.all()  # Vérifier l’association

@pytest.mark.django_db
def test_ingredient_can_have_labels(ingredient):
    """ Vérifie qu'un ingrédient peut être associé à des labels."""
    valid_label_name = LABEL_NAME_CHOICES[0]  # Prendre une catégorie existante
    label = Label.objects.create(label_name=valid_label_name)
    ingredient.labels.add(label)  # Assigner un label

    assert label in ingredient.labels.all()  # Vérifier l’association






# def test_ingredient_name_cannot_be_empty(self):
#     """ Vérifie qu'on ne peut pas créer un ingrédient sans `ingredient_name`"""
#     with self.assertRaises(Exception):
#         Ingredient.objects.create(ingredient_name=None)

# def test_cannot_assign_nonexistent_category(self):
#     """ Vérifie qu'on ne peut pas assigner une catégorie qui n'existe pas."""
#     ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    
#     with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
#         with transaction.atomic():  # ✅ Force Django à exécuter immédiatement la requête SQL
#             ingredient.categories.set([9999])  # 9999 est un ID qui n'existe pas

# def test_cannot_assign_nonexistent_label(self):
#     """ Vérifie qu'on ne peut pas assigner un label qui n'existe pas."""
#     ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    
#     with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
#         with transaction.atomic():  # ✅ Force Django à exécuter immédiatement la requête SQL
#             ingredient.labels.set([9999])  # 9999 est un ID qui n’existe pas
