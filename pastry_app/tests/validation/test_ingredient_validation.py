from pastry_app.models import Ingredient
from ..base_api_test import BaseAPITest
from rest_framework import status

class IngredientValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle Ingredient"""
    model = Ingredient
    model_name = "ingredient"

    def setUp(self):
        """Préparation : création d’un ingrédient pour tester les doublons"""
        super().setUp()
        self.ingredient = Ingredient.objects.create(ingredient_name="Chocolat")

    def test_create_ingredient_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un ingrédient sans `ingredient_name`"""
        response = self.create_object({})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("ingredient_name", response.json())  # Vérifie que le message d'erreur mentionne le champ manquant

    def test_create_duplicate_ingredient(self):
        """ Vérifie qu'on ne peut PAS créer deux ingrédients avec le même `ingredient_name`"""
        response = self.create_object({"ingredient_name": "Chocolat"})  # "Chocolat" existe déjà
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("ingredient_name", response.json())  # Vérifie que l'erreur concerne bien le champ `ingredient_name`

    def test_update_ingredient_to_duplicate(self):
        """ Vérifie qu'on ne peut PAS modifier un ingrédient en lui donnant un `ingredient_name` déjà existant"""
        ingredient2 = Ingredient.objects.create(ingredient_name="Vanille")  # Créer un autre ingrédient
        response = self.update_object(ingredient2.id, {"ingredient_name": "Chocolat"})  # Essaye de changer "Vanille" en "Chocolat"
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("ingredient_name", response.json())  # Vérifie que l'erreur concerne bien `ingredient_name`

    def test_get_nonexistent_ingredient(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un ingrédient qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404

    def test_delete_nonexistent_ingredient(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un ingrédient qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404
