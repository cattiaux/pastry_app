import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Recipe, Pan
from pastry_app.tests.utils import validate_constraint, validate_field_normalization

pytestmark = pytest.mark.django_db

# --- Fixtures hybrides ---

@pytest.fixture
def pan():
    return Pan.objects.create(pan_name="Cercle 18cm", pan_type="ROUND", diameter=18, height=4.5, units_in_mold=6)

@pytest.fixture
def base_recipe(pan):
    return Recipe.objects.create(recipe_name="Flan Pâtissier", chef_name="Cédric Grolet", recipe_type="BASE", 
                                 servings_min=6, servings_max=6, pan=pan, description="Un flan généreux à la vanille", 
                                 trick="Cuire doucement pour éviter les bulles")

@pytest.fixture
def recipe_factory(pan):
    def make_recipe(**kwargs):
        defaults = {"recipe_name": "Recette Test", "chef_name": "Chef Test", "recipe_type": "BASE", 
                    "servings_min": 4, "servings_max": 6, "pan": pan}
        defaults.update(kwargs)
        return Recipe.objects.create(**defaults)
    return make_recipe

# --- Tests de validation modèle ---

def test_recipe_creation_db(pan):
    """Vérifie qu'on peut créer une recette valide avec le minimum requis."""
    recipe = Recipe.objects.create(recipe_name="Cake", chef_name="Chef Test", recipe_type="BASE", servings_min=4, servings_max=4)
    assert recipe.id is not None
    assert str(recipe) == "Cake (Chef Test)"

def test_recipe_update_db(recipe_factory):
    """Vérifie qu'on peut modifier un champ texte de la recette."""
    recipe = recipe_factory(description="Ancienne description")
    recipe.description = "Nouvelle description très utile"
    recipe.save()
    recipe.refresh_from_db()
    assert recipe.description == "Nouvelle description très utile"

def test_recipe_str_method(base_recipe):
    """Vérifie le format lisible de __str__()."""
    assert str(base_recipe) == "Flan Pâtissier (Cédric Grolet)"

def test_unique_constraint_recipe_db(recipe_factory):
    """Vérifie qu'on ne peut pas créer deux recettes avec le même nom, chef, contexte et source."""
    recipe_factory(recipe_name="Cake Vanille", chef_name="Pierre Hermé", context_name="Entremet Signature", source="Livre 2022")
    with pytest.raises(Exception) as exc_info:
        recipe_factory(recipe_name="Cake Vanille", chef_name="Pierre Hermé", context_name="Entremet Signature", source="Livre 2022")
    assert "unique_recipe_identification" in str(exc_info.value)

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

@pytest.mark.parametrize("s_min, s_max, should_raise", [(None, None, False), (6, 6, False), (4, 8, False), (10, 6, True)])
def test_servings_range_logic_db(recipe_factory, s_min, s_max, should_raise):
    recipe = recipe_factory(servings_min=s_min, servings_max=s_max)
    if should_raise:
        with pytest.raises(ValidationError):
            recipe.full_clean()
    else:
        recipe.full_clean()

def test_parent_recipe_cannot_be_itself_db(recipe_factory):
    recipe = recipe_factory()
    recipe.parent_recipe = recipe
    with pytest.raises(ValidationError, match="sa propre version précédente"):
        recipe.full_clean()

def test_cycle_detection_db(recipe_factory):
    parent = recipe_factory(recipe_name="Parent")
    child = recipe_factory(recipe_name="Child", parent_recipe=parent)
    parent.parent_recipe = child
    with pytest.raises(ValidationError, match="Cycle détecté"):
        parent.full_clean()

def test_auto_fill_servings_from_pan_db(recipe_factory, pan):
    pan.quantity = 5
    pan.save()
    recipe = recipe_factory(pan=pan, servings_min=None, servings_max=None)
    recipe.full_clean()
    assert recipe.servings_min == 5
    assert recipe.servings_max == 5

def test_context_is_auto_filled_if_missing(recipe_factory):
    """Vérifie que context_name est automatiquement généré à partir de parent_recipe si manquant."""
    parent = recipe_factory(recipe_name="Tarte Citron")
    child = Recipe.objects.create(recipe_name="Tarte Citron revisitée", chef_name="Chef Junior", parent_recipe=parent, 
                                  recipe_type="BASE", servings_min=4, servings_max=4)
    assert child.context_name == "Variante de Tarte Citron"

def test_recipe_must_have_step_or_subrecipe(recipe_factory):
    """Vérifie qu'une recette doit avoir au moins une étape OU une sous-recette."""
    recipe = recipe_factory()
    # Pas de steps, pas de sub_recipes
    recipe.save()
    recipe.refresh_from_db()
    recipe.steps.all().delete()
    recipe.subrecipes.all().delete()
    with pytest.raises(ValidationError, match="au moins une étape ou une sous-recette"):
        recipe.full_clean()

def test_recipe_must_have_ingredient_or_subrecipe(recipe_factory):
    """Vérifie qu'une recette doit avoir au moins un ingrédient OU une sous-recette."""
    recipe = recipe_factory()
    recipe.recipe_ingredients.all().delete()
    recipe.subrecipes.all().delete()
    with pytest.raises(ValidationError, match="au moins un ingrédient ou une sous-recette"):
        recipe.full_clean()

@pytest.mark.parametrize("only_min, only_max", [(6, None), (None, 8)])
def test_auto_copy_servings_recipe_db(recipe_factory, only_min, only_max):
    """Vérifie que si un seul servings est fourni, l'autre est automatiquement copié."""
    recipe = recipe_factory(servings_min=only_min, servings_max=only_max)
    recipe.full_clean()
    if only_min:
        assert recipe.servings_max == only_min
    if only_max:
        assert recipe.servings_min == only_max

def test_recipe_with_multiple_pans(recipe_factory):
    """Vérifie qu'une recette utilisant plusieurs exemplaires du même moule ajuste correctement les servings."""
    recipe = recipe_factory(pan_quantity=3, servings_min=None, servings_max=None)
    recipe.full_clean()
    assert recipe.servings_min == recipe.pan.units_in_mold * 3

def test_custom_pan_with_total_volume(pan):
    """Vérifie que si volume_total est explicitement déclaré, il n'est pas multiplié par `units_in_mold`."""
    pan.pan_type = "CUSTOM"
    pan.volume_raw = 600
    pan.unit = "cm3"
    pan.is_total_volume = True
    pan.units_in_mold = 6
    pan.clean()
    assert pan.volume_cm3 == 600  # Pas multiplié