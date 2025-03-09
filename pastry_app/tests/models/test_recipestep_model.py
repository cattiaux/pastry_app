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
    assert recipe_step.recipe.recipe_name == normalize_case("Tarte aux fraises")
    assert recipe_step.step_number == 1
    assert recipe_step.instruction == "Mélanger la farine et le beurre."

@pytest.mark.django_db
def test_recipestep_update(recipe_step):
    """ Vérifie que l'on peut modifier un RecipeStep"""
    new_instruction = "New Instruction"
    recipe_step.instruction = new_instruction
    recipe_step.save()
    recipe_step.refresh_from_db()
    assert recipe_step.instruction == new_instruction

@pytest.mark.django_db
def test_recipestep_deletion(recipe, recipe_step):
    """ Vérifie que l'on peut supprimer un RecipeStep"""
    new_step = RecipeStep.objects.create(recipe=recipe, step_number=2, instruction="Ajouter le chocolat.")
    recipe_step_id = new_step.id
    new_step.delete()
    assert not RecipeStep.objects.filter(id=recipe_step_id).exists()

@pytest.mark.django_db
def test_cannot_delete_last_recipe_step(recipe_step):
    """Vérifie qu'on ne peut pas supprimer le dernier `RecipeStep` d'une recette."""
    with pytest.raises(ValidationError, match="A recipe must have at least one step."):
        recipe_step.delete()  # Devrait lever une erreur

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
def test_unique_constraint_recipestep(recipe_step):
    """Vérifie qu'on ne peut pas avoir deux `step_number` identiques dans une recette."""
    expected_error = "Recipe step with this Recipe and Step number already exists."
    # Vérifier que la validation empêche un doublon dès `save()`
    duplicate_step = RecipeStep(recipe=recipe_step.recipe, step_number=recipe_step.step_number,  # Même numéro d'étape
                                 instruction="Autre instruction")

    with pytest.raises(ValidationError) as excinfo:
        duplicate_step.full_clean()  # Déclenche la validation avant le save()

    error_messages = excinfo.value.message_dict.get("__all__", []) # Extraire le message d'erreur Django
    # Vérifier que l'erreur attendue est bien présente
    assert expected_error in error_messages, (f"Erreur attendue '{expected_error}' non trouvée dans '{error_messages}'")

@pytest.mark.parametrize("field_name", ["recipe", "instruction", "step_number"])
@pytest.mark.django_db
def test_required_fields_recipestep(field_name, recipe_step):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    # Si le champ est un `ForeignKey` ou `IntegerField`, on ne teste que `None`
    invalid_values = [None] if field_name in ["recipe", "step_number"] else [None, ""]
    for invalid_value in invalid_values:
        validate_constraint(RecipeStep, field_name, invalid_value, "field cannot be null")#, recipe=recipe_step.recipe)

@pytest.mark.parametrize(("field_name", "invalid_value"), [("step_number", 0), ("step_number", -1)])
@pytest.mark.django_db
def test_step_number_must_start_at_1(recipe, field_name, invalid_value):
    """Vérifie que `step_number` ne peut pas être inférieur à 1."""
    expected_error="Step number must start at 1."
    validate_constraint(RecipeStep, field_name, invalid_value, expected_error, 
                        recipe=recipe, instruction="Étape invalide.")

@pytest.mark.django_db
def test_step_number_must_be_strictly_increasing(recipe_step):
    """Vérifie que les numéros d'étape doivent être consécutifs."""
    # la fixture recipe_step crée déjà un premier recipe_step
    expected_error="Step numbers must be consecutive."
    validate_constraint(RecipeStep, "step_number", recipe_step.step_number+5, expected_error, 
                        recipe=recipe_step.recipe, instruction="Étape sautée.")

@pytest.mark.parametrize("instruction", ["A", ""])
@pytest.mark.django_db
def test_min_length_instruction_recipestep(instruction, recipe_step):
    """Vérifie que `instruction` doit avoir au moins 2 caractères."""
    min_length = 2
    expected_error="Instruction must be at least 2 characters long."
    validate_constraint(RecipeStep, "instruction", "A" * (min_length - 1), expected_error, recipe=recipe_step.recipe, step_number=1)

# @pytest.mark.parametrize("field_name", ["trick"])
# @pytest.mark.django_db
# def test_optional_field_recipestep(field_name, recipe_step):
#     """Vérifie que `trick` est bien un champ optionnel (`None` ou `""`)."""
#     validate_optional_field_value_db(RecipeStep, field_name, recipe=recipe_step.recipe, step_number=1, instruction="Mélanger.")

@pytest.mark.parametrize("field_name", ["trick"])
@pytest.mark.django_db
def test_optional_field_recipestep(field_name, recipe_step):
    """Vérifie que `trick` est bien un champ optionnel (`None` ou `""`)."""
    for i, value in enumerate(["", None], start=1):  # Incrémente `step_number` à chaque itération
        obj = RecipeStep.objects.create(recipe=recipe_step.recipe, 
                                        step_number=recipe_step.step_number + i,  # `step_number` unique à chaque itération 
                                        instruction="Mélanger.", **{field_name: value})
        obj.refresh_from_db()
        assert getattr(obj, field_name) == value, (f"Erreur sur {field_name}: attendu `{value}`, obtenu `{getattr(obj, field_name)}`")

@pytest.mark.django_db
def test_step_number_auto_increment(recipe):
    """Vérifie que `step_number` est auto-incrémenté s’il n’est pas précisé."""
    step1 = RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Première étape.")
    step2 = RecipeStep.objects.create(recipe=recipe, instruction="Deuxième étape.")  # `step_number` absent
    assert step2.step_number == step1.step_number + 1  # Vérifie que step2 = 2