import pytest
from typing import Optional
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
    return SubRecipe.objects.create(recipe=parent, sub_recipe=sub, quantity=qty, unit=unit)

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
    r = make_recipe(name="éclair chocolat 1", chef="chef", pan=base_pans["round_mid"], servings_min=6, servings_max=8, total_qty=900, categories=cats)
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

# =========================
# TESTS – UTILS (multiplier / scaling / references)
# =========================

# -------------------------------------------------
# Groupe 1 — Multiplier (get_scaling_multiplier)
# -------------------------------------------------

def test_scaling_error_no_source_no_target():
    """
    Recette sans pan ni servings + aucune cible fournie :
    get_scaling_multiplier doit lever ValueError avec le message consolidé.
    """
    r = Recipe.objects.create(recipe_name="recette vide", chef_name="chef ok")

    with pytest.raises(ValueError) as exc:
        get_scaling_multiplier(recipe=r)  # Pas de target_pan, pas de target_servings, pas de reference_recipe

    msg = str(exc.value)
    assert "La recette source n'a ni pan ni servings pour servir de base." in msg or "Impossible de calculer" in msg

def test_scaling_with_target_servings_uses_servings_mode_and_ratio():
    """
    Source avec servings_min/max (moyenne = 10) et cible en servings (15) :
    - mode doit être 'servings'
    - multiplicateur = Vtarget / Vsource = (15*150) / (10*150) = 1.5
    """
    # Source avec servings min/max (moyenne = 10)
    r = Recipe.objects.create(recipe_name="tarte", chef_name="yyy", servings_min=8, servings_max=12, total_recipe_quantity=2000)
    mult, mode = get_scaling_multiplier_old(recipe=r, target_servings=15)
    assert mode == "servings"
    # Vtarget/Vsource = (15*150) / (10*150) = 2250 / 1500 = 1.5
    expected = servings_to_volume(15) / servings_to_volume((8 + 12) / 2)
    assert mult == pytest.approx(expected, rel=1e-9)

@pytest.mark.parametrize(
    "smin,smax,target,expected_ratio",
    [
        (8, 12, 20, (20*150)/(10*150)),  # moyenne (8+12)/2 = 10  → ratio = (20*150)/(10*150) = 2.0
        (6, 10, 15, (15*150)/(8*150)),   # moyenne (6+10)/2 = 8   → ratio = (15*150)/(8*150)  = 1.875
    ],
)
def test_adapt_recipe_servings_to_servings(smin, smax, target, expected_ratio):
    """
    Servings d’origine → servings cible (aucun pan côté source/cible) :
    - mode doit être 'servings'
    - le calcul part de la moyenne quand min & max sont présents
    """
    r = Recipe.objects.create(recipe_name="genoise", chef_name="zzz", servings_min=smin, servings_max=smax, total_recipe_quantity=1200)
    mult, mode = get_scaling_multiplier_old(recipe=r, target_servings=target)
    assert mode == "servings"
    assert mult == pytest.approx(expected_ratio, rel=1e-9)

def test_multiplier_direct_pan_to_pan_priority_when_available(recette_eclair_choco, base_pans):
    """
    Cas direct : la recette source a un pan ET des servings.
    On adapte vers un pan cible : c’est la voie directe pan->pan (pas la référence),
    donc multiplier = target_volume / source_volume.
    """
    source = recette_eclair_choco  # a un pan (round_mid)
    target_pan = base_pans["round_big"]  # pan cible

    m, mode = get_scaling_multiplier(source, target_pan=target_pan, reference_recipe=None, prefer_reference=False)

    expected = target_pan.volume_cm3_cache / source.pan.volume_cm3_cache
    assert m == pytest.approx(expected)
    assert mode in ("pan", "servings")  # selon get_source_volume de la source; ici "pan" attendu
    assert mode == "pan"

def test_multiplier_fallback_to_servings_when_no_pan(recette_eclair_cafe, base_pans):
    """
    La recette source n’a PAS de pan mais a des servings.
    Si on cible un pan → on passe par servings(source)->pan(cible).
    """
    source = recette_eclair_cafe  # pas de pan
    target_pan = base_pans["round_small"]

    m, mode = get_scaling_multiplier(source, target_pan=target_pan, reference_recipe=None, prefer_reference=False)

    source_avg_serv = (source.servings_min + source.servings_max) / 2
    source_vol = source_avg_serv * 150
    expected = target_pan.volume_cm3_cache / source_vol
    assert m == pytest.approx(expected)
    assert mode == "servings"

def test_multiplier_error_without_target_pan_or_servings(recette_eclair_choco):
    """
    Pas de target_pan, pas de target_servings → erreur.
    """
    with pytest.raises(ValueError):
        get_scaling_multiplier(recette_eclair_choco)

