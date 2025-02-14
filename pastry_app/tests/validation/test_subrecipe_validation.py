from pastry_app.models import Recipe, SubRecipe
from ..base_api_test import BaseAPITest
from rest_framework import status

class SubRecipeValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle SubRecipe"""
    model = SubRecipe
    model_name = "subrecipe"

    def setUp(self):
        """Préparation : création d’une recette principale et d’une sous-recette pour tester les validations"""
        super().setUp()
        self.recipe = Recipe.objects.create(recipe_name="Tarte au citron", chef="Chef Marie")
        self.sub_recipe = Recipe.objects.create(recipe_name="Pâte sablée", chef="Chef Marie")
        self.sub_recipe_link = SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=1)

    def test_create_subrecipe_without_recipe(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` sans `recipe`"""
        response = self.create_object({"sub_recipe": self.sub_recipe.id, "quantity": 1})  # Pas de `recipe`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipe", response.json())

    def test_create_subrecipe_without_sub_recipe(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` sans `sub_recipe`"""
        response = self.create_object({"recipe": self.recipe.id, "quantity": 1})  # Pas de `sub_recipe`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sub_recipe", response.json())

    def test_create_subrecipe_without_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` sans `quantity`"""
        response = self.create_object({"recipe": self.recipe.id, "sub_recipe": self.sub_recipe.id})  # Pas de `quantity`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())

    def test_create_subrecipe_with_negative_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` avec une quantité négative"""
        response = self.create_object({"recipe": self.recipe.id, "sub_recipe": self.sub_recipe.id, "quantity": -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())

    def test_create_subrecipe_with_zero_quantity(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` avec une quantité de 0"""
        response = self.create_object({"recipe": self.recipe.id, "sub_recipe": self.sub_recipe.id, "quantity": 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.json())

    def test_create_subrecipe_with_same_recipe_as_subrecipe(self):
        """ Vérifie qu'on ne peut PAS créer un `SubRecipe` où `recipe` et `sub_recipe` sont identiques"""
        response = self.create_object({"recipe": self.recipe.id, "sub_recipe": self.recipe.id, "quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sub_recipe", response.json())

    def test_get_nonexistent_subrecipe(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un `SubRecipe` qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_subrecipe(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un `SubRecipe` qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
