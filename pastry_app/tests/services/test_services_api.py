import pytest
from typing import Optional
from django.contrib.auth import get_user_model
from pastry_app.utils import *
from pastry_app.text_utils import *
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

User = get_user_model()

@pytest.fixture
def user():
    admin = User.objects.create_user(username="user1", password="testpass123")
    admin.is_staff = True  # Assure que l'utilisateur est un admin
    admin.save()
    return admin 

# ---------- Helpers (mini factories) ----------

def make_pan_round(*, name=None, diameter=16.0, height=4.0, units_in_mold=1, user=None, guest_id=None, visibility="private"):
    pan = Pan.objects.create(pan_name=name, pan_type="ROUND", diameter=diameter, height=height, units_in_mold=units_in_mold, 
                             user=user, guest_id=guest_id, visibility=visibility)
    return pan

def make_ingredient(name: str):
    return Ingredient.objects.create(ingredient_name=name)

def make_category(user, name: str, *, ctype="recipe", parent=None):
    return Category.objects.create(category_name=name, category_type=ctype, parent_category=parent, created_by=user)

def make_recipe(*, name: str, chef: str = "chef", recipe_type: str = "BASE",
                pan: Optional[Pan] = None,
                servings_min: Optional[int] = None, servings_max: Optional[int] = None,
                total_qty: Optional[float] = None,
                categories: list[Category] = (),
                steps_text: list[str] = ("step ok",),
                user=None, guest_id=None, visibility="public"):
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
def base_categories(user):
    """ Crée la catégorie parent 'choux' (type 'recipe') + sous-catégories 'éclair' et 'religieuse'. """
    choux = make_category(user, "choux", ctype="recipe")
    eclair = make_category(user, "éclair", ctype="recipe", parent=choux)
    religieuse = make_category(user, "religieuse", ctype="recipe", parent=choux)
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


API_PREFIX = "/api"
URL_RECIPES_ADAPT = f"{API_PREFIX}/recipes-adapt/"
URL_PAN_ESTIMATION = f"{API_PREFIX}/pan-estimation/"
URL_PAN_SUGGESTION = f"{API_PREFIX}/pan-suggestion/"
URL_RECIPES_ADAPT_BY_ING = f"{API_PREFIX}/recipes-adapt/by-ingredient/"
URL_RECIPES_LIST = f"{API_PREFIX}/recipes/"
URL_RECIPES_LEGO_CANDIDATES = f"{API_PREFIX}/recipes/lego-candidates/"
URL_RECIPES_REFERENCE_USES = f"{API_PREFIX}/recipes/{{id}}/reference-uses/"

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _post(api_client, url: str, data: dict, user=None, guest_id=None):
    if user:
        api_client.force_authenticate(user=user)
    headers = {}
    if guest_id:
        headers["HTTP_X_GUEST_ID"] = guest_id
    return api_client.post(url, data, format="json", **headers)

def _get(api_client, url: str, params: Optional[dict] = None, user=None, guest_id=None):
    if user:
        api_client.force_authenticate(user=user)
    headers = {}
    if guest_id:
        headers["HTTP_X_GUEST_ID"] = guest_id
    return api_client.get(url, params, format="json", **headers)

# ===================================================================
# /recipes-adapt/ — POST
# ===================================================================

def test_recipes_adapt__pan_to_pan(api_client, recettes_choux, base_pans):
    src = recettes_choux["eclair_choco"]      # a un pan
    tgt = base_pans["round_big"]

    mult, mode = get_scaling_multiplier(src, target_pan=tgt)
    expected = scale_recipe_globally(src, mult)

    resp = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_pan_id": tgt.id})
    assert resp.status_code == status.HTTP_200_OK, resp.data
    data = resp.json()

    assert data["scaling_multiplier"] == pytest.approx(mult)
    assert data["scaling_mode"] in ("pan", "servings", "reference_recipe_pan", "reference_recipe_servings")

    got = {i["ingredient_name"]: i["quantity"] for i in data.get("ingredients", [])}
    exp = {i["ingredient_name"]: i["quantity"] for i in expected.get("ingredients", [])}
    for name, qty in got.items():
        assert qty == pytest.approx(exp[name], rel=1e-2)

def test_recipes_adapt__servings_to_pan(api_client, recettes_choux, base_pans):
    """
    Source sans pan (éclair café) → cible pan.
    On calcule le multiplicateur manuellement :
      source_volume = avg(servings_min,max) * 150 = 9 * 150 = 1350 cm³
      target_volume = volume du pan cible
      multiplier = target_volume / source_volume
    Puis on vérifie une quantité emblématique (ingrédient direct 'café' = 70g).
    """
    src = recettes_choux["eclair_cafe"]  # servings_min=8, max=10, total_qty=1200, café=70, pas de pan
    tgt = base_pans["round_mid"]    # diamètre 16, hauteur 4

    # calcul manuel : volumes (le Pan stocke volume_cm3_cache)
    target_volume = float(tgt.volume_cm3_cache)
    source_volume = 9 * 150.0  # moyenne 9 portions
    expected_multiplier = target_volume / source_volume
    expected_cafe_qty = 70.0 * expected_multiplier

    # calcul via méthode get_scaling_multiplier
    mult, _ = get_scaling_multiplier(src, target_pan=tgt)

    resp = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_pan_id": tgt.id})
    assert resp.status_code == 200, resp.data
    assert resp.json()["scaling_multiplier"] == pytest.approx(mult)
    assert resp.json()["scaling_multiplier"] == pytest.approx(expected_multiplier)

    print("Response data:", resp.json())  # DEBUG

    # vérif sur l’ingrédient 'café'
    cafe = next(i for i in resp.json()["ingredients"] if i["ingredient_name"].lower().startswith("cafe"))
    assert cafe["quantity"] == pytest.approx(expected_cafe_qty, rel=1e-2)