def test_calculate_quantity_multiplier_happy_and_invalid():
    """
    Couverture simple de calculate_quantity_multiplier.
    """
    assert calculate_quantity_multiplier(100, 200) == pytest.approx(2.0)
    assert calculate_quantity_multiplier(250, 125) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        calculate_quantity_multiplier(0, 10)
    with pytest.raises(ValueError):
        calculate_quantity_multiplier(-5, 10)

def test_multiplier_prefer_reference_pan_path_when_flag_true(recette_eclair_choco, recette_religieuse_cafe, base_pans):
    """
    prefer_reference=True + target_pan fourni :
    → on priorise la densité de la recette de référence.
       - densité ref = total_qty_ref / volume_ref (pan ref prioritaire sinon servings ref)
       - target_total_qty = densité_ref * volume_target_pan
       - multiplier = target_total_qty / total_qty_source
    """
    source = recette_eclair_choco          # total_qty=900, a un pan
    reference = recette_religieuse_cafe    # total_qty=1300, a un pan
    target_pan = base_pans["round_small"]  # pan cible

    m, mode = get_scaling_multiplier(source, target_pan=target_pan, reference_recipe=reference, prefer_reference=True)

    # Calcul attendu via la formule de la voie "reference_recipe_pan"
    ref_vol = reference.pan.volume_cm3_cache * (reference.pan_quantity or 1)
    ref_density = reference.total_recipe_quantity / ref_vol
    target_total_qty = ref_density * target_pan.volume_cm3_cache
    expected = target_total_qty / source.total_recipe_quantity

    assert m == pytest.approx(expected)
    assert mode in ("reference_recipe_pan", "pan")  # on attend "reference_recipe_pan"
    assert mode == "reference_recipe_pan"

def test_multiplier_prefer_reference_servings_path_when_flag_true(recette_eclair_choco, recette_eclair_cafe):
    """
    prefer_reference=True + target_servings fourni :
    → on priorise les servings de la référence (si elle en a), sinon son pan.
    """
    source = recette_eclair_choco         # total_qty=900
    reference = recette_eclair_cafe       # total_qty=1300, pas de pan mais des servings
    target_servings = 12

    m, mode = get_scaling_multiplier(source, target_servings=target_servings, reference_recipe=reference, prefer_reference=True)

    ref_avg_serv = (reference.servings_min + reference.servings_max) / 2
    ref_vol = ref_avg_serv * 150
    ref_density = reference.total_recipe_quantity / ref_vol
    target_vol = target_servings * 150
    target_total_qty = ref_density * target_vol
    expected = target_total_qty / source.total_recipe_quantity

    assert m == pytest.approx(expected)
    assert mode == "reference_recipe_servings"

def test_multiplier_stays_on_direct_path_when_prefer_reference_false_and_direct_possible(base_ingredients, monkeypatch):
    """
    Même si une référence est fournie, avec prefer_reference=False on DOIT rester en voie directe si elle est possible.
    On monkeypatch _try_reference pour lever si jamais elle est appelée.
    """
    # Directement scalable : source avec pan, cible pan
    pan_src = Pan.objects.create(pan_name="src", pan_type="CUSTOM", units_in_mold=6, volume_raw=1000, unit='cm3', is_total_volume=True)
    pan_tgt = Pan.objects.create(pan_name="tgt", pan_type="CUSTOM", units_in_mold=6, volume_raw=2000, unit='cm3', is_total_volume=True)
    src = make_recipe(name="base", pan=pan_src)
    add_ingredient(src, ingredient=base_ingredients["farine"], qty=200)
    src.save()

    # Référence (peu importe son contenu, elle ne doit PAS être utilisée)
    pan_ref = Pan.objects.create(pan_name="ref", pan_type="CUSTOM", units_in_mold=6, volume_raw=1500, unit='cm3', is_total_volume=True)
    ref = make_recipe(name="ref", pan=pan_ref)
    add_ingredient(ref, ingredient=base_ingredients["farine"], qty=200)
    ref.total_recipe_quantity = 1234
    ref.save()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("_try_reference ne doit pas être appelée quand la voie directe est possible et prefer_reference=False.")

    monkeypatch.setattr("pastry_app.utils_new._try_reference", fail_if_called, raising=True)

    multiplier, mode = get_scaling_multiplier(src, target_pan=pan_tgt, reference_recipe=ref, prefer_reference=False)

    assert mode == "pan"
    assert round(multiplier, 6) == round(2000/1000, 6)

