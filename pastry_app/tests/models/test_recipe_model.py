import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from pastry_app.models import Recipe, Pan, RecipeIngredient, Ingredient, RecipeStep, UserRecipeVisibility
from pastry_app.tests.utils import validate_constraint, validate_field_normalization, normalize_case

pytestmark = pytest.mark.django_db

User = get_user_model()

# --- Fixtures hybrides ---

@pytest.fixture
def pan():
    return Pan.objects.create(pan_name="Cercle 18cm", pan_type="ROUND", diameter=18, height=4.5, units_in_mold=1)

@pytest.fixture
def recipe(pan):
    recipe = Recipe.objects.create(recipe_name="Recette Démo", chef_name="Chef Démo", recipe_type="BASE", servings_min=6, servings_max=6, 
                                   pan=pan, description="Une recette complète pour les tests", trick="Cuire doucement")
    # Ajout d’un ingrédient
    ingredient = Ingredient.objects.create(ingredient_name="Test Ingredient")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=100, unit="g")
    # Ajout d’une étape
    RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger la farine et le sucre.")
    return recipe

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

# --- Tests de validation modèle ---

def test_recipe_creation_db(recipe):
    """Vérifie qu'on peut créer une recette valide avec le minimum requis."""
    assert recipe.id is not None
    assert str(recipe) == normalize_case("Recette Démo (Chef Démo)")

def test_recipe_update_db(recipe):
    """Vérifie qu'on peut modifier un champ texte de la recette."""
    recipe.description = "Nouvelle description"
    recipe.save()
    recipe.refresh_from_db()
    assert recipe.description == "Nouvelle description"

def test_recipe_str_method(recipe):
    assert str(recipe) == normalize_case("Recette Démo (Chef Démo)")

def test_unique_constraint_recipe_db(recipe, pan):
    """Vérifie qu'on ne peut pas créer deux recettes avec le même nom, chef, contexte et source."""
    with pytest.raises(Exception) as exc_info:
        Recipe.objects.create(recipe_name=recipe.recipe_name, chef_name=recipe.chef_name, recipe_type=recipe.recipe_type, 
                              context_name=recipe.context_name, source=recipe.source, servings_min=6, servings_max=8, pan=pan)
    assert "Il existe déjà une recette de ce nom et chef sans contexte." in str(exc_info.value)

@pytest.mark.parametrize("field_name, raw_value", [("recipe_name", "  TARTE citron  "), 
                                                   ("chef_name", "  cédric GROLET "), 
                                                   ("context_name", "  INSTAGRAM "), 
                                                   ("source", "  www.site.com  ")])
def test_normalized_fields_recipe_db(field_name, raw_value, pan):
    """Vérifie que les champs textuels sont bien normalisés avant sauvegarde."""
    validate_field_normalization(Recipe, field_name, raw_value, recipe_name="Tarte Poire", chef_name="Chef T", 
                                 recipe_type="BASE", servings_min=4, servings_max=4, pan=pan)

@pytest.mark.parametrize("field_name, min_length", [("description", 10), ("trick", 10), ("context_name", 3), ("source", 3)])
def test_min_length_fields_recipe_db(field_name, min_length, pan):
    validate_constraint(Recipe, field_name, "a" * (min_length - 1), "doit contenir au moins", 
                        recipe_name="Test recette", chef_name="Test chef", recipe_type="BASE", 
                        servings_min=4, servings_max=4, pan=pan)

@pytest.mark.parametrize("field_name", ["recipe_name", "chef_name", "recipe_type"])
def test_required_fields_recipe_db(field_name, pan):
    """Vérifie que les champs obligatoires ne peuvent pas être vides ou nuls."""
    for invalid_value in [None, ""]:
        validate_constraint(Recipe, field_name, invalid_value, "obligatoire", chef_name="Chef T", recipe_name="Tarte", 
                            recipe_type="BASE", servings_min=4, servings_max=4, pan=pan)

def test_pan_is_optional_recipe_db():
    """Vérifie qu'une recette peut être créée sans pan."""
    recipe = Recipe(recipe_name="Tarte Fruits", chef_name="Chef Libre", recipe_type="BASE", servings_min=4, servings_max=6, pan=None)
    recipe.full_clean()  # Ne doit pas lever d'erreur
    recipe.save()
    assert recipe.id is not None

@pytest.mark.parametrize("field_name, invalid_value", [("servings_min", 0), ("servings_max", -1)])
def test_servings_must_be_positive_recipe_db(field_name, invalid_value):
    validate_constraint(model=Recipe, field_name=field_name, value=invalid_value, expected_errors=["doit être supérieur à 0"], 
                        recipe_name="Gâteau Test", chef_name="Chef Test")

