from pastry_app.models import Recipe
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle Recipe"""
    model = Recipe
    model_name = "recipe"

    def setUp(self):
        """Préparation : création d’une recette pour tester les doublons"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Tarte aux pommes", chef="Chef Pierre")

    def test_create_recipe_without_name(self):
        """ Vérifie qu'on ne peut PAS créer une recette sans `recipe_name`"""
        response = self.create_object({"chef": "Chef Pierre"})  # Pas de `recipe_name`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("recipe_name", response.json())  # Vérifie que l'erreur mentionne `recipe_name`

    def test_create_recipe_without_chef(self):
        """ Vérifie qu'on ne peut PAS créer une recette sans `chef`"""
        response = self.create_object({"recipe_name": "Mousse au chocolat"})  # Pas de `chef`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("chef", response.json())  # Vérifie que l'erreur mentionne `chef`

    def test_create_duplicate_recipe(self):
        """ Vérifie qu'on ne peut PAS créer deux recettes avec le même `recipe_name` pour le même `chef`"""
        response = self.create_object({"recipe_name": "Tarte aux pommes", "chef": "Chef Pierre"})  # Déjà existant
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("recipe_name", response.json())  # Vérifie que l'erreur mentionne bien `recipe_name`

    def test_update_recipe_to_duplicate(self):
        """ Vérifie qu'on ne peut PAS modifier une recette pour lui donner un `recipe_name` déjà existant"""
        recipe2 = Recipe.objects.create(recipe_name="Mousse au chocolat", chef="Chef Marie")
        response = self.update_object(recipe2.id, {"recipe_name": "Tarte aux pommes", "chef": "Chef Pierre"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("recipe_name", response.json())  # Vérifie que l'erreur mentionne bien `recipe_name`

    def test_get_nonexistent_recipe(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une recette qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404

    def test_delete_nonexistent_recipe(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une recette qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404
