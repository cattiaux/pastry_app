from pastry_app.models import Ingredient, IngredientPrice
from ..base_api_test import BaseAPITest
from rest_framework import status

class IngredientPriceAPITest(BaseAPITest):
    """Test CRUD sur le modèle IngredientPrice"""
    model = IngredientPrice
    model_name = "ingredientprice"

    def setUp(self):
        """Création d’un ingrédient et d’un prix pour les tests"""
        super().setUp()
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")
        self.ingredient_price = IngredientPrice.objects.create(
            ingredient=self.ingredient, store="Supermarché A", price=2.5
        )

    def test_create_ingredient_price(self):
        """ Test de création d’un prix d’ingrédient"""
        response = self.create_object({
            "ingredient": self.ingredient.id, 
            "store": "Supermarché B", 
            "price": 3.0
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(IngredientPrice.objects.filter(store="Supermarché B", price=3.0).exists())

    def test_get_ingredient_price(self):
        """ Test de récupération d’un prix d’ingrédient"""
        response = self.get_object(self.ingredient_price.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("store"), "Supermarché A")

    def test_update_ingredient_price(self):
        """ Test de mise à jour d’un prix d’ingrédient"""
        response = self.update_object(self.ingredient_price.id, {
            "ingredient": self.ingredient.id, 
            "store": "Supermarché A", 
            "price": 2.8
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ingredient_price.refresh_from_db()
        self.assertEqual(self.ingredient_price.price, 2.8)

    def test_delete_ingredient_price(self):
        """ Test de suppression d’un prix d’ingrédient"""
        response = self.delete_object(self.ingredient_price.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(IngredientPrice.objects.filter(id=self.ingredient_price.id).exists())
