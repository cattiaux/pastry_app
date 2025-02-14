from pastry_app.models import Recipe, Ingredient, RecipeIngredient
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeIngredientAPITest(BaseAPITest):
    """Test CRUD sur le modèle RecipeIngredient"""
    model = RecipeIngredient
    model_name = "recipeingredient"

    def setUp(self):
        """Création d’une recette et d’un ingrédient pour les tests"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Cake", chef="Chef Paul")
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")
        self.recipe_ingredient = RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.ingredient, quantity=200)

    def test_create_recipe_ingredient(self):
        """Test d’ajout d’un ingrédient à une recette"""
        response = self.create_object({
            "recipe": self.recipe.id, 
            "ingredient": self.ingredient.id, 
            "quantity": 300
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RecipeIngredient.objects.filter(recipe=self.recipe, ingredient=self.ingredient, quantity=300).exists())

    def test_get_recipe_ingredient(self):
        """Test de récupération d’un ingrédient lié à une recette"""
        response = self.get_object(self.recipe_ingredient.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.assertEqual(response.json().get("recipe"), self.recipe.id) 
        self.assertEqual(response.json().get("ingredient"), self.ingredient.id)  
        self.assertEqual(response.json().get("quantity"), 200) 

    def test_update_recipe_ingredient(self):
        """Test de mise à jour de la quantité d’un ingrédient dans une recette"""
        response = self.update_object(self.recipe_ingredient.id, {
            "recipe": self.recipe.id, 
            "ingredient": self.ingredient.id, 
            "quantity": 250
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.recipe_ingredient.refresh_from_db()
        self.assertEqual(self.recipe_ingredient.quantity, 250)

    def test_delete_recipe_ingredient(self):
        """Test de suppression d’un ingrédient d’une recette"""
        response = self.delete_object(self.recipe_ingredient.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT) 
        self.assertFalse(RecipeIngredient.objects.filter(id=self.recipe_ingredient.id).exists())