def test_multiplier_direct_path_accounts_for_source_pan_quantity_when_multi_empreintes(base_ingredients):
    """
    Cas direct : la recette SOURCE a un moule et pan_quantity > 1.
    Attendu métier : le volume de base doit être "volume_pan_source * pan_quantity_source".
    On vérifie que le multiplicateur = target_volume / (source_volume * pan_quantity).
    """
    # Pan source
    pan_src = Pan.objects.create(pan_name="custom pan", pan_type="CUSTOM", units_in_mold=6, volume_raw=900, unit='cm3', is_total_volume=True)
    # Recette source avec pan_quantity=2 (→ 2 empreintes à remplir à l'identique)
    recipe_src = make_recipe(name="base", pan=pan_src)
    add_ingredient(recipe_src, ingredient=base_ingredients["farine"], qty=200)
    recipe_src.pan_quantity = 2
    recipe_src.total_recipe_quantity = 2000  # utile si la voie "ref" était appelée par erreur
    recipe_src.save()

    # Pan cible
    pan_tgt = Pan.objects.create(pan_name="custom pan 2", pan_type="CUSTOM", units_in_mold=10, volume_raw=1500, unit='cm3', is_total_volume=True)

    # Appel (voie directe attendue, sans référence)
    multiplier, mode = get_scaling_multiplier(recipe_src, target_pan=pan_tgt, reference_recipe=None, prefer_reference=False)

    # Volume attendu côté source = 900 * 2
    expected = 1500 / (900 * 2)

    assert mode == "pan"
    assert round(multiplier, 6) == round(expected, 6), (
        "Le multiplicateur devrait intégrer pan_quantity sur la source : "
        "target_volume / (source_volume * pan_quantity_source)."
    )

def test_multiplier_reference_used_as_fallback_when_no_pan_nor_servings(recette_eclair_choco, recette_religieuse_cafe, base_pans):
    """
    Cas “sans pan ni servings” côté source (on les retire volontairement),
    prefer_reference=False mais référence fournie → fallback référence.
    """
    source = recette_eclair_choco
    # on supprime pan + servings pour forcer le fallback
    source.pan = None
    source.servings_min = None
    source.servings_max = None
    source.save()

    reference = recette_religieuse_cafe
    target_pan = base_pans["round_big"]

    m, mode = get_scaling_multiplier( source, target_pan=target_pan, reference_recipe=reference, prefer_reference=False) # <- fallback, pas priorité explicite

    ref_vol = reference.pan.volume_cm3_cache * (reference.pan_quantity or 1)
    ref_density = reference.total_recipe_quantity / ref_vol
    target_total_qty = ref_density * target_pan.volume_cm3_cache
    expected = target_total_qty / source.total_recipe_quantity

    assert m == pytest.approx(expected)
    assert mode == "reference_recipe_pan"

def test_multiplier_reference_servings_path_uses_ref_pan_when_ref_has_no_servings(base_ingredients):
    """
    La recette source n'a pas d'info scalable (ni pan ni servings).
    La référence possède un PAN (volume connu) mais PAS de servings.
    La cible est un nombre de servings.
    Attendu : voie référence 'reference_recipe_servings' avec densité dérivée du PAN de la ref.
    """
    # Source sans pan ni servings, mais avec quantité totale (nécessaire pour densité)
    src = make_recipe(name="source-no-pan-no-servings", pan=None)
    add_ingredient(src, ingredient=base_ingredients["farine"], qty=200)
    src.servings_min = None
    src.servings_max = None
    src.total_recipe_quantity = 1000  # g
    src.save()

    # Référence : a un pan (volume connu), pas de servings
    ref_pan = Pan.objects.create(pan_name="ref-pan", pan_type="CUSTOM", units_in_mold=6, volume_raw=2000, unit='cm3', is_total_volume=True)
    ref = make_recipe(name="reference-with-pan", pan=ref_pan)
    add_ingredient(ref, ingredient=base_ingredients["farine"], qty=1200)
    ref.total_recipe_quantity = 1200  # g (densité = 1200/2000 = 0,6 g/cm3)
    ref.pan_quantity = 1
    ref.save()
    ref.refresh_from_db()
    ref.servings_min = None
    ref.servings_max = None

    # Cible : 10 servings → volume cible = 10 * 150 = 1500 cm3
    multiplier, mode = get_scaling_multiplier(src, target_servings=10, reference_recipe=ref, prefer_reference=False)

    # Densité ref via PAN → 1200 / (2000 * pan_quantity=1) = 0.6 g/cm3
    # Quantité cible = volume_cible * densité_ref = 1500 * 0.6 = 900 g
    # Multiplicateur = 900 / 1000 = 0.9
    assert mode == "reference_recipe_servings"
    assert round(multiplier, 6) == round(0.9, 6)
    
# -------------------------------------------------
# Groupe 2 — Scaling global (scale_recipe_globally)
# -------------------------------------------------

