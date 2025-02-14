from pastry_app.models import Ingredient, IngredientPrice
from ..base_api_test import BaseAPITest
from rest_framework import status

class IngredientPriceValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle IngredientPrice"""
    model = IngredientPrice
    model_name = "ingredientprice"

    def setUp(self):
        """Création d’un ingrédient pour tester les validations"""
        super().setUp()
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")

    def test_create_ingredient_price_without_ingredient(self):
        """ Vérifie qu'on ne peut PAS créer un IngredientPrice sans `ingredient`"""
        response = self.create_object({"store": "Supermarché A", "price": 2.5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ingredient", response.json())

    def test_create_ingredient_price_without_store(self):
        """ Vérifie qu'on ne peut PAS créer un IngredientPrice sans `store`"""
        response = self.create_object({"ingredient": self.ingredient.id, "price": 2.5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("store", response.json())

    def test_create_ingredient_price_without_price(self):
        """ Vérifie qu'on ne peut PAS créer un IngredientPrice sans `price`"""
        response = self.create_object({"ingredient": self.ingredient.id, "store": "Supermarché A"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.json())

    def test_create_ingredient_price_with_negative_price(self):
        """ Vérifie qu'on ne peut PAS créer un IngredientPrice avec un `price` négatif"""
        response = self.create_object({"ingredient": self.ingredient.id, "store": "Supermarché A", "price": -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.json())
