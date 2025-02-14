from pastry_app.models import Recipe, SubRecipe
from ..base_api_test import BaseAPITest
from rest_framework import status

class SubRecipeAPITest(BaseAPITest):
    """Test CRUD sur le modèle SubRecipe"""
    model = SubRecipe
    model_name = "subrecipe"

    def setUp(self):
        """Création d’une recette principale avec une sous-recette pour les tests"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Tarte au citron", chef="Chef Marie")
        self.sub_recipe = Recipe.objects.create(recipe_name="Pâte sablée", chef="Chef Marie")
        self.sub_recipe_link = SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=1)

    def test_create_subrecipe(self):
        """Test d'ajout d'une sous-recette à une recette"""
        new_sub_recipe = {"recipe": self.recipe.id, "sub_recipe": self.sub_recipe.id, "quantity": 2}
        response = self.create_object(new_sub_recipe)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SubRecipe.objects.filter(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=2).exists())

    def test_get_subrecipe(self):
        """Test de récupération d'une sous-recette"""
        response = self.get_object(self.sub_recipe_link.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Correction : utilisation de status.HTTP_200_OK
        self.assertEqual(response.json().get("recipe"), self.recipe.id)  # Vérification de la recette principale
        self.assertEqual(response.json().get("sub_recipe"), self.sub_recipe.id)  # Vérification de la sous-recette
        self.assertEqual(response.json().get("quantity"), 1)  # Vérification de la quantité

    def test_update_subrecipe(self):
        """Test de mise à jour de la quantité d'une sous-recette"""
        updated_data = {"recipe": self.recipe.id, "sub_recipe": self.sub_recipe.id, "quantity": 3}
        response = self.update_object(self.sub_recipe_link.id, updated_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Correction : utilisation de status.HTTP_200_OK
        self.sub_recipe_link.refresh_from_db()
        self.assertEqual(self.sub_recipe_link.quantity, 3)

    def test_delete_subrecipe(self):
        """Test de suppression d'une sous-recette"""
        response = self.delete_object(self.sub_recipe_link.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)  # Vérification standard des suppressions
        self.assertFalse(SubRecipe.objects.filter(id=self.sub_recipe_link.id).exists())