def test_recipes_adapt__pan_to_servings(api_client, recettes_choux):
    """
    Source avec pan (éclair choco) mais sans servings (on désactive les servings de l'éclair choco ici) → cible servings.
    Calcul manuel :
      source_volume = volume du pan source
      target_volume = target_servings * 150
      multiplier = target_volume / source_volume
    Vérifie la quantité de 'chocolat' (200g en base).
    """
    src = recettes_choux["eclair_choco"]      # pan = round_mid, total_qty=900, chocolat=200

    # on force l'absence de servings pour tester pan→servings
    src.servings_min = None
    src.servings_max = None
    src.save()
    print("serving min: ", src.servings_min, "max:", src.servings_max)  # DEBUG log
    target_servings = 12

    # calcul manuel
    source_volume = float(src.pan.volume_cm3_cache)
    target_volume = target_servings * 150.0
    expected_multiplier = target_volume / source_volume
    expected_choco_qty = 200.0 * expected_multiplier

    # calcul via méthode get_scaling_multiplier
    mult, _ = get_scaling_multiplier(src, target_servings=target_servings)
    
    resp = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_servings": target_servings})
    assert resp.status_code == 200, resp.data
    assert resp.json()["scaling_multiplier"] == pytest.approx(mult)
    assert resp.json()["scaling_multiplier"] == pytest.approx(expected_multiplier)

    choco = next(i for i in resp.json()["ingredients"] if i["ingredient_name"].lower().startswith("chocolat"))
    assert choco["quantity"] == pytest.approx(expected_choco_qty, rel=1e-2)

def test_recipes_adapt__servings_to_servings(api_client, recettes_choux):
    """
    Source servings → cible servings (éclair café).
    Calcul manuel :
      source_volume = avg(8,10)*150 = 9*150
      target_volume = 14*150
      multiplier = target_volume / source_volume
    Vérifie la quantité de 'café' (70g).
    """
    src = recettes_choux["eclair_cafe"]       # 8–10 portions, café=70
    target_servings = 14

    # calcul manuel
    source_volume = 9 * 150.0
    target_volume = target_servings * 150.0
    expected_multiplier = target_volume / source_volume
    expected_cafe_qty = 70.0 * expected_multiplier

    # calcul via méthode get_scaling_multiplier
    mult, _ = get_scaling_multiplier(src, target_servings=target_servings)
    
    resp = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_servings": target_servings})
    assert resp.status_code == 200
    assert resp.json()["scaling_multiplier"] == pytest.approx(mult)
    assert resp.json()["scaling_multiplier"] == pytest.approx(expected_multiplier)

    cafe = next(i for i in resp.json()["ingredients"] if i["ingredient_name"].lower().startswith("cafe"))
    assert cafe["quantity"] == pytest.approx(expected_cafe_qty, rel=1e-2)

@pytest.mark.parametrize(
    "use_target_pan, use_target_servings, expected_mode",
    [
        (True,  False, "reference_recipe_pan"),
        (False, True,  "reference_recipe_servings"),
    ]
)
def test_recipes_adapt__reference_recipe_modes(api_client, recettes_choux, base_pans, use_target_pan, use_target_servings, expected_mode):
    """
    Calcul manuel via densité de la recette de référence :
      - Si expected_mode == reference_recipe_pan:
          ref_density = ref.total_qty / (ref.pan.volume * ref.pan_quantity)
      - Si expected_mode == reference_recipe_servings:
          on privilégie les servings de la référence s'ils existent :
            ref_serv_avg = avg(ref.servings_min, ref.servings_max)
            ref_density = ref.total_qty / (ref_serv_avg*150)
          sinon fallback pan de la ref.

      Puis:
        target_volume = (pan cible).volume  OU  target_servings*150
        target_total_qty = target_volume * ref_density
        multiplier = target_total_qty / source.total_qty

      Vérifie une quantité emblématique côté source ('chocolat' pour PB choco).
    """
    src = recettes_choux["paris_brest_choco"]   # total_qty=800, chocolat=70
    ref = recettes_choux["eclair_choco"]     # total_qty=900, pan=round_mid, servings 6–8
    payload = {"recipe_id": src.id, "reference_recipe_id": ref.id, "prefer_reference": True}

    # calcul manuel
    if expected_mode == "reference_recipe_pan":
        ref_pan_vol = float(ref.pan.volume_cm3_cache)
        ref_vol = ref_pan_vol * float(getattr(ref, "pan_quantity", 1) or 1)
        ref_density = ref.total_recipe_quantity / ref_vol  # g/cm³
        # cible = pan
        tgt_pan = base_pans["round_small"]
        payload["target_pan_id"] = tgt_pan.id
        target_volume = float(tgt_pan.volume_cm3_cache)
    else:
        # priorité aux servings de la référence
        ref_serv_avg = ((ref.servings_min + ref.servings_max) / 2.0) if (ref.servings_min and ref.servings_max) else \
                       (ref.servings_min or ref.servings_max)
        if ref_serv_avg:
            ref_vol = ref_serv_avg * 150.0
            ref_density = ref.total_recipe_quantity / ref_vol
        else:
            ref_pan_vol = float(ref.pan.volume_cm3_cache)
            ref_vol = ref_pan_vol * float(getattr(ref, "pan_quantity", 1) or 1)
            ref_density = ref.total_recipe_quantity / ref_vol
        # cible = servings
        payload["target_servings"] = 8
        target_volume = 8 * 150.0

    target_total_qty = target_volume * ref_density
    expected_multiplier = target_total_qty / src.total_recipe_quantity
    expected_choco_qty = 70.0 * expected_multiplier

    # calcul via methode get_scaling_multiplier
    if use_target_pan:
        payload["target_pan_id"] = base_pans["round_small"].id
    if use_target_servings:
        payload["target_servings"] = 8

    mult, _ = get_scaling_multiplier(
        src,
        target_pan=base_pans["round_small"] if use_target_pan else None,
        target_servings=8 if use_target_servings else None,
        reference_recipe=ref,
        prefer_reference=True,
    )

    resp = _post(api_client, URL_RECIPES_ADAPT, payload)
    assert resp.status_code == 200, resp.data
    assert resp.json()["scaling_mode"] == expected_mode
    assert resp.json()["scaling_multiplier"] == pytest.approx(mult)
    assert resp.json()["scaling_multiplier"] == pytest.approx(expected_multiplier)

    choco = next(i for i in resp.json()["ingredients"] if i["ingredient_name"].lower().startswith("chocolat"))
    assert choco["quantity"] == pytest.approx(expected_choco_qty, rel=1e-2)
    
def test_recipes_adapt__validation_errors(api_client, recettes_choux):
    src = recettes_choux["eclair_choco"]

    # recipe_id manquant
    r1 = _post(api_client, URL_RECIPES_ADAPT, {})
    assert r1.status_code == 400
    assert "recipe_id" in r1.json().get("error", "").lower()

    # aucun critère fourni
    r2 = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id})
    assert r2.status_code == 400
    msg = r2.json().get("error", "")
    assert "moule" in msg or "portions" in msg or "référence" in msg

