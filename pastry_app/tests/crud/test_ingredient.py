from pastry_app.models import Ingredient
from ..base_api_test import BaseAPITest
from rest_framework import status

class IngredientAPITest(BaseAPITest):
    """Test CRUD sur le modèle Ingredient"""
    model = Ingredient
    model_name = "ingredient"

    def setUp(self):
        """Création d’un ingrédient pour les tests"""
        super().setUp()
        self.ingredient = Ingredient.objects.create(ingredient_name="Chocolat")

    def test_create_ingredient(self):
        """Test de création d’un ingrédient"""
        response = self.create_object({"ingredient_name": "Vanille"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Ingredient.objects.filter(ingredient_name="Vanille").exists())

    def test_get_ingredient(self):
        """Test de récupération d’un ingrédient"""
        response = self.get_object(self.ingredient.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK) 
        self.assertEqual(response.json().get("ingredient_name"), "Chocolat")

    def test_update_ingredient(self):
        """Test de mise à jour d’un ingrédient"""
        response = self.update_object(self.ingredient.id, {"ingredient_name": "Chocolat Noir"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.ingredient_name, "Chocolat Noir")

    def test_delete_ingredient(self):
        """Test de suppression d’un ingrédient"""
        response = self.delete_object(self.ingredient.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Ingredient.objects.filter(id=self.ingredient.id).exists())

