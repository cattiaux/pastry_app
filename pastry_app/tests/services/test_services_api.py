import pytest
from typing import Optional
from django.urls import reverse
from django.contrib.auth import get_user_model
from pastry_app.utils_new import *
from pastry_app.models import Recipe, Pan, Ingredient, RecipeIngredient, RecipeStep, SubRecipe, Category
from pastry_app.tests.base_api_test import api_client, base_url
import importlib
from pastry_app.views import *
import pastry_app.views
importlib.reload(pastry_app.views)

pytestmark = pytest.mark.django_db

# =========================
# FIXTURES & FACTORIES
# =========================

# ---------- Helpers (mini factories) ----------

def make_pan_round(*, name=None, diameter=16.0, height=4.0, units_in_mold=1, user=None, guest_id=None, visibility="private"):
    pan = Pan.objects.create(pan_name=name, pan_type="ROUND", diameter=diameter, height=height, units_in_mold=units_in_mold, 
                             user=user, guest_id=guest_id, visibility=visibility)
    return pan

def make_ingredient(name: str):
    return Ingredient.objects.create(ingredient_name=name)

def make_category(name: str, *, ctype="recipe", parent=None):
    return Category.objects.create(category_name=name, category_type=ctype, parent_category=parent)

def make_recipe(*, name: str, chef: str = "chef", recipe_type: str = "BASE",
                pan: Optional[Pan] = None,
                servings_min: Optional[int] = None, servings_max: Optional[int] = None,
                total_qty: Optional[float] = None,
                categories: list[Category] = (),
                steps_text: list[str] = ("step ok",),
                user=None, guest_id=None, visibility="private"):
    """
    Crée une Recipe minimale mais valide :
      - au moins 1 step
      - on pourra y ajouter : ingrédients (via add_ingredient) et sous-recettes (via add_subrecipe)
    """
    r = Recipe.objects.create(recipe_name=name, chef_name=chef, recipe_type=recipe_type, pan=pan, servings_min=servings_min, 
                              servings_max=servings_max, total_recipe_quantity=total_qty, user=user, guest_id=guest_id, visibility=visibility)

    # steps (min 1, longueur >= 5 déjà assurée par "step ok")
    for idx, text in enumerate(steps_text, start=1):
        RecipeStep.objects.create(recipe=r, step_number=idx, instruction=text)

    # catégories
    if categories:
        r.categories.set(categories)

    return r

def add_ingredient(recipe: Recipe, *, ingredient: Ingredient, qty: float, unit: str = "g", display_name: str = ""):
    return RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=qty, unit=unit, 
                                           display_name=display_name or ingredient.ingredient_name)

def add_subrecipe(parent: Recipe, *, sub: Recipe, qty: float, unit: str = "g"):
    return SubRecipe.objects.create(parent_recipe=parent, sub_recipe=sub, quantity=qty, unit=unit)

# ---------- Fixtures de base partagées ----------

@pytest.fixture
def base_categories():
    """ Crée la catégorie parent 'choux' (type 'recipe') + sous-catégories 'éclair' et 'religieuse'. """
    choux = make_category("choux", ctype="recipe")
    eclair = make_category("éclair", ctype="recipe", parent=choux)
    religieuse = make_category("religieuse", ctype="recipe", parent=choux)
    return {"choux": choux, "eclair": eclair, "religieuse": religieuse}

@pytest.fixture
def base_ingredients():
    """ Ingrédients minimaux (un par recette/sous-recette). """
    return {
        "farine": make_ingredient("farine"),
        "oeuf": make_ingredient("oeuf"),
        "lait": make_ingredient("lait"),
        "chocolat": make_ingredient("chocolat"),
        "cafe": make_ingredient("cafe"),
        "sucre": make_ingredient("sucre"),
        "praline_grue": make_ingredient("praliné grué"),
    }

@pytest.fixture
def base_pans():
    """ Trois moules ronds avec volumes différents pour tester le scaling & l’estimation. """
    return {
        "round_small": make_pan_round(name="cercle 14x3", diameter=14, height=3),
        "round_mid": make_pan_round(name="cercle 16x4", diameter=16, height=4),
        "round_big": make_pan_round(name="cercle 18x4.5", diameter=18, height=4.5),
    }

# ---------- Sous-recettes (chaque sous-recette = une Recipe) ----------

