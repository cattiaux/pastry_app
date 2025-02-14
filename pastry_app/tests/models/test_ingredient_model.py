from django.test import TestCase
from pastry_app.models import Ingredient, Category, Label
from pastry_app.tests.utils import normalize_case
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError

class IngredientModelTest(TestCase):
    """Tests unitaires du modèle Ingredient"""

    def setUp(self):
        """Création d’un ingrédient pour tester le modèle"""
        self.ingredient = Ingredient.objects.create(ingredient_name="Test Ingredient")

    def test_ingredient_creation(self):
        """ Vérifie que l'on peut créer un objet Ingredient"""
        self.assertIsInstance(self.ingredient, Ingredient)
        self.assertEqual(self.ingredient.ingredient_name, normalize_case("Test Ingredient"))

    def test_ingredient_str_method(self):
        """ Vérifie que `__str__()` retourne bien le `ingredient_name`"""
        self.assertEqual(str(self.ingredient), normalize_case("Test Ingredient"))

    def test_ingredient_update(self):
        """ Vérifie que l'on peut modifier un ingrédient"""
        self.ingredient.ingredient_name = "Updated Ingredient"
        self.ingredient.save()
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.ingredient_name, normalize_case("Updated Ingredient"))

    def test_ingredient_deletion(self):
        """ Vérifie que l'on peut supprimer un ingrédient"""
        ingredient_id = self.ingredient.id
        self.ingredient.delete()
        self.assertFalse(Ingredient.objects.filter(id=ingredient_id).exists())

    def test_ingredient_name_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer un ingrédient sans `ingredient_name`"""
        with self.assertRaises(Exception):
            Ingredient.objects.create(ingredient_name=None)

    def test_ingredient_can_have_categories(self):
        """🔍 Vérifie qu'un ingrédient peut être associé à des catégories."""
        ingredient = Ingredient.objects.create(ingredient_name="Chocolat Noir")
        category = Category.objects.create(category_name="Chocolat")
        ingredient.categories.add(category)  # Assigner une catégorie

        self.assertIn(category, ingredient.categories.all())  # Vérifier l’association

    def test_ingredient_can_have_labels(self):
        """ Vérifie qu'un ingrédient peut être associé à des labels."""
        ingredient = Ingredient.objects.create(ingredient_name="Chocolat Noir")
        label = Label.objects.create(label_name="Bio")
        ingredient.labels.add(label)  # Assigner un label

        self.assertIn(label, ingredient.labels.all())  # Vérifier l’association

    def test_cannot_assign_nonexistent_category(self):
        """ Vérifie qu'on ne peut pas assigner une catégorie qui n'existe pas."""
        ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
        
        with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
            with transaction.atomic():  # ✅ Force Django à exécuter immédiatement la requête SQL
                ingredient.categories.set([9999])  # 9999 est un ID qui n'existe pas

    def test_cannot_assign_nonexistent_label(self):
        """ Vérifie qu'on ne peut pas assigner un label qui n'existe pas."""
        ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
        
        with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
            with transaction.atomic():  # ✅ Force Django à exécuter immédiatement la requête SQL
                ingredient.labels.set([9999])  # 9999 est un ID qui n’existe pas