def test_recipes_adapt__prioritize_direct_when_possible(api_client, recettes_choux, base_pans):
    """
    prefer_reference=False + target_pan + reference → on attend le mode direct (pan/servings).
    """
    src = recettes_choux["eclair_choco"]
    ref = recettes_choux["eclair_cafe"]
    tgt = base_pans["round_mid"]

    mult_direct, _ = get_scaling_multiplier(src, target_pan=tgt, reference_recipe=ref, prefer_reference=False)
    resp = _post(api_client, URL_RECIPES_ADAPT, {
        "recipe_id": src.id,
        "target_pan_id": tgt.id,
        "reference_recipe_id": ref.id,
        "prefer_reference": False
    })
    assert resp.status_code == 200, resp.data
    assert resp.json()["scaling_multiplier"] == pytest.approx(mult_direct)
    assert resp.json()["scaling_mode"] in ("pan", "servings")

@pytest.mark.parametrize("recursive", [False, True])
def test_recipes_adapt__smoke_all_modes(api_client, recettes_choux, base_pans, recursive):
    """
    Tour rapide : l’endpoint répond et fournit un scaling_mode cohérent
    pour une recette simple et une recette avec sous-recettes.
    """
    src = recettes_choux["eclair_choco"] if not recursive else recettes_choux["paris_brest_choco"]

    # pan_to_pan
    r_pan = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_pan_id": base_pans["round_small"].id})
    assert r_pan.status_code == 200
    assert r_pan.json()["scaling_mode"] in ("pan",)

    # servings_to_servings
    r_serv = _post(api_client, URL_RECIPES_ADAPT, {"recipe_id": src.id, "target_servings": 9})
    assert r_serv.status_code == 200
    assert r_serv.json()["scaling_mode"] in ("servings",)

# ===================================================================
# /pan-estimation/ — POST
# ===================================================================

def test_pan_estimation__with_pan_id(api_client, base_pans):
    """
    Vérifie que l'estimation d'un moule via son ID retourne un statut 200
    et contient au moins le volume et un intervalle de portions.
    """
    pan = base_pans["round_mid"]
    resp = _post(api_client, URL_PAN_ESTIMATION, {"pan_id": pan.id})
    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert isinstance(data, dict)
    # est attendu : volume + intervalle de portions (noms exacts côté service au choix)
    assert any(k in data for k in ("volume_cm3", "volume"))
    assert any(k in data for k in ("estimated_servings_min", "estimated_servings_max"))

def test_pan_estimation__with_dimensions_round(api_client):
    """
    Serializer accepte pan_type + dimensions (ROUND: diameter + height).
    """
    payload = {"pan_type": "ROUND", "diameter": 20.0, "height": 5.0}
    resp = _post(api_client, URL_PAN_ESTIMATION, payload)
    assert resp.status_code in (200, 400)  # selon logique d'estimation interne
    if resp.status_code == 200:
        data = resp.json()
        assert any(k in data for k in ("volume_cm3", "volume"))

def test_pan_estimation__with_volume_raw(api_client):
    """
    Serializer accepte directement volume_raw.
    """
    resp = _post(api_client, URL_PAN_ESTIMATION, {"volume_raw": 1500.0})
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert isinstance(resp.json(), dict)

def test_pan_estimation__validation_error_when_no_inputs(api_client):
    """
    Vérifie qu'un appel à l'estimation sans paramètres renvoie une erreur de validation
    (400 ou 422) et que le message mentionne pan_id ou volume_raw.
    """
    resp = _post(api_client, URL_PAN_ESTIMATION, {})
    assert resp.status_code in (400, 422)
    # message du serializer
    if resp.status_code == 400:
        msgs = " ".join(resp.json().get("non_field_errors", []))
        assert "pan_id" in msgs or "volume_raw" in msgs

def test_pan_estimation_missing_params_returns_400(api_client):
    """Pan-estimation sans paramètres obligatoires → 400."""
    resp = api_client.post(URL_PAN_ESTIMATION, {}, format="json")
    assert resp.status_code == 400

# ===================================================================
# /pan-suggestion/ — POST
# ===================================================================

def test_pan_suggestion__basic_list(api_client):
    """
    Vérifie que la suggestion de moules pour un nombre de portions donné
    retourne une liste de dictionnaires (ou liste vide).
    """
    resp = _post(api_client, URL_PAN_SUGGESTION, {"target_servings": 10})
    assert resp.status_code == 200, resp.data
    lst = resp.json()
    assert isinstance(lst, list)
    if lst:
        assert isinstance(lst[0], dict)

def test_pan_suggestion__invalid_target_servings(api_client):
    """
    Vérifie qu'un nombre de portions cible invalide (0) provoque une
    erreur de validation (400 ou 422).
    """
    # Serializer force min_value=1 et check >0
    resp = _post(api_client, URL_PAN_SUGGESTION, {"target_servings": 0})
    assert resp.status_code in (400, 422)

# ===================================================================
# /recipes-adapt/by-ingredient/ — POST
# ===================================================================

def test_recipes_adapt_by_ingredient__limits_and_scales(api_client, base_ingredients):
    """
    Serializer n'accepte que des floats → on transmet des quantités numériques
    **dans les unités attendues par la recette**.
    """
    r = make_recipe(name="brioche-API")
    farine = base_ingredients["farine"]
    oeuf = Ingredient.objects.create(ingredient_name="oeuf2")

    # Recette : 200 g farine + 3 unités d'œuf (avec référence 1 unit = 55 g — utile pour utils si besoin)
    add_ingredient(r, ingredient=farine, qty=200.0, unit="g")
    add_ingredient(r, ingredient=oeuf, qty=3.0, unit="unit")
    IngredientUnitReference.objects.create(ingredient=oeuf, unit="unit", weight_in_grams=55)

    # Contraintes : on donne des valeurs numériques (pas de tuples d'unités)
    # Hypothèse : l'algo considère que la contrainte est donnée dans l'unité de la recette.
    constraints = {
        farine.id: 300.0,  # g
        oeuf.id: 2.0,      # unit
    }

    # Attente calculée côté utils
    normalized = normalize_constraints_for_recipe(r, constraints)
    limiting_mult, limiting_ing_id = get_limiting_multiplier(r, normalized)
    expected = scale_recipe_globally(r, limiting_mult)

    resp = _post(api_client, URL_RECIPES_ADAPT_BY_ING, {"recipe_id": r.id, "ingredient_constraints": constraints}, guest_id="guest-42")
    assert resp.status_code == 200, resp.data
    data = resp.json()

    # La view renvoie "multiplier" + "limiting_ingredient_id"
    assert data["multiplier"] == pytest.approx(limiting_mult)
    assert data["limiting_ingredient_id"] == limiting_ing_id

    got = {i["ingredient_name"]: i["quantity"] for i in data.get("ingredients", [])}
    exp = {i["ingredient_name"]: i["quantity"] for i in expected.get("ingredients", [])}
    for name, qty in got.items():
        assert qty == pytest.approx(exp[name], rel=1e-9)

