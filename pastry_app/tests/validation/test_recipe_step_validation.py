from pastry_app.models import Recipe, RecipeStep
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeStepValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle RecipeStep"""
    model = RecipeStep
    model_name = "recipestep"

    def setUp(self):
        """Préparation : création d’une recette et d’une étape pour tester les validations"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Mousse au chocolat", chef="Chef Pierre")
        self.recipe_step = RecipeStep.objects.create(recipe=self.recipe, step_number=1, instruction="Faire fondre le chocolat.")

    def test_create_recipe_step_without_recipe(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeStep` sans `recipe`"""
        response = self.create_object({"step_number": 2, "instruction": "Ajouter les œufs."})  # Pas de `recipe`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipe", response.json())

    def test_create_recipe_step_without_step_number(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeStep` sans `step_number`"""
        response = self.create_object({"recipe": self.recipe.id, "instruction": "Ajouter les œufs."})  # Pas de `step_number`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("step_number", response.json())

    def test_create_recipe_step_without_instruction(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeStep` sans `instruction`"""
        response = self.create_object({"recipe": self.recipe.id, "step_number": 2})  # Pas de `instruction`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("instruction", response.json())

    def test_create_recipe_step_with_negative_step_number(self):
        """ Vérifie qu'on ne peut PAS créer un `RecipeStep` avec un `step_number` négatif"""
        response = self.create_object({"recipe": self.recipe.id, "step_number": -1, "instruction": "Ajouter du sucre."})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("step_number", response.json())

    def test_create_duplicate_step_number_in_same_recipe(self):
        """ Vérifie qu'on ne peut PAS créer deux `RecipeStep` avec le même `step_number` dans une recette"""
        response = self.create_object({"recipe": self.recipe.id, "step_number": 1, "instruction": "Battre les œufs."})  # Step 1 déjà existant
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("step_number", response.json())

    def test_get_nonexistent_recipe_step(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un `RecipeStep` qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_recipe_step(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un `RecipeStep` qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