@pytest.mark.parametrize("multiplier", [0.5, 1.0, 2.0])
def test_scale_recipe_globally_scaling_of_direct_ingredients_and_subrecipes(recettes_choux, multiplier):
    """
    Vérifie que :
      - les quantités des ingrédients directs sont multipliées
      - idem pour les sous-recettes (quantité utilisée) et récursivement leur contenu
      - l’original n’est pas modifié en base
    On teste sur “éclair chocolat” qui possède un ingrédient direct + 2 sous-recettes.
    """
    r = recettes_choux["eclair_choco"]

    # Valeurs de départ
    expected_chocolat = round(200 * multiplier, 2) # Ingrédient direct chocolat = 200 g    
    expected_pate_choux = round(450 * multiplier, 2)  # Sous-recettes utilisées : pâte à choux 450 g
    expected_creme_choco = round(350 * multiplier, 2)  # Sous-recettes utilisées : crème pâtissière choco 350 g

    # Sauvegardes originales
    orig_direct_qties = [ri.quantity for ri in r.recipe_ingredients.all()]
    orig_sub_qties = [sr.quantity for sr in r.main_recipes.all()]

    # Appel
    result = scale_recipe_globally(r, multiplier)

    # 1) Ingrédients directs adaptés
    adapted_direct = result["ingredients"]
    assert len(adapted_direct) == len(orig_direct_qties)
    for i, ri in enumerate(adapted_direct):
        assert ri["quantity"] == pytest.approx(round(orig_direct_qties[i] * multiplier, 2))

    ing_by_name = {i["ingredient_name"]: i for i in result["ingredients"]}
    assert ing_by_name["chocolat"]["quantity"] == pytest.approx(expected_chocolat)

    # 2) Sous-recettes adaptées (quantité de sous-recette utilisée)
    adapted_sub = result["subrecipes"]
    assert len(adapted_sub) == len(orig_sub_qties)
    for i, sr in enumerate(adapted_sub):
        assert sr["quantity"] == pytest.approx(round(orig_sub_qties[i] * multiplier, 2))
        # On vérifie qu’on a bien une récursivité (liste d’ingrédients présente)
        assert "ingredients" in sr and isinstance(sr["ingredients"], list)

    sub_by_name = {s["sub_recipe_name"]: s for s in result["subrecipes"]}
    assert sub_by_name["pâte à choux"]["quantity"] == pytest.approx(expected_pate_choux)
    assert sub_by_name["crème pâtissière chocolat"]["quantity"] == pytest.approx(expected_creme_choco)

    # 3) L’original en base n’est pas modifié
    r.refresh_from_db()
    assert [ri.quantity for ri in r.recipe_ingredients.all()] == orig_direct_qties
    assert [sr.quantity for sr in r.main_recipes.all()] == orig_sub_qties
    assert any(ri.quantity == 200 for ri in r.recipe_ingredients.all())
    assert any(sr.quantity == 450 for sr in r.main_recipes.all())
    assert any(sr.quantity == 350 for sr in r.main_recipes.all())

    # 4) Multiplier = 1.0 → identique
    if multiplier == 1.0:
        for i, ri in enumerate(adapted_direct):
            assert ri["quantity"] == pytest.approx(orig_direct_qties[i])