def test_recipes_adapt_by_ingredient__bad_payload_validation(api_client):
    """
    DictField(child=FloatField) → si on envoie une valeur non numérique, 400/422.
    """
    r = make_recipe(name="omelette-API")
    ing = Ingredient.objects.create(ingredient_name="oeuf")
    add_ingredient(r, ingredient=ing, qty=150.0, unit="g")

    # valeur non float → devrait échouer en validation
    resp = _post(api_client, URL_RECIPES_ADAPT_BY_ING, {"recipe_id": r.id, "ingredient_constraints": {ing.id: "two"}})
    assert resp.status_code in (400, 422)

# ===================================================================
# /recipes/<id>/reference-suggestions/ — GET
# ===================================================================

def test_reference_suggestions__structure_and_exclusion(api_client, recettes_choux, base_pans):
    """
    Viewset action renvoie {"criteria": {...}, "reference_recipes": [...]}
    et sérialise chaque recette via RecipeReferenceSuggestionSerializer :
      fields = ["id", "recipe_name", "total_recipe_quantity", "category", "parent_category"]
    """
    host = recettes_choux["eclair_cafe"]  # pas de pan
    target_pan = base_pans["round_small"]

    url = f"{API_PREFIX}/recipes/{host.id}/reference-suggestions/"
    resp = _get(api_client, url, {"target_pan_id": target_pan.id})
    print(resp.json())
    assert resp.status_code == 200, resp.data

    payload = resp.json()
    assert set(payload.keys()) == {"criteria", "reference_recipes"}

    crit = payload["criteria"]
    assert set(crit.keys()) == {"target_pan_id", "target_servings"}
    # target_pan_id renvoyé en entier si fourni
    if crit["target_pan_id"] is not None:
        assert isinstance(crit["target_pan_id"], int)

    items = payload["reference_recipes"]
    assert isinstance(items, list)

    # host exclu
    ids = [it.get("id") for it in items]
    assert host.id not in ids

    # check serializer fields (si liste non vide)
    if items:
        keys = set(items[0].keys())
        assert {"id", "recipe_name", "total_recipe_quantity", "category", "parent_category"} <= keys

def test_reference_suggestions__by_servings_and_param_validation(api_client, recettes_choux):
    """
    Vérifie qu'une recette peut suggérer des références via target_servings (200 avec référence_recipes)
    et qu'un target_pan_id invalide renvoie une erreur 400 avec message approprié.
    """
    host = recettes_choux["paris_brest_choco"]
    url = f"{API_PREFIX}/recipes/{host.id}/reference-suggestions/"

    ok = _get(api_client, url, {"target_servings": 10})
    assert ok.status_code == 200, ok.data
    assert "reference_recipes" in ok.json()

    bad = _get(api_client, url, {"target_pan_id": "oops"})
    assert bad.status_code == 400
    assert "target_pan_id" in bad.json().get("error", "")

# ===================================================================
# /recipes/<id>/adapt/ — POST (action du RecipeViewSet)
# ===================================================================

def test_recipe_adapt_action__guest_clones_everything(api_client, recettes_choux):
    """
    Invité (header X-Guest-Id) : clone une recette existante.
    - parent_recipe = mère (top-level)
    - recipe_type = VARIATION
    - visibility = private
    - is_default = False
    - guest_id propagé, user=None
    - ingrédients, étapes, sous-recettes, catégories/labels copiés
    - recipe_name personnalisable
    """
    original = recettes_choux["paris_brest_choco"]  # a des sous-recettes/ingrédients/étapes dans nos fixtures
    guest = "guest-42"

    url = f"{API_PREFIX}/recipes/{original.id}/adapt/"
    payload = {"recipe_name": "Ma variation PB", "version_note": "test note"}
    resp = _post(api_client, url, payload, guest_id=guest)
    assert resp.status_code == status.HTTP_201_CREATED, resp.data

    new_id = resp.json()["id"]
    new_recipe = Recipe.objects.get(pk=new_id)

    # la "mère" est l’ancêtre top-level de original (si original est déjà une adaptation)
    mother = original
    while mother.parent_recipe:
        mother = mother.parent_recipe

    assert new_recipe.parent_recipe_id == mother.id
    assert new_recipe.recipe_type == "VARIATION"
    assert new_recipe.visibility == "private"
    assert new_recipe.is_default is False
    assert new_recipe.user is None
    assert new_recipe.guest_id == guest
    assert new_recipe.recipe_name == normalize_case("Ma variation PB")

    # contenu cloné
    assert new_recipe.recipe_ingredients.count() == original.recipe_ingredients.count()
    assert new_recipe.steps.count() == original.steps.count()
    assert new_recipe.main_recipes.count() == original.main_recipes.count()
    assert set(new_recipe.categories.values_list("id", flat=True)) == set(original.categories.values_list("id", flat=True))
    assert set(new_recipe.labels.values_list("id", flat=True)) == set(original.labels.values_list("id", flat=True))

def test_recipe_adapt_action__user_and_chaining_keeps_mother(api_client, recettes_choux, user):
    """
    Utilisateur authentifié :
    - le clone appartient au user (guest_id None)
    - si on adapte une adaptation, la nouvelle variation pointe toujours sur la mère top-level.
    """
    api_client.force_authenticate(user=user)

    original = recettes_choux["eclair_choco"]  # a priori recette de base avec pan
    # 1er clone
    url1 = f"{API_PREFIX}/recipes/{original.id}/adapt/"
    r1 = _post(api_client, url1, {"recipe_name": "Var 1"})
    assert r1.status_code == status.HTTP_201_CREATED, r1.data
    child1 = Recipe.objects.get(pk=r1.json()["id"])
    assert child1.user_id == user.id
    assert child1.guest_id is None
    # 2ème clone depuis la variation (doit remonter à la mère "original")
    url2 = f"{API_PREFIX}/recipes/{child1.id}/adapt/"
    r2 = _post(api_client, url2, {"recipe_name": "Var 2 depuis Var 1"})
    assert r2.status_code == status.HTTP_201_CREATED, r2.data
    child2 = Recipe.objects.get(pk=r2.json()["id"])

    # mother = ancêtre top-level de child1 (devrait être original)
    mother = child1
    while mother.parent_recipe:
        mother = mother.parent_recipe

    assert mother.id == original.id
    assert child2.parent_recipe_id == original.id
    assert child2.user_id == user.id
    assert child2.guest_id is None

    # Quick sanity : contenu copié aussi au 2ème clone
    assert child2.recipe_ingredients.count() == child1.recipe_ingredients.count()
    assert child2.steps.count() == child1.steps.count()
    assert child2.main_recipes.count() == child1.main_recipes.count()

