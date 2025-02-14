from django.test import TestCase
from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from pastry_app.tests.utils import normalize_case

class RecipeIngredientModelTest(TestCase):
    """Tests unitaires du modèle RecipeIngredient"""

    def setUp(self):
        """Création d’une recette et d’un ingrédient pour tester le modèle"""
        self.recipe = Recipe.objects.create(recipe_name="Cake", chef="Chef Paul")
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")
        self.recipe_ingredient = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ingredient, quantity=200
        )

    def test_recipe_ingredient_creation(self):
        """ Vérifie que l'on peut créer un objet RecipeIngredient"""
        self.assertIsInstance(self.recipe_ingredient, RecipeIngredient)
        self.assertEqual(self.recipe_ingredient.recipe, self.recipe)
        self.assertEqual(self.recipe_ingredient.ingredient, self.ingredient)
        self.assertEqual(self.recipe_ingredient.quantity, 200)

    def test_recipe_ingredient_str_method(self):
        """ Vérifie que `__str__()` retourne bien `Recette - Ingrédient (quantité)`"""
        expected_str = f"Cake - Farine (200g)"
        self.assertEqual(str(self.recipe_ingredient), expected_str)

    def test_recipe_ingredient_update(self):
        """ Vérifie que l'on peut modifier un RecipeIngredient"""
        self.recipe_ingredient.quantity = 300
        self.recipe_ingredient.save()
        self.recipe_ingredient.refresh_from_db()
        self.assertEqual(self.recipe_ingredient.quantity, 300)

    def test_recipe_ingredient_deletion(self):
        """ Vérifie que l'on peut supprimer un RecipeIngredient"""
        recipe_ingredient_id = self.recipe_ingredient.id
        self.recipe_ingredient.delete()
        self.assertFalse(RecipeIngredient.objects.filter(id=recipe_ingredient_id).exists())

    def test_recipe_ingredient_cannot_have_null_recipe(self):
        """ Vérifie qu'on ne peut pas créer un RecipeIngredient sans `recipe`"""
        with self.assertRaises(Exception):
            RecipeIngredient.objects.create(recipe=None, ingredient=self.ingredient, quantity=100)

    def test_recipe_ingredient_cannot_have_null_ingredient(self):
        """ Vérifie qu'on ne peut pas créer un RecipeIngredient sans `ingredient`"""
        with self.assertRaises(Exception):
            RecipeIngredient.objects.create(recipe=self.recipe, ingredient=None, quantity=100)

    def test_recipe_ingredient_cannot_have_null_quantity(self):
        """ Vérifie qu'on ne peut pas créer un RecipeIngredient sans `quantity`"""
        with self.assertRaises(Exception):
            RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.ingredient, quantity=None)

    def test_recipe_ingredient_must_have_positive_quantity(self):
        """ Vérifie que `quantity` doit être strictement positif"""
        with self.assertRaises(Exception):
            RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.ingredient, quantity=-10)

    def test_recipe_ingredient_must_not_have_zero_quantity(self):
        """ Vérifie qu'on ne peut PAS avoir une quantité de 0"""
        with self.assertRaises(Exception):
            RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.ingredient, quantity=0)