@pytest.mark.parametrize("s_min, s_max, should_raise", [(None, None, False), (6, 6, False), (4, 8, False), (10, 6, True)])
def test_servings_min_max_coherence_recipe_db(recipe, s_min, s_max, should_raise):
    recipe.servings_min = s_min
    recipe.servings_max = s_max
    if should_raise:
        with pytest.raises(ValidationError):
            recipe.full_clean()
    else:
        recipe.full_clean()

def test_parent_recipe_cannot_be_itself_db(recipe):
    recipe.parent_recipe = recipe
    recipe.recipe_type = "VARIATION"
    with pytest.raises(ValidationError, match="sa propre version précédente"):
        recipe.full_clean()

def test_cycle_detection_db(recipe):
    child = Recipe.objects.create(recipe_name="Child", chef_name="Chef", recipe_type="VARIATION",
                                  servings_min=4, servings_max=4, parent_recipe=recipe, pan=recipe.pan)
    recipe.parent_recipe = child
    recipe.recipe_type = "VARIATION"
    with pytest.raises(ValidationError, match="Cycle détecté"):
        recipe.full_clean()

def test_auto_fill_servings_from_pan_db(recipe):
    """Vérifie que servings_min et servings_max sont générés automatiquement si absents mais pan défini."""
    recipe.servings_min = None
    recipe.servings_max = None
    recipe.full_clean()
    assert recipe.servings_min == recipe.pan.units_in_mold
    assert recipe.servings_max == recipe.pan.units_in_mold

def test_context_is_auto_filled_if_missing(recipe):
    """Vérifie que context_name est automatiquement généré à partir de parent_recipe si manquant."""
    child = Recipe.objects.create(recipe_name="Tarte Citron revisitée", chef_name="Chef Junior", recipe_type="VARIATION", 
                                  servings_min=4, servings_max=4, parent_recipe=recipe, pan=recipe.pan)
    assert child.context_name == f"Variante de {recipe.recipe_name}"

def test_recipe_without_ingredients_and_subrecipes_is_invalid(recipe):
    """Vérifie qu'une recette sans ingrédient ni sous-recette est invalide (même avec une étape)."""
    recipe.recipe_ingredients.all().delete()
    recipe.main_recipes.all().delete()
    # On garde au moins une étape
    with pytest.raises(ValidationError, match="au moins un ingrédient ou une sous-recette"):
        recipe.full_clean()

def test_recipe_without_steps_is_invalid(recipe):
    """Vérifie qu'une recette sans étape est invalide (même si elle a un ingrédient)."""
    # Ajouter une étape temporaire pour pouvoir supprimer l’autre sans déclencher le signal
    RecipeStep.objects.create(recipe=recipe, step_number=2, instruction="temporaire")
    # Supprimer toutes les étapes
    recipe.steps.all().delete()
    # Valider le modèle
    with pytest.raises(ValidationError, match="au moins une étape"):
        recipe.full_clean()

@pytest.mark.parametrize("only_min, only_max", [(6, None), (None, 8)])
def test_auto_copy_servings_recipe_db(recipe, only_min, only_max):
    """Vérifie que si un seul servings est fourni, l'autre est automatiquement copié."""
    recipe.servings_min = only_min
    recipe.servings_max = only_max
    recipe.full_clean()
    if only_min:
        assert recipe.servings_max == only_min
    if only_max:
        assert recipe.servings_min == only_max

def test_custom_pan_with_total_volume(pan):
    """Vérifie que si volume_total est explicitement déclaré, il n'est pas multiplié par `units_in_mold`."""
    pan.pan_type = "CUSTOM"
    pan.volume_raw = 600
    pan.unit = "cm3"
    pan.is_total_volume = True
    pan.units_in_mold = 6
    pan.clean()
    assert pan.volume_cm3 == 600  # Pas multiplié

def test_servings_are_scaled_by_pan_quantity(recipe):
    """Vérifie qu'une recette utilisant plusieurs exemplaires du même moule ajuste correctement les servings."""
    recipe.pan_quantity = 3
    recipe.servings_min = None
    recipe.servings_max = None
    recipe.full_clean()
    assert recipe.servings_min == recipe.pan.units_in_mold * 3
    assert recipe.servings_max == recipe.pan.units_in_mold * 3

@pytest.mark.parametrize("existing_context,new_context", [(None, ""), ("", None)])
def test_no_duplicate_recipe_same_name_chef_no_context(existing_context, new_context, pan):
    """Impossible de créer deux recettes même nom/chef avec context_name vide ou null."""
    Recipe.objects.create(recipe_name="Flan", chef_name="Michalak", recipe_type="BASE", servings_min=6, servings_max=6, pan=pan, context_name=existing_context)
    with pytest.raises(ValidationError, match="Il existe déjà une recette de ce nom et chef sans contexte"):
        r = Recipe(recipe_name="Flan", chef_name="Michalak", recipe_type="BASE", servings_min=6, servings_max=6, pan=pan, context_name=new_context)
        r.full_clean()

