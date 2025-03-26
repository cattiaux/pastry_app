import pytest
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import (
    validate_constraint_api, validate_unique_constraint_api, validate_field_normalization_api,
    validate_update_to_duplicate_api, normalize_case)

pytestmark = pytest.mark.django_db
model_name = "recipes"

# ----------------------------------------
# Base data helper
# ----------------------------------------

def base_data(**overrides):
    """Retourne un dictionnaire de données valides pour une recette."""
    data = {
        "recipe_name": "Tarte Normande",
        "chef_name": "Chef Normand",
        "recipe_type": "BASE",
        "servings_min": 6,
        "servings_max": 6,
        "steps": [{"step_number": 1, "instruction": "Préchauffer le four."}],
        "ingredients": [{"ingredient_name": "Pommes", "quantity": 300, "unit": "g"}],
        "pan_quantity": 1,
    }
    data.update(overrides)
    return data

@pytest.mark.parametrize("field_name", ["recipe_name", "chef_name", "recipe_type"])
def test_required_fields_recipe_api(api_client, base_url, field_name):
    data = base_data()
    data[field_name] = None
    validate_constraint_api(api_client, base_url, model_name, field_name, "This field may not be null.", **data)

@pytest.mark.parametrize("field_name, min_length", [("description", 10), ("trick", 10), ("context_name", 3), ("source", 3)])
def test_min_length_fields_recipe_api(api_client, base_url, field_name, min_length):
    data = base_data()
    data[field_name] = "a" * (min_length - 1)
    validate_constraint_api(api_client, base_url, model_name, field_name, "doit contenir au moins", **data)

@pytest.mark.parametrize("field_name, value", [("description", ""), ("trick", None), ("context_name", ""), ("source", None)])
def test_optional_fields_recipe_api(api_client, base_url, field_name, value):
    data = base_data()
    data[field_name] = value
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == status.HTTP_201_CREATED

@pytest.mark.parametrize("field_name, raw_value", [
    ("recipe_name", "  TARTE citron  "),
    ("chef_name", "  cédric GROLET "),
    ("context_name", "  INSTAGRAM "),
    ("source", "  www.site.com  ")
])
def test_normalized_fields_recipe_api(api_client, base_url, field_name, raw_value):
    data = base_data()
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **data)

# ----------------------------------------
# Servings validations
# ----------------------------------------

@pytest.mark.parametrize("field_name, invalid_value", [
    ("servings_min", 0), ("servings_max", -1)
])
def test_servings_must_be_positive_recipe_api(api_client, base_url, field_name, invalid_value):
    data = base_data()
    data[field_name] = invalid_value
    expected_error = "Ensure this value is greater than or equal to 1."
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_error, **data)

@pytest.mark.parametrize("s_min, s_max, should_raise", [(10, 6, True), (4, 8, False)])
def test_servings_min_max_coherence_recipe_api(api_client, base_url, s_min, s_max, should_raise):
    data = base_data(servings_min=s_min, servings_max=s_max)
    response = api_client.post(base_url(model_name), data, format="json")
    if should_raise:
        assert response.status_code == 400
        assert "minimal" in str(response.json()).lower()
    else:
        assert response.status_code == 201

# ----------------------------------------
# Unicité
# ----------------------------------------

def test_unique_constraint_recipe_api(api_client, base_url):
    data = base_data(recipe_name="Cake Vanille", chef_name="Pierre Hermé",
                     context_name="Entremet Signature", source="Livre 2022")
    validate_unique_constraint_api(api_client, base_url, model_name, "recipe_name", **data)

def test_update_to_duplicate_recipe_api(api_client, base_url):
    data1 = base_data(recipe_name="Recette A", chef_name="Chef A", context_name="Instagram", source="Livre A")
    data2 = base_data(recipe_name="Recette B", chef_name="Chef B", context_name="Instagram", source="Livre A")
    validate_update_to_duplicate_api(api_client, base_url, model_name, data1, data2)

# ----------------------------------------
# Logique métier : parent, variation, cycles, contenu
# ----------------------------------------

def test_cannot_be_own_parent(api_client, base_url):
    data = base_data()
    response = api_client.post(base_url(model_name), data, format="json")
    recipe_id = response.data["id"]

    patch_data = {"parent_recipe": recipe_id, "recipe_type": "VARIATION"}
    response = api_client.patch(base_url(model_name) + f"{recipe_id}/", patch_data, format="json")
    assert response.status_code == 400
    assert "propre version" in str(response.data).lower()

def test_variation_requires_parent(api_client, base_url):
    data = base_data(recipe_type="VARIATION")
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "doit avoir une parent_recipe" in str(response.data).lower()

def test_parent_requires_variation_type(api_client, base_url):
    parent = api_client.post(base_url(model_name), base_data(), format="json").data
    child = base_data(recipe_type="BASE", parent_recipe=parent["id"], recipe_name="Sous-recette")
    response = api_client.post(base_url(model_name), child, format="json")
    assert response.status_code == 400
    assert "doit être de type variation" in str(response.data).lower()

def test_cycle_detection_indirect(api_client, base_url):
    a = api_client.post(base_url(model_name), base_data(recipe_name="A"), format="json").data
    b = api_client.post(base_url(model_name), base_data(recipe_name="B", parent_recipe=a["id"], recipe_type="VARIATION"), format="json").data
    c = api_client.post(base_url(model_name), base_data(recipe_name="C", parent_recipe=b["id"], recipe_type="VARIATION"), format="json").data

    patch = {"parent_recipe": c["id"], "recipe_type": "VARIATION"}
    response = api_client.patch(base_url(model_name) + f"{a['id']}/", patch, format="json")
    assert response.status_code == 400
    assert "cycle détecté" in str(response.data).lower()

def test_recipe_requires_ingredient_or_subrecipe(api_client, base_url):
    data = base_data()
    data.pop("ingredients")
    data.pop("sub_recipes", None)
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "au moins un ingrédient ou une sous-recette" in str(response.data).lower()

def test_recipe_requires_step(api_client, base_url):
    data = base_data()
    data.pop("steps")
    data.pop("sub_recipes", None)
    response = api_client.post(base_url(model_name), data, format="json")
    assert response.status_code == 400
    assert "au moins une étape" in str(response.data).lower()