from django.test import TestCase
from pastry_app.models import Recipe
from pastry_app.tests.utils import normalize_case

class RecipeModelTest(TestCase):
    """Tests unitaires du modèle Recipe"""

    def setUp(self):
        """Création d’une recette pour tester le modèle"""
        self.recipe = Recipe.objects.create(recipe_name="Test Recipe", chef="Test Chef")

    def test_recipe_creation(self):
        """ Vérifie que l'on peut créer un objet Recipe"""
        self.assertIsInstance(self.recipe, Recipe)
        self.assertEqual(self.recipe.recipe_name, normalize_case("Test Recipe"))
        self.assertEqual(self.recipe.chef, normalize_case("Test Chef"))

    def test_recipe_str_method(self):
        """ Vérifie que `__str__()` retourne bien le `recipe_name`"""
        self.assertEqual(str(self.recipe), normalize_case("Test Recipe"))

    def test_recipe_update(self):
        """ Vérifie que l'on peut modifier une recette"""
        self.recipe.recipe_name = "Updated Recipe"
        self.recipe.save()
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.recipe_name, normalize_case("Updated Recipe"))

    def test_recipe_deletion(self):
        """ Vérifie que l'on peut supprimer une recette"""
        recipe_id = self.recipe.id
        self.recipe.delete()
        self.assertFalse(Recipe.objects.filter(id=recipe_id).exists())

    def test_recipe_name_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer une recette sans `recipe_name`"""
        with self.assertRaises(Exception):  # Django va lever une exception
            Recipe.objects.create(recipe_name=None, chef="Test Chef")

    def test_recipe_chef_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer une recette sans `chef`"""
        with self.assertRaises(Exception):
            Recipe.objects.create(recipe_name="Some Recipe", chef=None)