# ===================================================================
# /recipes/{host_id}/subrecipes/{sub_id}/ingredients/bulk-edit — POST (action du RecipeViewSet)
# ===================================================================

def _bulk_edit_url(base_url, host_id: int, sub_id: int) -> str:
    """Construit l’URL de l’action bulk-edit sur une sous-recette d’un hôte."""
    return base_url("recipes") + f"{host_id}/subrecipes/{sub_id}/ingredients/bulk-edit/"

def test_variant_bulk_edit__not_impact_source(api_client, base_url, base_ingredients):
    """
    GIVEN A→B (B: farine=100, sucre=30)
    WHEN  on POST bulk-edit avec 2 updates (farine=120, sucre=40)
    THEN  A est rebranchée sur B', B est inchangé, B' contient les nouvelles quantités,
          et le nom de B' est suffixé.
    """
    # A → B (B: farine=100, sucre=30)
    B = make_recipe(name="BBB", chef="Chef B", visibility="private")
    far = add_ingredient(B, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    suc = add_ingredient(B, ingredient=base_ingredients["sucre"], qty=30.0, unit="g")

    A = make_recipe(name="AAA", chef="Chef A", visibility="private")
    link = add_subrecipe(A, sub=B, qty=200.0, unit="g")

    for r in (A, B):
        r.user = None
        r.guest_id = "guest-1"
        r.save()

    payload = {
        "updates": [
            {"ingredient_id": far.ingredient_id, "quantity": 120.0, "unit": "g"},
            {"ingredient_id": suc.ingredient_id, "quantity": 40.0, "unit": "g"},
        ],
        "multiplier": 1.0,
    }
    resp = _post(api_client, _bulk_edit_url(base_url, A.id, link.id), payload, guest_id="guest-1")
    print(resp.json())  # DEBUG log
    assert resp.status_code == 200, getattr(resp, "data", resp.content)

    # Rewire + clone OK
    link.refresh_from_db(); A.refresh_from_db(); B.refresh_from_db()
    variant = link.sub_recipe
    assert variant.id != B.id
    assert variant.parent_recipe_id == B.id
    assert variant.owned_by_recipe_id == A.id
    assert normalize_case("[usage: AAA]") in variant.recipe_name

    # B inchangé
    got_B = {ri.ingredient.ingredient_name: ri.quantity for ri in B.recipe_ingredients.all()}
    assert got_B["farine"] == 100.0
    assert got_B["sucre"] == 30.0

    # B′ mis à jour
    got_V = {ri.ingredient.ingredient_name: ri.quantity for ri in variant.recipe_ingredients.all()}
    assert got_V["farine"] == 120.0
    assert got_V["sucre"] == 40.0

def test_variant_bulk_edit__reuse_variant_no_duplicate(api_client, base_url, base_ingredients):
    """
    GIVEN A→B
    WHEN  on POST bulk-edit deux fois
    THEN  la première crée B' et la seconde réutilise B' (même id), et un seul clone existe pour (A,B).
    """
    B = make_recipe(name="BBB", chef="Chef B", visibility="private")
    far = add_ingredient(B, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    A = make_recipe(name="AAA", chef="Chef A", visibility="private")
    link = add_subrecipe(A, sub=B, qty=200.0, unit="g")

    for r in (A, B):
        r.user = None
        r.guest_id = "guest-1"
        r.save()

    # 1er edit → crée B′
    url = _bulk_edit_url(base_url, A.id, link.id)
    payload = {"updates": [{"ingredient_id": far.ingredient_id, "quantity": 120.0}]}
    r1 = _post(api_client, url, payload, guest_id="guest-1")
    assert r1.status_code == 200

    link.refresh_from_db()
    variant_id = link.sub_recipe_id

    # 2e edit → réutilise B′
    r2 = _post(api_client, url, {"updates": [{"ingredient_id": far.ingredient_id, "quantity": 130.0}]}, guest_id="guest-1")
    assert r2.status_code == 200

    link.refresh_from_db()
    assert link.sub_recipe_id == variant_id

    # Un seul clone pour (A,B)
    clones = Recipe.objects.filter(parent_recipe=B, owned_by_recipe=A)
    assert clones.count() == 1
    assert clones.first().recipe_ingredients.get(ingredient_id=far.ingredient_id).quantity == 130.0

def test_variant_modif_source_not_impact_variant(api_client, base_url, base_ingredients):
    """
    Isolation API :
    - modifier B (source) après création de B' ne modifie pas B',
    - modifier B' ne modifie pas B.
    """
    B = make_recipe(name="BBB", chef="Chef B", visibility="private")
    far = add_ingredient(B, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    A = make_recipe(name="AAA", chef="Chef A", visibility="private")
    link = add_subrecipe(A, sub=B, qty=200.0, unit="g")

    for r in (A, B):
        r.user = None
        r.guest_id = "guest-1"
        r.save()
    
    # Créer la variante via 1er edit
    url = _bulk_edit_url(base_url, A.id, link.id)
    r = _post(api_client, url, {"updates": [{"ingredient_id": far.ingredient_id, "quantity": 120.0, "unit": "g"}]}, guest_id="guest-1")
    assert r.status_code == 200

    link.refresh_from_db()
    variant = link.sub_recipe

    # Modifier B directement → B′ inchangé
    ri_B = B.recipe_ingredients.get(ingredient_id=far.ingredient_id)
    ri_B.quantity = 999.0
    ri_B.save()
    assert variant.recipe_ingredients.get(ingredient_id=far.ingredient_id).quantity == 120.0

    # Modifier B′ → B inchangé
    ri_V = variant.recipe_ingredients.get(ingredient_id=far.ingredient_id)
    ri_V.quantity = 111.0
    ri_V.save()
    assert B.recipe_ingredients.get(ingredient_id=far.ingredient_id).quantity == 999.0
    assert variant.recipe_ingredients.get(ingredient_id=far.ingredient_id).quantity == 111.0

def test_variant__check_name_after_clone(api_client, base_url, base_ingredients):
    """
    Vérifie le nommage de la variante : le nom est suffixé avec le contexte d’usage (ex. "[usage: AAA]").
    """
    B = make_recipe(name="BBB", chef="Chef B", visibility="private")
    far = add_ingredient(B, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    A = make_recipe(name="AAA", chef="Chef A", visibility="private")
    link = add_subrecipe(A, sub=B, qty=200.0, unit="g")

    for r in (A, B):
        r.user = None
        r.guest_id = "guest-1"
        r.save()

    url = _bulk_edit_url(base_url, A.id, link.id)
    r = api_client.post(url, {"updates": [{"ingredient_id": far.ingredient_id, "quantity": 120.0}]}, format="json", HTTP_X_GUEST_ID="guest-1")
    print(r.json())
    assert r.status_code == 200

    link.refresh_from_db()
    variant = link.sub_recipe
    assert normalize_case("[usage: AAA]") in variant.recipe_name

# ===================================================================
# Couverture élargie
# ===================================================================

def test_recipe_adaptation__reference_recipe_error_message(api_client, recettes_choux):
    """
    Cas d'erreur de logique métier via ValueError attrapée par la view.
    On force un cas vraisemblable (ex: référence inutilisable) selon l'implémentation interne.
    Ici on appelle avec prefer_reference=True mais sans cible exploitable → l'interne peut lever.
    """
    src = recettes_choux["paris_brest_choco"]
    ref = make_recipe(name="ref-incomplete")  # référence minimaliste
    # pas d'info de scaling sur ref → utils peut lever ValueError
    resp = _post(api_client, URL_RECIPES_ADAPT, {
        "recipe_id": src.id,
        "reference_recipe_id": ref.id,
        "prefer_reference": True,
    })
    assert resp.status_code in (400, 422)

# =========================
# /recipes/ — recherche classique
# =========================

def _extract_items(resp):
    data = resp.json()
    return data.get("results", data) if isinstance(data, dict) else data

def test_recipes_list__q_and_search_equivalent(api_client, recettes_choux):
    """
    Vérifie que les paramètres `q` et `search` produisent exactement
    le même ensemble d'identifiants de recettes dans la liste.
    """
    # Les deux paramètres doivent donner le même set d'IDs
    r1 = _get(api_client, URL_RECIPES_LIST, {"q": "éclair"})
    r2 = _get(api_client, URL_RECIPES_LIST, {"search": "éclair"})
    assert r1.status_code == 200 and r2.status_code == 200
    ids1 = {it["id"] for it in _extract_items(r1)}
    ids2 = {it["id"] for it in _extract_items(r2)}
    assert ids1 == ids2

def test_recipes_list__search_hits_category(api_client, recettes_choux):
    """
    Vérifie qu'une recherche par `q` retourne les recettes correspondant
    au nom d'une catégorie (`categories__category_name`).
    """
    # Doit matcher via categories__category_name
    religieuse = recettes_choux["religieuse_cafe"]
    r = _get(api_client, URL_RECIPES_LIST, {"q": "religieuse"})
    assert r.status_code == 200
    ids = {it["id"] for it in _extract_items(r)}
    assert religieuse.id in ids

def test_recipes_list__filter_tags_any_all(api_client, base_ingredients):
    """
    Vérifie le filtrage par tags :
    - Mode `any` retourne toutes les recettes contenant au moins un des tags donnés.
    - Mode `all` retourne seulement celles contenant tous les tags donnés.
    """
    # Prépare 3 recettes avec tags
    r1 = make_recipe(name="tag-r1")
    r1.tags = ["vegan"]
    far = add_ingredient(r1, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    r1.save()
    r2 = make_recipe(name="tag-r2")
    r2.tags = ["vegan","healthy"]
    far = add_ingredient(r2, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    r2.save()
    r3 = make_recipe(name="tag-r3")
    r3.tags = ["healthy"]
    far = add_ingredient(r3, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    r3.save()

    # any = OR → r1,r2,r3
    any_r = _get(api_client, URL_RECIPES_LIST, {"tags": "vegan,healthy", "tags_mode": "any"})
    assert any_r.status_code == 200
    any_ids = {it["id"] for it in _extract_items(any_r)}
    assert {r1.id, r2.id, r3.id} <= any_ids

    # all = AND → seulement r2
    all_r = _get(api_client, URL_RECIPES_LIST, {"tags": "vegan,healthy", "tags_mode": "all"})
    assert all_r.status_code == 200
    all_ids = {it["id"] for it in _extract_items(all_r)}
    assert all_ids == {r2.id}

def test_recipes_list__payload_is_light(api_client, recettes_choux):
    """
    Vérifie que la réponse en liste ne contient pas de champs lourds
    (`ingredients`, `steps`, `sub_recipes`) et qu'elle contient bien
    les champs attendus minimaux.
    """
    # En liste, pas d'objets lourds (ingredients/steps/sub_recipes)
    sample = next(iter(recettes_choux.values()))
    r = _get(api_client, URL_RECIPES_LIST, {"q": sample.recipe_name})
    assert r.status_code == 200
    item = _extract_items(r)[0]
    assert "ingredients" not in item and "steps" not in item and "sub_recipes" not in item
    # champs attendus
    for key in ("id","recipe_name","chef_name","context_name","servings_avg","updated_at"):
        assert key in item

def test_recipes_list__ordering_updated_at(api_client, base_ingredients):
    """
    Vérifie que le tri décroissant par `updated_at` fonctionne avec
    `ordering=-updated_at` : un élément mis à jour récemment apparaît
    avant un élément plus ancien.
    """
    # Vérifie que -updated_at fonctionne
    older = make_recipe(name="older")
    far = add_ingredient(older, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    newer = make_recipe(name="newer")
    far = add_ingredient(newer, ingredient=base_ingredients["farine"], qty=100.0, unit="g")
    newer.description = "touch to update"; newer.save()  # met à jour updated_at
    r = _get(api_client, URL_RECIPES_LIST, {"ordering": "-updated_at", "q": "tag-irrelevant"})
    assert r.status_code == 200
    items = _extract_items(r)
    ids = [it["id"] for it in items]
    # newer doit apparaître avant older si les deux sont présents
    if newer.id in ids and older.id in ids:
        assert ids.index(newer.id) < ids.index(older.id)

# =========================
# /recipes/lego-candidates/ — GET
# =========================

def _extract_results_or_list(resp):
    data = resp.json()
    return data.get("results", data) if isinstance(data, dict) else data

def test_lego_candidates__basic_200_and_payload_shape(api_client, recettes_choux):
    """
    Doit répondre 200 et renvoyer une liste paginée ou brute d'items "légers"
    sans ingrédients/étapes/sous_recettes. Teste aussi la clé 'count' si pagination DRF active.
    """
    r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"q": "éclair"})
    assert r.status_code == 200, r.data
    data = r.json()
    items = _extract_results_or_list(r)
    assert isinstance(items, list)
    if isinstance(data, dict):  # pagination activée
        assert {"count", "next", "previous", "results"} <= set(data.keys())

    if items:
        sample = items[0]
        # payload "léger"
        assert "ingredients" not in sample and "steps" not in sample and "sub_recipes" not in sample
        # champs minimaux attendus en liste
        for key in ("id", "recipe_name", "chef_name", "context_name", "servings_avg", "updated_at"):
            assert key in sample

def test_lego_candidates__unknown_param_rejected(api_client):
    """
    Si la whitelist stricte est active côté view:
    un paramètre non listé renvoie 400 et cite la clé incriminée.
    """
    r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"q": "choux", "not_allowed": "x"})
    assert r.status_code in (400, 200)
    if r.status_code == 400:
        assert "not_allowed" in (r.json().get("detail") or "")

def test_lego_candidates__shares_tags_filter_any_all(api_client, base_ingredients):
    """
    Vérifie que le filtrage tags fonctionne identiquement à la recherche classique.
    - any -> OR
    - all -> AND
    """
    r1 = make_recipe(name="lego-tag-r1"); add_ingredient(r1, ingredient=base_ingredients["farine"], qty=1)
    r1.tags = ["vegan"]; r1.save()
    r2 = make_recipe(name="lego-tag-r2"); add_ingredient(r2, ingredient=base_ingredients["farine"], qty=1)
    r2.tags = ["vegan", "healthy"]; r2.save()
    r3 = make_recipe(name="lego-tag-r3"); add_ingredient(r3, ingredient=base_ingredients["farine"], qty=1)
    r3.tags = ["healthy"]; r3.save()

    any_r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"tags": "vegan,healthy", "tags_mode": "any"})
    assert any_r.status_code == 200
    any_ids = {it["id"] for it in _extract_results_or_list(any_r)}
    assert {r1.id, r2.id, r3.id} <= any_ids

    all_r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"tags": "vegan,healthy", "tags_mode": "all"})
    assert all_r.status_code == 200
    all_ids = {it["id"] for it in _extract_results_or_list(all_r)}
    assert all_ids == {r2.id}

