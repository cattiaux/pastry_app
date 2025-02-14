from pastry_app.models import Recipe
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeAPITest(BaseAPITest):
    """Test CRUD sur le modèle Recipe"""
    model = Recipe
    model_name = "recipe"

    def setUp(self):
        """Création d’une recette pour les tests"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Tarte aux pommes", chef="Chef Pierre")

    def test_create_recipe(self):
        """Test de création d’une recette"""
        response = self.create_object({"recipe_name": "Brownie", "chef": "Chef Marie"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Recipe.objects.filter(recipe_name="Brownie").exists())

    def test_get_recipe(self):
        """Test de récupération d’une recette"""
        response = self.get_object(self.recipe.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.assertEqual(response.json().get("recipe_name"), "Tarte aux pommes") 
        self.assertEqual(response.json().get("chef"), "Chef Pierre") 

    def test_update_recipe(self):
        """Test de mise à jour d’une recette"""
        response = self.update_object(self.recipe.id, {"recipe_name": "Tarte aux poires", "chef": "Chef Pierre"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.recipe_name, "Tarte aux poires")

    def test_delete_recipe(self):
        """Test de suppression d’une recette"""
        response = self.delete_object(self.recipe.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT) 
        self.assertFalse(Recipe.objects.filter(id=self.recipe.id).exists())