def test_scale_recipe_globally_deep_recursion_and_rounding(base_ingredients):
    """
    Vérifie la récursion profonde, l'arrondi et l'usage du multiplicateur *local* par préparation.

    Structure:
      A (ingr A1 = 10.0 g)
        └─ B (ingr B1 = 3.333 g ; utilise C à 12.5 g)
             └─ C (ingr C1 = 7.777 g)

    Paramètres:
      multiplier = 1.2345

    Ce que l'on vérifie:
      - Les ingrédients directs de chaque recette sont multipliés et ARRONDIS à 2 décimales.
      - La quantité de chaque sous-recette (main_sub.quantity) est multipliée par le facteur du parent
        et ARRONDIE à 2 décimales pour l'affichage.
      - À chaque sous-recette, on utilise un **multiplicateur local** :
            local_preparation = (quantité utilisée de la préparation dans le parent, en g)
                                / (total_recipe_quantity de la préparation, en g)
        et c’est ce multiplicateur local qui est passé à la récursion et appliqué aux ingrédients
        **de cette préparation**.
      - La structure imbriquée est conservée et la base n’est pas modifiée.
    """
    # C
    C = make_recipe(name="CCC", pan=None)
    add_ingredient(C, ingredient=base_ingredients["farine"], qty=7.777, unit="g")

    # B avec C en sous-recette (ex: on utilise 12.5 g de C "tel quel" dans B)
    B = make_recipe(name="BBB", pan=None)
    add_ingredient(B, ingredient=base_ingredients["farine"], qty=3.333, unit="g")
    add_subrecipe(B, sub=C, qty=12.5, unit="g")

    # A avec B en sous-recette + ingrédient direct
    A = make_recipe(name="AAA", pan=None)
    add_ingredient(A, ingredient=base_ingredients["farine"], qty=10.0, unit="g")
    add_subrecipe(A, sub=B, qty=20.0, unit="g")

    multiplier = 1.2345
    scaled = scale_recipe_globally(A, multiplier)

    # Ingrédient A1
    a1 = next(i for i in scaled["ingredients"] if i["ingredient_id"] == A.recipe_ingredients.first().ingredient_id)
    assert a1["original_quantity"] == 10.0
    assert a1["quantity"] == round(10.0 * multiplier, 2)  # 12.35

    # Sous-recette B
    assert len(scaled["subrecipes"]) == 1
    B_node = scaled["subrecipes"][0]
    assert B_node["sub_recipe_name"] == normalize_case("BBB")
    assert B_node["original_quantity"] == 20.0
    assert B_node["quantity"] == round(20.0 * multiplier, 2)  # 24.69

    # multiplicateur local attendu = (quantité utilisée de B en g) / (total B en g)
    used_qty_B = 20.0 * multiplier                           # B est utilisé à 20 g dans A
    total_B = sum(ri.quantity for ri in B.recipe_ingredients.all())  # 3.333 g avec ce setup
    expected_local_B = used_qty_B / total_B                           # ≈ 7.407740774
    assert B_node["scaling_multiplier"] == pytest.approx(expected_local_B, rel=1e-9)

    # Ingrédient B1 dans B → multiplié par le local de B
    b1 = next(i for i in B_node["ingredients"] if i["ingredient_id"] == B.recipe_ingredients.first().ingredient_id)
    assert b1["original_quantity"] == 3.333
    expected_b1_qty = round(3.333 * expected_local_B, 2)  # quantité attendue pour l’ingrédient B1
    assert b1["quantity"] == expected_b1_qty

    # Sous-recette C dans B (niveau 2)
    assert len(B_node["subrecipes"]) == 1
    C_node = B_node["subrecipes"][0]
    assert C_node["sub_recipe_name"] == normalize_case("CCC")
    assert C_node["original_quantity"] == 12.5
    # quantité affichée pour C = 12.5 × local_B (arrondie)
    assert C_node["quantity"] == round(12.5 * expected_local_B, 2)

    # multiplicateur local attendu pour C = (quantité utilisée de C dans B) / (total standalone de C)
    total_C = sum(ri.quantity for ri in C.recipe_ingredients.all())   # 7.777 g
    expected_local_C = (12.5 * expected_local_B) / total_C
    assert C_node["scaling_multiplier"] == pytest.approx(expected_local_C, rel=1e-9)

    # Ingrédient C1 dans C
    c1 = next(i for i in C_node["ingredients"] if i["ingredient_id"] == C.recipe_ingredients.first().ingredient_id)
    assert c1["original_quantity"] == 7.777
    assert c1["quantity"] == round(7.777 * expected_local_C, 2)

    # --- Vérifier que la base n'a pas été modifiée ---
    A.refresh_from_db(); B.refresh_from_db(); C.refresh_from_db()
    assert [ri.quantity for ri in A.recipe_ingredients.all()] == [10.0]
    assert [ri.quantity for ri in B.recipe_ingredients.all()] == [3.333]
    assert [ri.quantity for ri in C.recipe_ingredients.all()] == [7.777]
    assert [sr.quantity for sr in A.main_recipes.all()] == [20.0]
    assert [sr.quantity for sr in B.main_recipes.all()] == [12.5]

# -------------------------------------------------
# Groupe 3 — Estimation et suggestions de pan
# -------------------------------------------------

def test_suggest_pans_for_servings_returns_close_match():
    """
    Cible 10 portions → volume cible = 10 * 150 = 1500 cm³.
    On crée un moule exactement à 1500 cm³ : il doit apparaître dans les suggestions,
    avec une estimation standard de 10 portions.
    """
    # Moule dans la fenêtre ±5% (ici pile 1500 cm³)
    pan_ok = Pan.objects.create(pan_name="custom-1500", pan_type="CUSTOM", units_in_mold=1, volume_raw=1500, unit="cm3", is_total_volume=True)
    # Quelques moules hors fenêtre pour bruit
    Pan.objects.create(pan_name="custom-1200", pan_type="CUSTOM", units_in_mold=1, volume_raw=1200, unit="cm3", is_total_volume=True)
    Pan.objects.create(pan_name="custom-2000", pan_type="CUSTOM", units_in_mold=1, volume_raw=2000, unit="cm3", is_total_volume=True)

    suggestions = suggest_pans_for_servings(10)  # 1500 cm³ visé  :contentReference[oaicite:3]{index=3}
    assert len(suggestions) >= 1

    # Trouver notre moule dans la liste et vérifier l’estimation de portions
    s = next(x for x in suggestions if x["id"] == pan_ok.id)
    assert s["estimated_servings_standard"] == 10  # 1500/150 = 10, arrondi standard :contentReference[oaicite:4]{index=4}
    assert 1425 <= s["volume_cm3_cache"] <= 1575   # fenêtre ±5%  :contentReference[oaicite:5]{index=5}
    assert s["match_type"] == "close"              # cas “fenêtre”  :contentReference[oaicite:6]{index=6}

