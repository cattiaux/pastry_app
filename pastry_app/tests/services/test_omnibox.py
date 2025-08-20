# tests/services/test_omnibox_api.py
import pytest
from django.contrib.auth import get_user_model
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.models import Recipe, Ingredient, Pan, Category, Label, Store, UserRecipeVisibility
from pastry_app.text_utils import *

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/search/"

User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

def test_search_requires_q(api_client):
    r = api_client.get(SEARCH_URL)
    assert r.status_code == 400
    assert "error" in r.data

def test_search_rejects_invalid_entities(api_client):
    r = api_client.get(SEARCH_URL, {"q": "a", "entities": "recipes,foo"})
    assert r.status_code == 400
    assert "invalides" in str(r.data).lower() or "invalid" in str(r.data).lower()

def test_search_defaults_and_limit(api_client):
    Ingredient.objects.create(ingredient_name="Pomme")
    Store.objects.create(store_name="Super U", city="Paris")
    Recipe.objects.create(recipe_name="Tarte Pomme", chef_name="Alice", visibility="public")

    r = api_client.get(SEARCH_URL, {"q": "p", "limit": 1})  # defaults entities: recipes,ingredients,stores
    assert r.status_code == 200
    for key in ("q", "limit", "entities"):
        assert key in r.data
    # chaque entité par défaut présente, taille ≤ 1
    for ent in ("recipes", "ingredients", "stores"):
        assert ent in r.data
        assert isinstance(r.data[ent], list)
        assert len(r.data[ent]) <= 1
        # shape des items
        for it in r.data[ent]:
            assert "title" in it
            assert "score" in it

def test_search_recipes_visibility_and_soft_hide(api_client, user):
    User = get_user_model()
    other = User.objects.create_user(username="other", password="x")

    # public visible
    pub = Recipe.objects.create(recipe_name="Tarte aux Pommes", chef_name="Alice", visibility="public")
    # privé de l'utilisateur courant
    own = Recipe.objects.create(recipe_name="Tarte privée", chef_name="Alice", visibility="private", user=user)
    # privé d'un autre user
    other_private = Recipe.objects.create(recipe_name="Tarte secrète", chef_name="Bob", visibility="private", user=other)
    # soft-hide du public pour user
    UserRecipeVisibility.objects.create(user=user, recipe=pub, visible=False)

    api_client.force_authenticate(user=user)
    r = api_client.get(SEARCH_URL, {"q": "Tarte", "entities": "recipes", "limit": 10})
    assert r.status_code == 200
    titles = [it["title"] for it in r.data.get("recipes", [])]
    assert normalize_case("Tarte privée") in titles
    assert normalize_case("Tarte aux Pommes") not in titles  # soft-hidden
    assert normalize_case("Tarte secrète") not in titles     # privé d’un autre

def test_search_serializers_shapes_per_entity(api_client):
    # seed
    rcp = Recipe.objects.create(recipe_name="Paris-Brest", chef_name="Pierre", context_name="Concours", visibility="public")
    Ingredient.objects.create(ingredient_name="Noisette")
    Pan.objects.create(pan_name="Moule rond 18", pan_type="ROUND", diameter=18, height=5)
    Category.objects.create(category_name="Pâte à choux", category_type="recipe")
    Label.objects.create(label_name="Sans lactose", label_type="both")
    Store.objects.create(store_name="Carrefour", city="Lyon", zip_code="69000")

    r = api_client.get(SEARCH_URL, {"q": "o", "entities": "recipes,ingredients,pans,categories,labels,stores", "limit": 5})
    assert r.status_code == 200

    # RecipeOmniSerializer
    recs = r.data.get("recipes", [])
    if recs:
        it = recs[0]
        assert {"id","title","subtitle","score"} <= set(it.keys())
        # subtitle = "chef · context" si context_name existe
        if rcp.context_name:
            assert normalize_case("Pierre") in it["subtitle"]

    # IngredientOmniSerializer
    ings = r.data.get("ingredients", [])
    if ings:
        assert {"id","title","score"} <= set(ings[0].keys())

    # PanOmniSerializer
    pans = r.data.get("pans", [])
    if pans:
        assert {"id","title","score"} <= set(pans[0].keys())
        # titre doit refléter pan_name
        assert any(normalize_case("Moule rond 18") == p["title"] for p in pans)

    # CategoryOmniSerializer
    cats = r.data.get("categories", [])
    if cats:
        assert {"id","title","score"} <= set(cats[0].keys())

    # LabelOmniSerializer
    labs = r.data.get("labels", [])
    if labs:
        assert {"id","title","score"} <= set(labs[0].keys())

    # StoreOmniSerializer
    stores = r.data.get("stores", [])
    if stores:
        it = stores[0]
        assert {"id","title","subtitle","score"} <= set(it.keys())

def test_search_sorted_by_score_desc(api_client):
    # deux ingrédients proches pour tester l’ordre par score
    Ingredient.objects.create(ingredient_name="pomme")
    Ingredient.objects.create(ingredient_name="compote de pomme")

    r = api_client.get(SEARCH_URL, {"q": "pomme", "entities": "ingredients", "limit": 10})
    assert r.status_code == 200
    items = r.data.get("ingredients", [])
    # tous ont un score
    scores = [it["score"] for it in items]
    assert all(isinstance(s, (int, float)) for s in scores)
    # ordre non croissant
    assert scores == sorted(scores, reverse=True)

def test_search_limit_is_per_entity_and_bounded(api_client):
    Ingredient.objects.bulk_create([Ingredient(ingredient_name=f"ing{i}") for i in range(20)])
    r = api_client.get(SEARCH_URL, {"q": "ing", "entities": "ingredients,stores", "limit": 100})
    assert r.status_code == 200
    # limit max = 10 par entité
    assert len(r.data.get("ingredients", [])) <= 10
    # stores peut être vide si non match, mais la clé existe pas forcément; c’est OK
