import pytest
from rest_framework import status
from django.contrib.auth import get_user_model
from pastry_app.models import Ingredient, Recipe
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import (
    validate_constraint_api, validate_unique_constraint_api, validate_field_normalization_api,
    validate_update_to_duplicate_api, normalize_case)

pytestmark = pytest.mark.django_db
model_name = "recipes"

User = get_user_model()

@pytest.fixture
def guest_id():
    # Peut être un UUID aléatoire ou une string fixe pour plus de stabilité
    return "test-guest-id-123"

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def other_user():
    return User.objects.create_user(username="user2", password="testpass456")
    
# ----------------------------------------
# Base data helper
# ----------------------------------------

def base_recipe_data(**overrides):
    """Retourne un dictionnaire de données valides pour une recette."""
    ingredient = Ingredient.objects.get_or_create(ingredient_name="Pommes")[0]
    data = {
        "recipe_name": "Tarte Normande",
        "chef_name": "Chef Normand",
        "recipe_type": "BASE",
        "servings_min": 6,
        "servings_max": 6,
        "steps": [{"step_number": 1, "instruction": "Préchauffer le four."}],
        "ingredients": [{"ingredient": ingredient.pk, "quantity": 300, "unit": "g"}],
        "pan_quantity": 1,
        "visibility": "private",
        "is_default": False,
    }
    data.update(overrides)
    return data