def test_suggest_pans_for_servings_falls_back_to_closest_when_no_window_match():
    """
    Cible 9 portions → volume cible = 1350 cm³.
    Aucun moule dans la fenêtre [1282.5 ; 1417.5] → on doit obtenir le plus proche.
    Ici 1600 (écart 250) est plus proche que 1000 (écart 350).
    """
    pan_1000 = Pan.objects.create(pan_name="custom-1000", pan_type="CUSTOM", units_in_mold=1, volume_raw=1000, unit="cm3", is_total_volume=True)
    pan_1600 = Pan.objects.create(pan_name="custom-1600", pan_type="CUSTOM", units_in_mold=1, volume_raw=1600, unit="cm3", is_total_volume=True)

    suggestions = suggest_pans_for_servings(9)  # 1350 cm³ visé  :contentReference[oaicite:7]{index=7}
    assert suggestions, "Aucune suggestion retournée alors que des moules existent."

    # Le premier doit être le plus proche en volume (1600 ici)
    first = suggestions[0]
    assert first["id"] == pan_1600.id  # fallback “closest”  :contentReference[oaicite:8]{index=8}
    # L’estimation standard ~ round(1600/150) = 11  :contentReference[oaicite:9]{index=9}
    assert first["estimated_servings_standard"] == 11

    # Selon l’implémentation actuelle, le fallback passe par une première branche qui marque "close".
    # (Une seconde branche marque "closest" si la première n’a rien rempli.)  :contentReference[oaicite:10]{index=10}
    assert first["match_type"] in {"close", "closest"}

# -------------------------------------------------
# Groupe 4 — Sélection de référence (suggest_recipe_reference)
# -------------------------------------------------

def test_suggest_reference_with_target_servings_prefers_same_subcategory_then_parent(recettes_choux):
    """
    Cible = servings → tous les candidats ont des servings.
    Le tri se fait donc sur le score catégories :
      - priorité forte aux sous-catégories communes ('éclair' vs 'éclair')
      - puis parent ('choux')
    On attend que 'éclair café 2' (même sous-cat) passe avant religieuse/paris-brest.
    """
    recipe = recettes_choux["eclair_choco"]
    candidates = suggest_recipe_reference(recipe, target_servings=10)

    # On ne garde que les suggestions niveau "recette"
    recipe_cand = [cand for cand in candidates if cand.get("level") == "recipe"]
    assert recipe_cand, "Aucune suggestion niveau 'recipe' retournée"
    names = [it["recipe_name"] for it in recipe_cand]

    # Le premier devrait être la recette partageant la sous-catégorie 'éclair'
    assert names[0] == "éclair café 2"
    # Les deux suivants sont les autres de la famille "choux" (ordre exact non garanti)
    assert set(names[1:3]) == {"religieuse café 3", "paris-brest chocolat 4"}

    base_keys = {"id", "recipe_name", "total_recipe_quantity", "category", "parent_category"}
    assert base_keys <= set(recipe_cand[0].keys())

def test_suggest_reference_prefers_higher_category_score_even_if_mode_mismatched(recettes_choux):
    """
    Le candidat au plus haut cat_score doit rester devant,
    même s'il ne matche pas le mode cible (pan ou servings).
    """
    base = recettes_choux["eclair_choco"]  # choux + éclair
    # target_servings: tous ont des servings -> tiebreaker inutile si cat_score différent
    candidates = suggest_recipe_reference(base, target_servings=8)

    # Récupère l'ordre de classement niveau RECETTE
    recipe_cand = [cand for cand in candidates if cand.get("level") == "recipe"]
    assert recipe_cand
    names = [cand["recipe_name"] for cand in recipe_cand]

    # Attendu en tête (meilleur cat_score = 110) : éclair café
    assert names[0].startswith("éclair café")

