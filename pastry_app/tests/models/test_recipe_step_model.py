import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Recipe, RecipeStep
from pastry_app.tests.utils import *


@pytest.fixture
def recipe():
    """Crée une recette par défaut pour tester les RecipeStep."""
    return Recipe.objects.create(recipe_name="Tarte aux fraises")

@pytest.fixture
def recipe_step(recipe):
    """Crée une première étape pour la recette."""
    return RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger la farine et le beurre.", trick="beurre mou")

@pytest.mark.django_db
def test_recipestep_creation(recipe_step):
    """Vérifie qu'on peut créer une étape valide."""
    assert isinstance(recipe_step, RecipeStep)
    assert recipe_step.recipe.step_name == "Tarte aux fraises"
    assert recipe_step.step_number == 1
    assert recipe_step.instruction == "Mélanger la farine et le beurre."

@pytest.mark.django_db
def test_recipestep_update(recipe_step):
    """ Vérifie que l'on peut modifier un RecipeStep"""
    # Sélectionner un RecipeStep différent de `recipe_step`
    new_instruction = "New Instruction"
    recipe_step.instruction = new_instruction
    recipe_step.save()
    recipe_step.refresh_from_db()
    assert recipe_step.instruction == new_instruction

@pytest.mark.django_db
def test_recipestep_deletion(recipe_step):
    """ Vérifie que l'on peut supprimer un RecipeStep"""
    recipe_step_id = recipe_step.id
    recipe_step.delete()
    assert not RecipeStep.objects.filter(id=recipe_step_id).exists()

@pytest.mark.django_db
def test_unique_constraint_recipestep(recipe_step):
    """Vérifie qu'on ne peut pas avoir deux `step_number` identiques dans une recette."""
    expected_error="Recipe step number must be unique within a recipe."
    validate_unique_together(RecipeStep, expected_error=expected_error, recipe=recipe_step.recipe, 
                             step_number=recipe_step.step_number, instruction="Autre instruction")

@pytest.mark.parametrize("field_name", ["instruction", "step_number"])
@pytest.mark.django_db
def test_required_fields_recipestep(field_name, recipe_step):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    for invalid_value in [None, ""]:
        validate_constraint(RecipeStep, field_name, invalid_value, "field cannot be null", recipe=recipe_step.recipe)

@pytest.mark.parametrize(("field_name", "invalid_step_number"), ("step_number", [0, -1]))
@pytest.mark.django_db
def test_step_number_must_start_at_1(recipe, field_name, invalid_step_number):
    """Vérifie que `step_number` ne peut pas être inférieur à 1."""
    expected_error="Step number must start at 1."
    validate_constraint(RecipeStep, field_name, value=invalid_step_number, 
                        expected_error=expected_error, recipe=recipe, instruction="Étape invalide.")

@pytest.mark.django_db
def test_step_number_must_be_strictly_increasing(recipe_step):
    """Vérifie que les numéros d'étape doivent être consécutifs."""
    # la fixture recipe_step crée déjà un premier recipe_step
    expected_error="Step numbers must be consecutive."
    validate_constraint(RecipeStep, field_name="step_number", value=recipe_step.step_number+5, expected_error=expected_error, 
                        recipe=recipe_step.recipe, instruction="Étape sautée.")

@pytest.mark.parametrize("instruction", ["A", ""])
@pytest.mark.django_db
def test_min_length_instruction_recipestep(instruction, recipe_step):
    """Vérifie que `instruction` doit avoir au moins 2 caractères."""
    min_length = 2
    expected_error="Instruction must be at least 2 characters long."
    validate_constraint(RecipeStep, instruction, "A" * (min_length - 1), expected_error, recipe=recipe_step.recipe, step_number=1)

@pytest.mark.parametrize("field_name", ["trick"])
@pytest.mark.django_db
def test_optional_field_recipestep(field_name, recipe_step):
    """Vérifie que `trick` est bien un champ optionnel (`None` ou `""`)."""
    validate_optional_field_value_db(RecipeStep, field_name, recipe=recipe_step.recipe, step_number=1, instruction="Mélanger.")

@pytest.mark.django_db
def test_deleting_step_reorders_steps(recipe_step):
    """Vérifie que supprimer une étape réorganise les `step_number`."""
    # L'instance step1 est créé par la fixture recipe_step
    step2 = RecipeStep.objects.create(recipe=recipe_step.recipe, step_number=2, instruction="Deuxième étape.")
    step3 = RecipeStep.objects.create(recipe=recipe_step.recipe, step_number=3, instruction="Troisième étape.")

    step2.delete()  # Suppression de l'étape 2

    # Vérifier que l'étape 3 est maintenant l'étape 2
    step_remaining = RecipeStep.objects.get(recipe=recipe_step.recipe, step_number=2)
    assert step_remaining.instruction == "Troisième étape."

@pytest.mark.django_db
def test_cannot_delete_last_recipe_step(recipe_step):
    """Vérifie qu'on ne peut pas supprimer le dernier `RecipeStep` d'une recette."""
    with pytest.raises(ValidationError, match="A recipe must have at least one step."):
        recipe_step.delete()  # Devrait lever une erreur














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
