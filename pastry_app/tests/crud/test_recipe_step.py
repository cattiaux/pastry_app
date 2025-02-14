from pastry_app.models import Recipe, RecipeStep
from ..base_api_test import BaseAPITest
from rest_framework import status

class RecipeStepAPITest(BaseAPITest):
    """Test CRUD sur le modèle RecipeStep"""
    model = RecipeStep
    model_name = "recipestep"

    def setUp(self):
        """Création d’une recette et d’une étape pour les tests"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Mousse au chocolat", chef="Chef Pierre")
        self.recipe_step = RecipeStep.objects.create(recipe=self.recipe, step_number=1, instruction="Faire fondre le chocolat.")

    def test_create_recipe_step(self):
        """Test de création d'une étape pour une recette"""
        response = self.create_object({
            "recipe": self.recipe.id, 
            "step_number": 2, 
            "instruction": "Ajouter les œufs et le sucre."
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RecipeStep.objects.filter(step_number=2, recipe=self.recipe).exists())

    def test_get_recipe_step(self):
        """Test de récupération d'une étape"""
        response = self.get_object(self.recipe_step.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK) 
        self.assertEqual(response.json().get("step_number"), 1) 
        self.assertEqual(response.json().get("instruction"), "Faire fondre le chocolat.") 

    def test_update_recipe_step(self):
        """Test de mise à jour d'une étape"""
        response = self.update_object(self.recipe_step.id, {
            "recipe": self.recipe.id, 
            "step_number": 1, 
            "instruction": "Faire fondre le chocolat au bain-marie."
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.recipe_step.refresh_from_db()
        self.assertEqual(self.recipe_step.instruction, "Faire fondre le chocolat au bain-marie.")

    def test_delete_recipe_step(self):
        """Test de suppression d'une étape"""
        response = self.delete_object(self.recipe_step.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)  
        self.assertFalse(RecipeStep.objects.filter(id=self.recipe_step.id).exists())