def test_suggest_reference_uses_mode_only_as_tiebreaker(recettes_choux, base_pans, monkeypatch):
    """
    Deux candidats ex-aequo au cat_score :
    - on force l'égalité du score global (on neutralise nom/prépa/chef) pour que le tie-breaker (mode) tranche.
    - celui qui a un pan (si cible=pan) ou des servings (si cible=servings) passe devant.
    """
    base = recettes_choux["religieuse_cafe"]  # choux + religieuse

    # Neutralise les signaux qui faisaient diverger les scores:
    # - similarité de nom (ex: "café")
    # - similarité de structure de préparations
    # - bonus chef
    monkeypatch.setitem(pastry_app.utils_new.REF_SELECTION_CONFIG, "w_recipe_name_similarity", 0.0)
    monkeypatch.setitem(pastry_app.utils_new.REF_SELECTION_CONFIG, "w_recipe_prep_structure_jaccard", 0.0)
    monkeypatch.setattr(pastry_app.utils_new, "_chef_match_bonus", lambda base, cand: 0)

    candidates = suggest_recipe_reference(base, target_pan=base_pans["round_big"])

    # Récupère l'ordre de classement niveau RECETTE
    recipe_cand = [cand for cand in candidates if cand.get("level") == "recipe"]
    assert recipe_cand
    names = [it["recipe_name"] for it in recipe_cand]

    # vérifie qu'on a bien des scores égaux pour les deux éclairs (diagnostic)
    scores_by_name = {cand["recipe_name"]: cand["score"] for cand in recipe_cand}
    assert pytest.approx(scores_by_name["éclair chocolat 1"], rel=1e-9) == scores_by_name["éclair café 2"]

    # Dans nos fixtures : "éclair choco" a un pan, "éclair café" n’en a pas -> "éclair choco" doit être devant.
    assert names.index("éclair chocolat 1") < names.index("éclair café 2")

def test_suggest_reference_excludes_self(recettes_choux):
    """ Par définition, les suggestions excluent la recette en cours. """
    recipe = recettes_choux["eclair_cafe"]
    candidates = suggest_recipe_reference(recipe, target_servings=8)
    assert recipe not in candidates

def test_suggest_reference_excludes_non_scalable_candidates(base_ingredients):
    """
    Le filtre d'éligibilité impose qu'un candidat ait pan(volume) OU servings.
    On crée 3 candidats dans la même catégorie parente :
      - cand_pan     : a un pan (scalable)
      - cand_serv    : a des servings (scalable)
      - cand_none    : ni pan ni servings (doit être EXCLU)
    On vérifie que 'recipe_level' ne contient pas cand_none.
    """
    # Catégorie parente commune pour ne pas exclure pour une autre raison
    parent = Category.objects.create(category_name="patisseries", category_type="recipe")
    sub_cat = Category.objects.create(category_name="choux", category_type="recipe", parent_category=parent)

    # Base
    base = make_recipe(name="base", pan=None)
    add_ingredient(base, ingredient=base_ingredients["farine"], qty=200)
    base.categories.add(sub_cat)
    base.save()

    # cand_pan : scalable par PAN
    pan = Pan.objects.create(pan_name="cand-pan", pan_type="CUSTOM", units_in_mold=1, volume_raw=1500, unit='cm3', is_total_volume=True)
    cand_pan = make_recipe(name="cand-pan", pan=pan)
    add_ingredient(cand_pan, ingredient=base_ingredients["farine"], qty=200)
    cand_pan.categories.add(sub_cat)
    cand_pan.save()

    # cand_serv : scalable par SERVINGS
    cand_serv = make_recipe(name="cand-serv", pan=None)
    add_ingredient(cand_serv, ingredient=base_ingredients["farine"], qty=200)
    cand_serv.servings_min = 8
    cand_serv.servings_max = 10
    cand_serv.categories.add(sub_cat)
    cand_serv.save()

    # cand_none : NON-scalable
    cand_none = make_recipe(name="cand-none", pan=None)
    add_ingredient(cand_none, ingredient=base_ingredients["farine"], qty=200)
    cand_none.servings_min = None
    cand_none.servings_max = None
    cand_none.categories.add(sub_cat)
    cand_none.save()

    # On passe la liste complète en "candidates" → l'algo doit exclure cand_none
    candidates = suggest_recipe_reference(base, target_pan=pan, candidates=Recipe.objects.filter(id__in=[cand_pan.id, cand_serv.id, cand_none.id]))

    recipe_cand = [cand for cand in candidates if cand.get("level") == "recipe"]
    ids = [cand["id"] for cand in recipe_cand]

    assert cand_pan.id in ids
    assert cand_serv.id in ids
    assert cand_none.id not in ids, "Un candidat sans pan ET sans servings ne doit pas apparaître."

# -------------------------------------------------
# Groupe 5 — Limitation par ingrédients
# -------------------------------------------------