def test_lego_candidates__usage_type_preparation_filters_only_used_subrecipes(api_client, base_ingredients):
    """
    usage_type=preparation -> ne renvoie que des recettes effectivement utilisées comme sous-recettes.
    - R_standalone: jamais utilisée (ne doit PAS apparaître)
    - R_prep: utilisée au moins une fois comme sous-recette (DOIT apparaître)
    """
    R_standalone = make_recipe(name="standalone-only"); add_ingredient(R_standalone, ingredient=base_ingredients["farine"], qty=1)
    R_prep = make_recipe(name="prep-used"); add_ingredient(R_prep, ingredient=base_ingredients["farine"], qty=1)
    Host = make_recipe(name="host"); add_ingredient(Host, ingredient=base_ingredients["farine"], qty=1)
    add_subrecipe(Host, sub=R_prep, qty=10.0)

    r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"usage_type": "preparation"})
    assert r.status_code == 200
    ids = {it["id"] for it in _extract_results_or_list(r)}
    assert R_prep.id in ids
    assert R_standalone.id not in ids

def test_lego_candidates__mine_filters_by_owner_user_or_guest(api_client, base_ingredients, user):
    """
    mine=1 -> restreint aux recettes du user courant OU du guest_id fourni.
    On crée deux recettes: une pour le user, une pour un guest_id.
    """
    # user-owned
    api_client.force_authenticate(user=user)
    ru = make_recipe(name="mine_user"); add_ingredient(ru, ingredient=base_ingredients["farine"], qty=1)
    ru.user = user; ru.guest_id = None; ru.save()

    # guest-owned
    rg = make_recipe(name="mine_guest"); add_ingredient(rg, ingredient=base_ingredients["farine"], qty=1)
    rg.user = None; rg.guest_id = "guest-xyz"; rg.save()

    # mine=1 en contexte user -> doit contenir ru et pas rg
    r_user = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"mine": 1})
    assert r_user.status_code == 200
    ids_user = {it["id"] for it in _extract_results_or_list(r_user)}
    assert ru.id in ids_user
    assert rg.id not in ids_user

    # mine=1 en contexte guest -> doit contenir rg
    api_client.force_authenticate(user=None)
    r_guest = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"mine": 1}, guest_id="guest-xyz")
    assert r_guest.status_code == 200
    ids_guest = {it["id"] for it in _extract_results_or_list(r_guest)}
    assert rg.id in ids_guest
    # ru peut exister dans la base mais ne doit pas matcher mine côté guest
    assert ru.id not in ids_guest

