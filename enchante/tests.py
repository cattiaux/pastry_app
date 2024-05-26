from django.test import TestCase, Client
from django.urls import reverse
from .models import Recipe, Ingredient, Pan, RoundPan, SquarePan
from .serializers import RecipeSerializer, IngredientSerializer, PanSerializer, RoundPanSerializer, SquarePanSerializer

class RecipeModelTest(TestCase):
    def setUp(self):
        self.recipe = Recipe.objects.create(recipe_name='Test Recipe', chef='Test Chef')

    def test_recipe_creation(self):
        self.assertIsInstance(self.recipe, Recipe)
        self.assertEqual(self.recipe.__str__(), 'Test Recipe')

class IngredientModelTest(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(ingredient_name='Test Ingredient')

    def test_ingredient_creation(self):
        self.assertIsInstance(self.ingredient, Ingredient)
        self.assertEqual(self.ingredient.__str__(), 'Test Ingredient')

class RecipeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.recipe = Recipe.objects.create(recipe_name='Test Recipe', chef='Test Chef')

    def test_get_recipe(self):
        response = self.client.get(reverse('recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Recipe')

    def test_update_recipe(self):
        response = self.client.put(reverse('recipe-detail', args=[self.recipe.id]), {
            'recipe_name': 'Updated Recipe',
            'chef': 'Updated Chef',
        })
        self.assertEqual(response.status_code, 200)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.recipe_name, 'Updated Recipe')
        self.assertEqual(self.recipe.chef, 'Updated Chef')

    def test_delete_recipe(self):
        response = self.client.delete(reverse('recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Recipe.objects.filter(id=self.recipe.id).exists())

class IngredientViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.ingredient = Ingredient.objects.create(ingredient_name='Test Ingredient')

    def test_get_ingredient(self):
        response = self.client.get(reverse('ingredient-detail', args=[self.ingredient.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Ingredient')

    def test_update_ingredient(self):
        response = self.client.put(reverse('ingredient-detail', args=[self.ingredient.id]), {
            'ingredient_name': 'Updated Ingredient',
        })
        self.assertEqual(response.status_code, 200)
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.ingredient_name, 'Updated Ingredient')

    def test_delete_ingredient(self):
        response = self.client.delete(reverse('ingredient-detail', args=[self.ingredient.id]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Ingredient.objects.filter(id=self.ingredient.id).exists())