def test_normalize_constraints_for_recipe_converts_units_via_unit_reference():
    """
    Vérifie que normalize_constraints_for_recipe convertit correctement les contraintes
    vers l’unité attendue par la RECETTE, en s’appuyant sur IngredientUnitReference.
    """
    # Recette : 200 g farine, 3 oeufs (unit)
    r = Recipe.objects.create(recipe_name="brioche", chef_name="bbb", recipe_type="BASE")
    farine = Ingredient.objects.create(ingredient_name="farine")
    oeuf = Ingredient.objects.create(ingredient_name="oeuf")
    RecipeIngredient.objects.create(recipe=r, ingredient=farine, quantity=200, unit="g")
    RecipeIngredient.objects.create(recipe=r, ingredient=oeuf, quantity=3, unit="unit")

    # Référence d’unité : 1 oeuf = 55 g (pivot = grammes)
    IngredientUnitReference.objects.create(ingredient=oeuf, unit="unit", weight_in_grams=55)

    # Contraintes brutes (côté user) :
    # - Farine déjà en g (pas de conversion)
    # - Oeuf fourni en grammes → doit être converti en "unit" attendu par la recette
    raw_constraints = {
        farine.id: 300,        # déjà g
        oeuf.id: ("g", 110),   # 110 g → 2 unités
    }

    normalized = normalize_constraints_for_recipe(r, raw_constraints, user=None, guest_id=None)

    assert set(normalized.keys()) == {farine.id, oeuf.id}
    assert normalized[farine.id] == pytest.approx(300.0, rel=1e-12)
    assert normalized[oeuf.id] == pytest.approx(2.0, rel=1e-12)

def test_normalize_constraints_for_recipe_missing_reference_raises():
    """
    Si une conversion est nécessaire mais qu’aucune IngredientUnitReference adaptée n’existe,
    la fonction doit lever une ValidationError explicite.
    """
    # Recette : 150 g d'oeuf (la recette attend des grammes)
    r = Recipe.objects.create(recipe_name="omelette", chef_name="ccc", recipe_type="BASE")
    oeuf = Ingredient.objects.create(ingredient_name="oeuf")
    RecipeIngredient.objects.create(recipe=r, ingredient=oeuf, quantity=150, unit="g")

    # Aucune référence "unit" pour l'œuf n’est créée ici → conversion impossible
    raw_constraints = {oeuf.id: ("unit", 2),}  # user fournit 2 unités, mais la recette attend "g"

    with pytest.raises(ValidationError) as exc:
        normalize_constraints_for_recipe(r, raw_constraints, user=None, guest_id=None)

    assert "Aucune référence de conversion" in str(exc.value)

def test_get_limiting_multiplier_single_limit():
    """ Vérifie que le multiplicateur maximal est bien déterminé par l’ingrédient dont le stock est limitant (cas d’une seule limitation). """
    # Recette : 100 g farine, 2 g levure
    r = Recipe.objects.create(recipe_name="cake", chef_name="aaa", recipe_type="BASE")
    farine = Ingredient.objects.create(ingredient_name="farine")
    levure = Ingredient.objects.create(ingredient_name="levure")
    RecipeIngredient.objects.create(recipe=r, ingredient=farine, quantity=100, unit="g")
    RecipeIngredient.objects.create(recipe=r, ingredient=levure, quantity=2, unit="g")

    # Stock dispo : 150 g farine, 100 g levure → limite = 150/100 = 1.5 (farine)
    stock = {farine.id: 150, levure.id: 100}
    mult, limiting = get_limiting_multiplier(r, stock)
    assert mult == pytest.approx(1.5, rel=1e-9)
    assert limiting == farine.id

def test_get_limiting_multiplier_multi_limit_with_unit_reference():
    """ Vérifie que le calcul identifie un ou plusieurs ingrédients limitants lorsque leurs ratios sont égaux. """
    # Recette : 200 g farine, 3 oeufs (unit)
    r = Recipe.objects.create(recipe_name="brioche", chef_name="bbb", recipe_type="BASE")
    farine = Ingredient.objects.create(ingredient_name="farine")
    oeuf = Ingredient.objects.create(ingredient_name="oeuf")
    RecipeIngredient.objects.create(recipe=r, ingredient=farine, quantity=200, unit="g")
    RecipeIngredient.objects.create(recipe=r, ingredient=oeuf, quantity=3, unit="unit")

    # Référence d’unité : 1 oeuf = 55 g
    IngredientUnitReference.objects.create(ingredient=oeuf, unit="unit", weight_in_grams=55)

    # Stock : 300 g farine, 2 oeufs
    # Limites : farine 300/200 = 1.5 ; oeuf 2/3 ≈ 0.666... → min = 2/3 et c’est l’œuf qui limite
    stock = {farine.id: 300, oeuf.id: 2}
    mult, limiting = get_limiting_multiplier(r, stock)
    assert mult == pytest.approx(2/3, rel=1e-9)
    assert limiting == oeuf.id

    # Variante “égalité” : farine ≈ 133.333 g → 133.333/200 ≈ 2/3, oeuf = 2/3 aussi
    # La fonction retourne UN seul ingrédient limitant (le premier rencontré).
    stock_equal = {farine.id: 133.3333, oeuf.id: 2}
    mult2, limiting2 = get_limiting_multiplier(r, stock_equal)
    assert mult2 == pytest.approx(2/3, rel=1e-5)
    assert limiting2 in {farine.id, oeuf.id}  # égalité acceptée, un seul id est renvoyé