@pytest.mark.parametrize("data,expected_msg", [
    ({"recipe_type": "VARIATION", "parent_recipe": None, "adaptation_note": None}, "doit avoir une parent_recipe"),
    ({"recipe_type": "BASE", "parent_recipe": 1, "adaptation_note": None}, "doit être de type VARIATION"),
    ({"recipe_type": "BASE", "parent_recipe": None, "adaptation_note": "Adaptation"}, "Ce champ n'est permis que pour une adaptation"),
])
def test_recipe_adaptation_rules(recipe, pan, data, expected_msg):
    """Vérifie les règles d'adaptation (VARIATION, parent_recipe, adaptation_note)."""
    # On récupère une recette existante pour tester parent_recipe
    parent = recipe if data.get("parent_recipe") else None
    r = Recipe(
        recipe_name="Recette Test", chef_name="Chef Test",
        servings_min=1, servings_max=1, pan=pan,
        recipe_type=data["recipe_type"],
        parent_recipe=parent,
        adaptation_note=data.get("adaptation_note"),
    )
    with pytest.raises(ValidationError, match=expected_msg):
        r.full_clean()

def test_valid_variation_with_adaptation_note(recipe, pan):
    """VARIATION avec parent_recipe ET adaptation_note : OK."""
    r = Recipe(recipe_name="Variante Flan", chef_name="Michalak", recipe_type="VARIATION", servings_min=3, servings_max=3, 
               pan=pan, parent_recipe=recipe, adaptation_note="Test")
    r.full_clean()
    r.save()
    assert r.id is not None

# --- test pour UserRecipeVisibility ---

@pytest.mark.parametrize(
    "with_user, with_guest_id, should_raise",
    [
        (True,  True,  True),   # Les deux → doit lever une erreur
        (True,  False, False),  # Uniquement user → ok
        (False, True,  False),  # Uniquement guest → ok
        (False, False, False),  # Aucun → ok
    ]
)
def test_recipe_user_and_guest_id(user, with_user, with_guest_id, should_raise):
    user_instance = user if with_user else None
    guest_value = "guestid-xyz" if with_guest_id else None
    recipe = Recipe(recipe_name="Tarte au citron", chef_name="Paul", servings_min=1, servings_max=1, user=user_instance, guest_id=guest_value)
    if should_raise:
        with pytest.raises(ValidationError):
            recipe.full_clean()
    else:
        recipe.full_clean()

def test_create_user_visibility(db, user, recipe):
    """On peut créer une UserRecipeVisibility pour un user et une recette."""
    v = UserRecipeVisibility.objects.create(user=user, recipe=recipe, visible=False)
    assert v.pk is not None
    assert v.visible is False
    assert v.user == user
    assert v.guest_id is None

def test_create_guest_visibility(db, recipe):
    """On peut créer une UserRecipeVisibility pour un guest_id et une recette."""
    v = UserRecipeVisibility.objects.create(guest_id="guest-123", recipe=recipe, visible=False)
    assert v.pk is not None
    assert v.visible is False
    assert v.user is None
    assert v.guest_id == "guest-123"

def test_visibility_error_if_no_user_nor_guest_id(db, recipe):
    """Erreur si ni user ni guest_id n'est renseigné."""
    v = UserRecipeVisibility(recipe=recipe, visible=False)
    with pytest.raises(ValidationError, match="lié à un user OU un guest_id"):
        v.full_clean()

def test_visibility_error_if_both_user_and_guest_id(db, user, recipe):
    """Erreur si user ET guest_id sont définis."""
    v = UserRecipeVisibility(user=user, guest_id="guest-123", recipe=recipe)
    with pytest.raises(ValidationError, match="ne peut pas avoir à la fois user et guest_id"):
        v.full_clean()

def test_unique_constraint(db, user, recipe):
    """On ne peut pas dupliquer une ligne (user, guest_id, recipe)."""
    UserRecipeVisibility.objects.create(user=user, recipe=recipe)
    v2 = UserRecipeVisibility(user=user, recipe=recipe)
    with pytest.raises(Exception): 
        v2.save()

def test_visibility_unique_constraint_guest(db, recipe):
    UserRecipeVisibility.objects.create(guest_id="guest-123", recipe=recipe)
    v2 = UserRecipeVisibility(guest_id="guest-123", recipe=recipe)
    with pytest.raises(Exception):
        v2.save()

def test_visibility_hidden_at_autofilled(db, user, recipe):
    v = UserRecipeVisibility.objects.create(user=user, recipe=recipe)
    assert v.hidden_at is not None