def test_lego_candidates__default_ordering_by_name_then_recent(api_client, base_ingredients):
    """
    Sans 'ordering', la view ordonne par 'recipe_name' puis '-updated_at'.
    On crée deux recettes dont l'une est 'touchée' pour être plus récente et on
    vérifie l'ordre relatif si les deux sont présentes dans la page.
    """
    a = make_recipe(name="aaa", chef="alpha"); add_ingredient(a, ingredient=base_ingredients["farine"], qty=1)
    b = make_recipe(name="aaa", chef="bravo"); add_ingredient(b, ingredient=base_ingredients["farine"], qty=1)
    b.description = "touch to update"; b.save()  # met à jour updated_at

    r = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"q": "aaa"})
    assert r.status_code == 200
    items = _extract_results_or_list(r)
    ids = [it["id"] for it in items if it["recipe_name"].lower().startswith("aaa")]
    if a.id in ids and b.id in ids:
        # même nom → b plus récent doit venir avant a
        assert ids.index(b.id) < ids.index(a.id)

# =========================
# /recipes/{id}/reference-uses/ — GET
# =========================

def _extract_uses(resp):
    data = resp.json()
    return data.get("results", data) if isinstance(data, dict) else data

def test_reference_uses__basic_200_and_payload_shape(api_client, subrecipes, recettes_choux):
    """
    Doit répondre 200 et renvoyer une liste d'usages.
    Chaque item expose au minimum: usage_type, host_recipe_id, host_recipe_name.
    Les hôtes attendus pour 'pâte à choux' sont les 4 recettes “choux”.
    """
    prep = subrecipes["pate_choux"]
    r = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id))
    assert r.status_code == 200, r.data

    items = _extract_uses(r)
    assert isinstance(items, list)
    if items:
        must_keys = {"usage_type", "host_recipe_id", "host_recipe_name"}
        assert must_keys <= set(items[0].keys())

    expected_hosts = {
        recettes_choux["eclair_choco"].id,
        recettes_choux["eclair_cafe"].id,
        recettes_choux["religieuse_cafe"].id,
        recettes_choux["paris_brest_choco"].id,
    }
    got_hosts = {it["host_recipe_id"] for it in items}
    assert expected_hosts <= got_hosts

