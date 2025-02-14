from django.test import TestCase
from pastry_app.models import Recipe, SubRecipe
from pastry_app.tests.utils import normalize_case

class SubRecipeModelTest(TestCase):
    """Tests unitaires du modèle SubRecipe"""

    def setUp(self):
        """Création d’une recette principale et d’une sous-recette pour tester le modèle"""
        self.recipe = Recipe.objects.create(recipe_name="Tarte au citron", chef="Chef Marie")
        self.sub_recipe = Recipe.objects.create(recipe_name="Pâte sablée", chef="Chef Marie")
        self.sub_recipe_link = SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=1)

    def test_subrecipe_creation(self):
        """ Vérifie que l'on peut créer un objet SubRecipe"""
        self.assertIsInstance(self.sub_recipe_link, SubRecipe)
        self.assertEqual(self.sub_recipe_link.recipe, self.recipe)
        self.assertEqual(self.sub_recipe_link.sub_recipe, self.sub_recipe)
        self.assertEqual(self.sub_recipe_link.quantity, 1)

    def test_subrecipe_str_method(self):
        """ Vérifie que `__str__()` retourne bien `Recette (quantité) -> Sous-recette`"""
        expected_str = f"Tarte au citron (1) -> Pâte sablée"
        self.assertEqual(str(self.sub_recipe_link), expected_str)

    def test_subrecipe_update(self):
        """ Vérifie que l'on peut modifier un SubRecipe"""
        self.sub_recipe_link.quantity = 3
        self.sub_recipe_link.save()
        self.sub_recipe_link.refresh_from_db()
        self.assertEqual(self.sub_recipe_link.quantity, 3)

    def test_subrecipe_deletion(self):
        """ Vérifie que l'on peut supprimer un SubRecipe"""
        subrecipe_id = self.sub_recipe_link.id
        self.sub_recipe_link.delete()
        self.assertFalse(SubRecipe.objects.filter(id=subrecipe_id).exists())

    def test_subrecipe_cannot_have_null_recipe(self):
        """ Vérifie qu'on ne peut pas créer un SubRecipe sans `recipe`"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=None, sub_recipe=self.sub_recipe, quantity=1)

    def test_subrecipe_cannot_have_null_sub_recipe(self):
        """ Vérifie qu'on ne peut pas créer un SubRecipe sans `sub_recipe`"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=self.recipe, sub_recipe=None, quantity=1)

    def test_subrecipe_cannot_have_null_quantity(self):
        """ Vérifie qu'on ne peut pas créer un SubRecipe sans `quantity`"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=None)

    def test_subrecipe_must_have_positive_quantity(self):
        """ Vérifie que `quantity` doit être strictement positif"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=-1)

    def test_subrecipe_must_not_have_zero_quantity(self):
        """ Vérifie qu'on ne peut PAS avoir une quantité de 0"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.sub_recipe, quantity=0)

    def test_subrecipe_recipe_cannot_be_equal_to_sub_recipe(self):
        """ Vérifie qu'on ne peut PAS avoir `recipe` et `sub_recipe` identiques"""
        with self.assertRaises(Exception):
            SubRecipe.objects.create(recipe=self.recipe, sub_recipe=self.recipe, quantity=1)
