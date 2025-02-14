from django.test import TestCase
from pastry_app.models import Recipe, RecipeStep
from pastry_app.tests.utils import normalize_case

class RecipeStepModelTest(TestCase):
    """Tests unitaires du modèle RecipeStep"""

    def setUp(self):
        """Création d’une recette et d’une étape pour tester le modèle"""
        self.recipe = Recipe.objects.create(recipe_name="Mousse au chocolat", chef="Chef Pierre")
        self.recipe_step = RecipeStep.objects.create(recipe=self.recipe, step_number=1, instruction="Faire fondre le chocolat.")

    def test_recipe_step_creation(self):
        """ Vérifie que l'on peut créer un objet RecipeStep"""
        self.assertIsInstance(self.recipe_step, RecipeStep)
        self.assertEqual(self.recipe_step.recipe, self.recipe)
        self.assertEqual(self.recipe_step.step_number, 1)
        self.assertEqual(self.recipe_step.instruction, normalize_case("Faire fondre le chocolat."))

    def test_recipe_step_str_method(self):
        """ Vérifie que `__str__()` retourne bien `Recipe - Étape X`"""
        self.assertEqual(str(self.recipe_step), normalize_case("Mousse au chocolat - Étape 1"))

    def test_recipe_step_update(self):
        """ Vérifie que l'on peut modifier un RecipeStep"""
        self.recipe_step.instruction = "Faire fondre le chocolat au bain-marie."
        self.recipe_step.save()
        self.recipe_step.refresh_from_db()
        self.assertEqual(self.recipe_step.instruction, normalize_case("Faire fondre le chocolat au bain-marie."))

    def test_recipe_step_deletion(self):
        """ Vérifie que l'on peut supprimer un RecipeStep"""
        step_id = self.recipe_step.id
        self.recipe_step.delete()
        self.assertFalse(RecipeStep.objects.filter(id=step_id).exists())

    def test_recipe_step_cannot_have_null_recipe(self):
        """ Vérifie qu'on ne peut pas créer un RecipeStep sans `recipe`"""
        with self.assertRaises(Exception):
            RecipeStep.objects.create(recipe=None, step_number=2, instruction="Ajouter les œufs.")

    def test_recipe_step_cannot_have_null_step_number(self):
        """ Vérifie qu'on ne peut pas créer un RecipeStep sans `step_number`"""
        with self.assertRaises(Exception):
            RecipeStep.objects.create(recipe=self.recipe, step_number=None, instruction="Ajouter les œufs.")

    def test_recipe_step_cannot_have_null_instruction(self):
        """ Vérifie qu'on ne peut pas créer un RecipeStep sans `instruction`"""
        with self.assertRaises(Exception):
            RecipeStep.objects.create(recipe=self.recipe, step_number=2, instruction=None)

    def test_recipe_step_must_have_positive_step_number(self):
        """ Vérifie que `step_number` doit être strictement positif"""
        with self.assertRaises(Exception):
            RecipeStep.objects.create(recipe=self.recipe, step_number=-1, instruction="Ajouter du sucre.")

    def test_recipe_step_must_be_unique_per_recipe(self):
        """ Vérifie qu'on ne peut pas avoir deux RecipeStep avec le même `step_number` dans une recette"""
        with self.assertRaises(Exception):
            RecipeStep.objects.create(recipe=self.recipe, step_number=1, instruction="Battre les œufs.")