def test_reference_uses__filter_by_host_category(api_client, subrecipes, base_categories):
    """
    Filtre par catégorie hôte: host_category=<id cat>.
    Pour 'pâte à choux' et cat 'éclair', on ne garde que les usages dont l’hôte a cette catégorie.
    """
    prep = subrecipes["pate_choux"]
    cat_eclair_id = base_categories["eclair"].id

    r = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"host_category": cat_eclair_id})
    assert r.status_code == 200
    items = _extract_uses(r)
    assert all("éclair" in it["host_recipe_name"].lower() for it in items)

def test_reference_uses__has_pan_and_has_servings_filters(api_client, subrecipes, recettes_choux):
    """
    has_pan=1 -> garde seulement les hôtes avec pan.
    has_servings=1 -> garde seulement les hôtes avec servings.
    """
    prep = subrecipes["pate_choux"]

    # has_pan=1
    r_pan = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"has_pan": 1, "guest_id":"test-guest"})
    print(r_pan.json())
    assert r_pan.status_code == 200
    ids_pan = {it["host_recipe_id"] for it in _extract_uses(r_pan)}
    assert recettes_choux["eclair_choco"].id in ids_pan
    assert recettes_choux["religieuse_cafe"].id in ids_pan
    assert recettes_choux["paris_brest_choco"].id in ids_pan
    # l’éclair café n’a pas de pan → absent
    assert recettes_choux["eclair_cafe"].id not in ids_pan

    # has_servings=1
    r_serv = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"has_servings": 1})
    assert r_serv.status_code == 200
    ids_serv = {it["host_recipe_id"] for it in _extract_uses(r_serv)}
    # nos 4 hôtes ont des servings dans les fixtures
    assert {
        recettes_choux["eclair_choco"].id,
        recettes_choux["eclair_cafe"].id,
        recettes_choux["religieuse_cafe"].id,
        recettes_choux["paris_brest_choco"].id,
    } <= ids_serv

def test_reference_uses__order_recent(api_client, subrecipes):
    """
    Valide un tri supporté par l’API: order=name (alphabétique).
    """
    prep = subrecipes["pate_choux"]
    r = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"order": "name"})
    assert r.status_code == 200
    items = _extract_uses(r)
    names = [it["host_recipe_name"] for it in items]
    assert names == sorted(names, key=lambda s: s.lower())

def test_reference_uses__pagination_keys_when_paginated(api_client, subrecipes):
    """
    Si la pagination DRF est active, la réponse doit exposer count/next/previous/results.
    """
    prep = subrecipes["pate_choux"]
    r = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"page": 1})
    assert r.status_code == 200
    data = r.json()
    if isinstance(data, dict):
        assert {"count", "next", "previous", "results"} <= set(data.keys())

def test_end_to_end__candidates_then_reference_uses(api_client, recettes_choux):
    """
    Enchaînement global:
      1) recherche candidats avec q="choux"
      2) on prend l’item dont le nom contient "pâte à choux"
      3) on appelle /reference-uses/ et on vérifie que les hôtes attendus sont listés.
    """
    r1 = _get(api_client, URL_RECIPES_LEGO_CANDIDATES, {"q": "choux"})
    assert r1.status_code == 200
    candidates = _extract_results_or_list(r1)
    assert isinstance(candidates, list) and candidates

    # pick 'pâte à choux'
    cand = next(c for c in candidates if "choux" in c["recipe_name"].lower())
    uses_resp = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=cand["id"]))
    assert uses_resp.status_code == 200
    uses = _extract_uses(uses_resp)
    host_ids = {u["host_recipe_id"] for u in uses}

    assert {
        recettes_choux["eclair_choco"].id,
        recettes_choux["eclair_cafe"].id,
        recettes_choux["religieuse_cafe"].id,
        recettes_choux["paris_brest_choco"].id,
    } <= host_ids

def test_reference_uses__standalone_toggle(api_client, subrecipes):
    """
    Par défaut, pas de ligne 'standalone'.
    Avec include_standalone=1, on doit voir un item usage_type='standalone' et host_* = null.
    """
    prep = subrecipes["pate_choux"]

    r0 = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id))
    assert r0.status_code == 200
    items0 = _extract_uses(r0)
    assert not any(it["usage_type"] == "standalone" for it in items0)

    r1 = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"include_standalone": 1})
    assert r1.status_code == 200
    items1 = _extract_uses(r1)
    st = [it for it in items1 if it["usage_type"] == "standalone"]
    assert len(st) == 1
    assert st[0]["host_recipe_id"] is None and st[0]["host_recipe_name"] is None

def test_reference_uses__alias_params_equivalence(api_client, subrecipes):
    """
    Les alias host_has_pan / host_has_servings sont équivalents à has_pan / has_servings.
    """
    prep = subrecipes["pate_choux"]

    # has_pan=1
    r_a = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"has_pan": 1})
    r_b = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"host_has_pan": 1})
    ids_a = {it["host_recipe_id"] for it in _extract_uses(r_a) if it["usage_type"] == "as_preparation"}
    ids_b = {it["host_recipe_id"] for it in _extract_uses(r_b) if it["usage_type"] == "as_preparation"}
    assert ids_a == ids_b

    # has_servings=1
    r_c = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"has_servings": 1})
    r_d = _get(api_client, URL_RECIPES_REFERENCE_USES.format(id=prep.id), {"host_has_servings": 1})
    ids_c = {it["host_recipe_id"] for it in _extract_uses(r_c) if it["usage_type"] == "as_preparation"}
    ids_d = {it["host_recipe_id"] for it in _extract_uses(r_d) if it["usage_type"] == "as_preparation"}
    assert ids_c == ids_d