@pytest.fixture
def subrecipes(base_ingredients):
    """
    Sous-recettes utilisées par les 4 recettes “choux”.
    - Une seule step + un seul ingrédient par sous-recette.
    - Quantités différentes pour vérifier le scaling plus tard.
    """
    # pâte à choux
    pate_choux = make_recipe(name="pâte à choux", steps_text=["mélanger cuire etc"])
    add_ingredient(pate_choux, ingredient=base_ingredients["farine"], qty=200)

    # crème pâtissière chocolat
    creme_choco = make_recipe(name="crème pâtissière chocolat", steps_text=["cuire lait + liaison etc"])
    add_ingredient(creme_choco, ingredient=base_ingredients["chocolat"], qty=150)

    # crème pâtissière café
    creme_cafe = make_recipe(name="crème pâtissière café", steps_text=["mêmes étapes version café"])
    add_ingredient(creme_cafe, ingredient=base_ingredients["cafe"], qty=150)

    # glaçage café
    glacage_cafe = make_recipe(name="glaçage café", steps_text=["mixer, ajuster texture"])
    add_ingredient(glacage_cafe, ingredient=base_ingredients["sucre"], qty=50)

    # praliné grué
    praline_grue = make_recipe(name="praliné grué", steps_text=["broyer, sabler, mixer"])
    add_ingredient(praline_grue, ingredient=base_ingredients["praline_grue"], qty=100)

    return {
        "pate_choux": pate_choux,
        "creme_choco": creme_choco,
        "creme_cafe": creme_cafe,
        "glacage_cafe": glacage_cafe,
        "praline_grue": praline_grue,
    }

# ---------- Les 4 recettes principales “choux” ----------

@pytest.fixture
def recette_eclair_choco(base_categories, base_ingredients, base_pans, subrecipes):
    """
    Éclair au chocolat :
      - cat 'choux' + sous-cat 'éclair'
      - a un pan (round_mid)
      - a aussi des servings pour varier les contextes
    """
    cats = [base_categories["choux"], base_categories["eclair"]]
    r = make_recipe(name="éclair chocolat 1", pan=base_pans["round_mid"], servings_min=6, servings_max=8, total_qty=900, categories=cats)
    # ingrédient direct unique
    add_ingredient(r, ingredient=base_ingredients["chocolat"], qty=200)

    # sous-recettes : pâte à choux + crème pâtissière choco
    add_subrecipe(r, sub=subrecipes["pate_choux"], qty=450)
    add_subrecipe(r, sub=subrecipes["creme_choco"], qty=350)
    return r

@pytest.fixture
def recette_eclair_cafe(base_categories, base_ingredients, subrecipes):
    """
    Éclair au café :
      - cat 'choux' + sous-cat 'éclair'
      - pas de pan ; uniquement servings (différents de l’autre éclair)
    """
    cats = [base_categories["choux"], base_categories["eclair"]]
    r = make_recipe(name="éclair café 2", pan=None, servings_min=8, servings_max=10, total_qty=1200, categories=cats)
    add_ingredient(r, ingredient=base_ingredients["cafe"], qty=70)
    add_subrecipe(r, sub=subrecipes["pate_choux"], qty=600)
    add_subrecipe(r, sub=subrecipes["creme_cafe"], qty=450)
    add_subrecipe(r, sub=subrecipes["glacage_cafe"], qty=80)
    return r

@pytest.fixture
def recette_religieuse_cafe(base_categories, base_ingredients, base_pans, subrecipes):
    """
    Religieuse café :
      - cat 'choux' + sous-cat 'religieuse'
      - a un pan (différent) ET des servings
    """
    cats = [base_categories["choux"], base_categories["religieuse"]]
    r = make_recipe(name="religieuse café 3", pan=base_pans["round_big"], servings_min=10, servings_max=12, total_qty=1300, categories=cats)
    add_ingredient(r, ingredient=base_ingredients["cafe"], qty=70)
    add_subrecipe(r, sub=subrecipes["pate_choux"], qty=650)
    add_subrecipe(r, sub=subrecipes["creme_cafe"], qty=500)
    add_subrecipe(r, sub=subrecipes["glacage_cafe"], qty=80)
    return r

@pytest.fixture
def recette_paris_brest_choco(base_categories, base_ingredients, base_pans, subrecipes):
    """
    Paris-Brest chocolat :
      - cat 'choux' (pas de sous-catégorie)
      - pan (différent) ET servings
    """
    cats = [base_categories["choux"]]
    r = make_recipe(name="paris-brest chocolat 4", pan=base_pans["round_small"], servings_min=6, servings_max=6, total_qty=800, categories=cats)
    add_ingredient(r, ingredient=base_ingredients["chocolat"], qty=70)
    add_subrecipe(r, sub=subrecipes["pate_choux"], qty=400)
    add_subrecipe(r, sub=subrecipes["creme_choco"], qty=300)
    add_subrecipe(r, sub=subrecipes["praline_grue"], qty=30)
    return r

# ---------- Regroupement pratique ----------

@pytest.fixture
def recettes_choux(recette_eclair_choco, recette_eclair_cafe, recette_religieuse_cafe, recette_paris_brest_choco):
    """
    Renvoie un dict contenant les 4 recettes pour les tests
    de sélection/référence/scaling.
    """
    return {
        "eclair_choco": recette_eclair_choco,
        "eclair_cafe": recette_eclair_cafe,
        "religieuse_cafe": recette_religieuse_cafe,
        "paris_brest_choco": recette_paris_brest_choco,
    }

