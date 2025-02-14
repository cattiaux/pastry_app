from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeIngredientValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle RecipeIngredient"""
    model = RecipeIngredient
    model_name = "recipeingredient"

    def setUp(self):
        """Préparation : création d’une recette et d’un ingrédient pour tester les validations"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Cake", chef="Chef Paul")
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")
        self.recipe_ingredient = RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.ingredient, quantity=200)

    def test_create_recipe_ingredient_without_recipe(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeIngredient` sans `recipe`"""
        response = self.create_object({"ingredient": self.ingredient.id, "quantity": 100})  # Pas de `recipe`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipe", response.json())

    def test_create_recipe_ingredient_without_ingredient(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeIngredient` sans `ingredient`"""
        response = self.create_object({"recipe": self.recipe.id, "quantity": 100})  # Pas de `ingredient`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ingredient", response.json())

    def test_create_recipe_ingredient_without_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeIngredient` sans `quantity`"""
        response = self.create_object({"recipe": self.recipe.id, "ingredient": self.ingredient.id})  # Pas de `quantity`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())

    def test_create_recipe_ingredient_with_negative_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeIngredient` avec une quantité négative"""
        response = self.create_object({"recipe": self.recipe.id, "ingredient": self.ingredient.id, "quantity": -10})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())  # Vérifie que l'erreur concerne `quantity`

    def test_create_recipe_ingredient_with_zero_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeIngredient` avec une quantité de 0"""
        response = self.create_object({"recipe": self.recipe.id, "ingredient": self.ingredient.id, "quantity": 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())  # Vérifie que l'erreur concerne `quantity`

    def test_get_nonexistent_recipe_ingredient(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un `RecipeIngredient` qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_recipe_ingredient(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un `RecipeIngredient` qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