@pytest.mark.parametrize("field_name", ["recipe_name", "chef_name", "recipe_type"])
def test_required_fields_recipe_api(api_client, base_url, field_name, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data[field_name] = None
    validate_constraint_api(api_client, base_url, model_name, field_name, "This field may not be null.", **data)

@pytest.mark.parametrize("field_name, min_length", [("description", 10), ("trick", 10), ("context_name", 3), ("source", 3)])
def test_min_length_fields_recipe_api(api_client, base_url, field_name, min_length, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data[field_name] = "a" * (min_length - 1)
    validate_constraint_api(api_client, base_url, model_name, field_name, "doit contenir au moins", **data)

@pytest.mark.parametrize("field_name, value", [("description", ""), ("trick", None), ("context_name", ""), ("source", None)])
def test_optional_fields_recipe_api(api_client, base_url, field_name, value, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data[field_name] = value
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == status.HTTP_201_CREATED

@pytest.mark.parametrize("field_name, raw_value", [
    ("recipe_name", "  TARTE citron  "),
    ("chef_name", "  cédric GROLET "),
    ("context_name", "  INSTAGRAM "),
    ("source", "  www.site.com  ")
])
def test_normalized_fields_recipe_api(api_client, base_url, field_name, raw_value, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **data)

# ----------------------------------------
# Servings validations
# ----------------------------------------

@pytest.mark.parametrize("field_name, invalid_value", [
    ("servings_min", 0), ("servings_max", -1)
])
def test_servings_must_be_positive_recipe_api(api_client, base_url, field_name, invalid_value, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data[field_name] = invalid_value
    expected_error = "Ensure this value is greater than or equal to 1."
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_error, **data)

@pytest.mark.parametrize("s_min, s_max, should_raise", [(10, 6, True), (4, 8, False)])
def test_servings_min_max_coherence_recipe_api(api_client, base_url, s_min, s_max, should_raise, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data(servings_min=s_min, servings_max=s_max)
    response = api_client.post(base_url(model_name), data, format="json")
    if should_raise:
        assert response.status_code == 400
        assert "le nombre de portions minimum ne peut pas être supérieur au maximum." in str(response.json()).lower()
    else:
        assert response.status_code == 201

# ----------------------------------------
# Unicité
# ----------------------------------------

def test_unique_constraint_recipe_api(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data(recipe_name="Cake Vanille", chef_name="Pierre Hermé",
                     context_name="Entremet Signature", source="Livre 2022")
    validate_unique_constraint_api(api_client, base_url, model_name, "recipe_name", create_initiate=False, **data)

def test_update_to_duplicate_recipe_api(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data1 = base_recipe_data(recipe_name="Recette A", chef_name="Chef A", context_name="Instagram", source="Livre A")
    data2 = base_recipe_data(recipe_name="Recette B", chef_name="Chef B", context_name="Instagram", source="Livre A")
    validate_update_to_duplicate_api(api_client, base_url, model_name, data1, data2, create_initiate=False)

# ----------------------------------------
# Logique métier : parent, variation, cycles, contenu
# ----------------------------------------

def test_cannot_be_own_parent(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    response = api_client.post(base_url(model_name), data, format="json")
    recipe_id = response.data["id"]

    patch_data = {"parent_recipe": recipe_id, "recipe_type": "VARIATION"}
    response = api_client.patch(base_url(model_name) + f"{recipe_id}/", patch_data, format="json")
    print(response.json())
    assert response.status_code == 400
    assert "propre version" in str(response.data).lower()

def test_variation_requires_parent(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data(recipe_type="VARIATION")
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "doit avoir une parent_recipe" in str(response.data).lower()

def test_parent_requires_variation_type(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    parent = api_client.post(base_url(model_name), base_recipe_data(), format="json").data
    child = base_recipe_data(recipe_type="BASE", parent_recipe=parent["id"], recipe_name="Sous-recette")
    response = api_client.post(base_url(model_name), child, format="json")
    assert response.status_code == 400
    assert "doit être de type variation" in str(response.data).lower()

def test_cycle_detection_indirect(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    response_a = api_client.post(base_url(model_name), base_recipe_data(recipe_name="AAAA"), format="json")
    response_b = api_client.post(base_url(model_name), base_recipe_data(recipe_name="BBBB", parent_recipe=response_a.data["id"], recipe_type="VARIATION"), format="json")
    response_c = api_client.post(base_url(model_name), base_recipe_data(recipe_name="CCCC", parent_recipe=response_b.data["id"], recipe_type="VARIATION"), format="json")

    patch = {"parent_recipe": response_c.data["id"], "recipe_type": "VARIATION"}
    response = api_client.patch(base_url(model_name) + f"{response_a.data['id']}/", patch, format="json")
    assert response.status_code == 400
    assert "cycle détecté" in str(response.data).lower()

def test_recipe_requires_ingredient_or_subrecipe(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data.pop("ingredients")
    data.pop("sub_recipes", None)
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "au moins un ingrédient ou une sous-recette" in str(response.data).lower()

def test_recipe_requires_step(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    data.pop("steps")
    data.pop("sub_recipes", None)
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "au moins une étape" in str(response.data).lower()

def test_patch_with_steps_is_rejected(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    recipe = api_client.post(base_url(model_name), data=data, format="json").data
    update = {"steps": [{"step_number": 1, "instruction": "Modifié"}]}
    response = api_client.patch(f"{base_url(model_name)}{recipe['id']}/", data=update, format="json")
    assert response.status_code == 400
    assert "steps" in str(response.data).lower()

def test_patch_subrecipe_does_not_affect_parent(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    recipe = api_client.post(base_url(model_name), data=data, format="json").data
    patch = {"description": "Nouvelle description"}
    response = api_client.patch(f"{base_url(model_name)}{recipe['id']}/", data=patch, format="json")
    assert response.status_code == 200
    assert response.data["description"] == "Nouvelle description"

def test_patch_description_does_not_remove_steps(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    recipe = api_client.post(base_url(model_name), data=data, format="json").data
    patch = {"description": "test d'une description"}
    response = api_client.patch(f"{base_url(model_name)}{recipe['id']}/", patch, format="json")
    print(response.json())
    assert response.status_code == 200
    detail = api_client.get(f"{base_url(model_name)}{recipe['id']}/").json()
    assert len(detail["steps"]) == 1

def test_patch_step_does_not_affect_recipe(api_client, base_url, user):
    api_client.force_authenticate(user=user)
    data = base_recipe_data()
    recipe = api_client.post(base_url(model_name), data=data, format="json").data
    step_id = recipe["steps"][0]["id"]
    patch = {"instruction": "Instruction modifiée"}
    url = f"{base_url(model_name)}{recipe['id']}/steps/{step_id}/"
    response = api_client.patch(url, patch, format="json")
    assert response.status_code == 200
    recipe_check = api_client.get(f"{base_url(model_name)}{recipe['id']}/").json()
    assert recipe_check["steps"][0]["instruction"] == "Instruction modifiée"

# --- Tests de validation métier : adaptation de recettes ---

def test_adaptation_note_requires_parent(api_client, base_url, user):
    """On ne peut ajouter adaptation_note que si parent_recipe est défini (ici, que via l’endpoint adapté)."""
    api_client.force_authenticate(user=user)
    # Essaye de créer une recette sans parent, avec adaptation_note
    payload = base_recipe_data(recipe_name="BadAdapt", adaptation_note="Doit échouer")
    resp = api_client.post(base_url(model_name), payload, format="json")
    assert "adaptation_note" in resp.json() or resp.status_code == 400

def test_adaptation_of_adaptation_points_to_mother(api_client, base_url, user):
    """Adapter une adaptation rattache bien la nouvelle adaptation à la recette mère, pas à l'adaptation."""
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    # Crée la mère
    resp_mother = api_client.post(url, base_recipe_data(), format="json")
    mother_id = resp_mother.data["id"]
    # Crée une adaptation 1
    resp_adapt1 = api_client.post(f"{url}{mother_id}/adapt/", base_recipe_data(recipe_name="var1"), format="json")
    adapt1_id = resp_adapt1.data["id"]
    # Crée adaptation2 sur adaptation1
    resp_adapt2 = api_client.post(f"{url}{adapt1_id}/adapt/", base_recipe_data(recipe_name="var2"), format="json")
    assert resp_adapt2.status_code == 201
    adapt2 = resp_adapt2.data
    # L'adaptation finale pointe bien sur la mère
    assert adapt2["parent_recipe"] == mother_id

def test_adaptation_permissions(api_client, base_url, user, other_user):
    """Seul le créateur (ou admin) peut modifier son adaptation, pas les autres."""
    url= base_url(model_name)
    api_client.force_authenticate(user=user)
    mother = api_client.post(url, base_recipe_data(), format="json").data
    fork = api_client.post(f"{url}{mother['id']}/adapt/", base_recipe_data(recipe_name="forky"), format="json").data
    fork_url = f"{url}{fork['id']}/"

    # User peut modifier
    resp = api_client.patch(fork_url, {"recipe_name": "update"}, format="json")
    assert resp.status_code == 200

    # Un autre user ne peut pas modifier
    api_client.force_authenticate(user=other_user)
    resp2 = api_client.patch(fork_url, {"recipe_name": "forbidden"}, format="json")
    assert resp2.status_code in [403, 404]

def test_adaptation_permissions_guest(api_client, base_url, guest_id):
    """Un invité ne peut modifier/supprimer QUE ses propres adaptations."""
    url= base_url(model_name)
    # Crée la recette mère
    mother = api_client.post(url, base_recipe_data(visibility="public"), format="json").data
    # Invité A adapte la recette
    payload = base_recipe_data(recipe_name="forky", steps=[{"step_number": 1, "instruction": "Go"}])
    fork = api_client.post(f"{url}{mother['id']}/adapt/", payload, format="json", HTTP_X_GUEST_ID=guest_id).data
    fork_url = f"{url}{fork['id']}/"

    # Invité A peut modifier
    resp = api_client.patch(fork_url, {"recipe_name": "updated"}, format="json", HTTP_X_GUEST_ID=guest_id)
    assert resp.status_code == 200

    # Invité B ne peut pas modifier
    resp2 = api_client.patch(fork_url, {"recipe_name": "forbidden"}, format="json", HTTP_X_GUEST_ID="other-guest-id")
    assert resp2.status_code == 403

    # Invité B ne peut pas supprimer non plus
    resp3 = api_client.delete(fork_url, HTTP_X_GUEST_ID="other-guest-id")
    assert resp3.status_code == 403

    # Invité A peut supprimer
    resp4 = api_client.delete(fork_url, HTTP_X_GUEST_ID=guest_id)
    assert resp4.status_code in (204, 200)

def test_filter_adaptations_by_parent(api_client, base_url, user):
    """ Le filtrage sur parent_recipe ne retourne que les adaptations (pas la mère). """
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    # Crée une recette mère
    response = api_client.post(url, base_recipe_data(recipe_name="Mère"), format="json")
    parent_id = response.json()["id"]

    # Crée deux adaptations
    resp1 = api_client.post(url, base_recipe_data(recipe_name="Adapt1", parent_recipe=parent_id, recipe_type="VARIATION"), format="json")
    assert resp1.status_code == 201, resp1.data
    resp2 = api_client.post(url, base_recipe_data(recipe_name="Adapt2", parent_recipe=parent_id, recipe_type="VARIATION"), format="json")
    assert resp2.status_code == 201, resp2.data

    # Filtre
    resp = api_client.get(f"{url}?parent_recipe={parent_id}")
    names = [r["recipe_name"] for r in resp.json()]
    print("names : ", names)
    assert normalize_case("Adapt1") in names
    assert normalize_case("Adapt2") in names
    assert "Mère" not in names  # La recette mère ne doit pas apparaître dans le filtrage

def test_cannot_delete_mother_with_adaptations(api_client, base_url, user):
    url = base_url(model_name)
    api_client.force_authenticate(user=user)
    # Crée la mère
    mother = api_client.post(url, base_recipe_data(), format="json").data
    # Crée une adaptation
    api_client.post(f"{url}{mother['id']}/adapt/", base_recipe_data(recipe_name="forked"), format="json")
    # Tente de supprimer la mère
    resp = api_client.delete(f"{url}{mother['id']}/")
    assert resp.status_code == 400  # Ou 403 selon ta logique
    assert "adaptation" in str(resp.json()).lower()

def test_soft_hide_base_recipe_for_user(api_client, base_url, user, other_user):
    """
    Un user peut masquer une recette de base UNIQUEMENT pour lui : elle reste visible pour les autres users/invités.
    """
    url = base_url("recipes")
    # Création d'une recette de base par un admin
    base_data = base_recipe_data(recipe_name="BaseMasquee", is_default=True, visibility="public")
    response = api_client.post(url, base_data, format="json")
    base_id = response.data["id"]
    
    # User1 "masque" la recette de base pour lui (simulateur : suppression logique ou table de masquage, à adapter)
    api_client.force_authenticate(user=user)
    hide_resp = api_client.delete(f"{url}{base_id}/")
    print(hide_resp.json())
    assert hide_resp.status_code in (204, 200)  # Soft-delete OK

    # User1 NE VOIT PLUS la recette
    list_resp = api_client.get(url)
    assert all(r["id"] != base_id for r in list_resp.json())

    # User2 la voit toujours
    api_client.force_authenticate(user=other_user)
    list_resp2 = api_client.get(url)
    assert any(r["id"] == base_id for r in list_resp2.json())