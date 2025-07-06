import pytest, json, re
from rest_framework import status
from django.contrib.auth import get_user_model
from pastry_app.tests.utils import *
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.models import Pan

model_name = "pans"
pytestmark = pytest.mark.django_db
User = get_user_model()
 
@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def pan(db):
    return Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="Mon Moule", units_in_mold=3)

@pytest.mark.parametrize("field_name", ["pan_type", "unit"])
def test_choices_validation_pan_api(api_client, base_url, field_name):
    """Vérifie que seuls les choix valides sont acceptés pour certains champs"""
    url = base_url(model_name)
    valid_data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3"}
    valid_data[field_name] = "invalid"
    response = api_client.post(url, data=valid_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()

@pytest.mark.parametrize("field_name", ["pan_type", "volume_raw", "unit"])
def test_required_fields_pan_api(api_client, base_url, field_name):
    """Vérifie que les champs obligatoires sont bien requis selon le type"""
    expected_errors = ["This field is required.", "Unité requise pour un moule personnalisé.", "Volume requis pour un moule personnalisé."]
    base_data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3"}
    base_data.pop(field_name)
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **base_data)

def test_unique_constraint_api(api_client, base_url):
    """Vérifie que le champ `pan_name` est unique via l'API (même après normalisation)"""
    valid_data = {"pan_type": "CUSTOM", "volume_raw": 800, "unit": "cm3", "pan_name": "mon moule"}
    response = validate_unique_constraint_api(api_client, base_url, model_name, "pan_name", create_initiate=False, **valid_data)
    assert "pan_name" in response.json()

@pytest.mark.parametrize("field_name, raw_value", [
    ("pan_name", "  Mon Moule  "),
    ("pan_brand", "  DEBUYER  ")
])
def test_normalized_fields_pan_api(api_client, base_url, field_name, raw_value):
    """Vérifie que `pan_name` et `pan_brand` sont bien normalisés via l’API"""
    url = base_url(model_name)
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3"}
    data[field_name] = raw_value
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[field_name] == normalize_case(raw_value)

@pytest.mark.parametrize("field_name", ["pan_name", "pan_brand"])
def test_min_length_fields_api(api_client, base_url, field_name):
    url = base_url(model_name)
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3"}
    data[field_name] = "a"
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()

@pytest.mark.parametrize("invalid_combo, expected_error", [
    ({"pan_type": "ROUND", "height": 4}, "requis pour un moule rond"),
    ({"pan_type": "ROUND", "diameter": 16}, "requis pour un moule rond"),
    ({"pan_type": "RECTANGLE", "width": 10, "rect_height": 3}, "requis pour un moule rectangulaire"),
    ({"pan_type": "CUSTOM", "unit": "cm3"}, "volume requis pour un moule personnalisé"),
    ({"pan_type": "CUSTOM", "volume_raw": 1000}, "unité"),
])
def test_clean_validation_errors_pan_api(api_client, base_url, invalid_combo, expected_error):
    """Vérifie que les validations métier (`clean`) fonctionnent aussi via l’API"""
    url = base_url(model_name)
    response = api_client.post(url, data=json.dumps(invalid_combo), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # assert expected_error.lower() in json.dumps(response.json()).lower()
    flat_messages = " ".join([msg for messages in response.json().values() for msg in messages])
    assert expected_error.lower() in flat_messages.lower()

def test_update_to_duplicate_name_api(api_client, base_url, user):
    """Vérifie qu'on ne peut PAS modifier un Pan pour lui attribuer un nom déjà existant"""
    api_client.force_authenticate(user=user)
    pan1 = Pan.objects.create(user=user, pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="Original")
    pan2 = Pan.objects.create(user=user, pan_type="CUSTOM", volume_raw=800, unit="cm3", pan_name="Unique")
    url = base_url(model_name) + f"{pan2.id}/"
    response = api_client.patch(url, data={"pan_name": "Original"}, format="json")
    print(response.json())  # Pour débogage
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pan_name" in response.json()

def test_read_only_volume_cm3_api(api_client, base_url):
    url = base_url(model_name)
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3", "volume_cm3": 9999} # tentative d'écrasement
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["volume_cm3"] != 9999
    assert response.json()["volume_cm3"] == 1000

@pytest.mark.parametrize("pan_type, field_name, invalid_value", [
    ("ROUND", "diameter", 0),
    ("ROUND", "height", 0),
    ("RECTANGLE", "length", 0),
    ("RECTANGLE", "width", 0),
    ("RECTANGLE", "rect_height", 0),
    ("CUSTOM", "volume_raw", 0),
])
def test_min_value_constraints_api(api_client, base_url, pan_type, field_name, invalid_value):
    """Vérifie que les champs numériques doivent respecter leur valeur minimale selon pan_type"""
    url = base_url(model_name)

    # Champs de base valides
    base_fields = {"ROUND": {"diameter": 10, "height": 5}, 
                   "RECTANGLE": {"length": 10, "width": 5, "rect_height": 3}, 
                   "CUSTOM": {"volume_raw": 1000, "unit": "cm3"}
                   }[pan_type].copy()

    # On injecte la valeur invalide
    base_fields[field_name] = invalid_value
    data = {"pan_type": pan_type, **base_fields}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()

@pytest.mark.parametrize("pan_type, extra_fields, expected_error", [
    ("ROUND", {"volume_raw": 1000}, "Ce champ n'est pas autorisé pour un moule rond."),
    ("RECTANGLE", {"diameter": 10}, "Ce champ n'est pas autorisé pour un moule rectangulaire."),
    ("CUSTOM", {"length": 20}, "Ce champ n'est pas autorisé pour un moule personnalisé."),
])
def test_post_exclusive_fields_pan_api(api_client, base_url, pan_type, extra_fields, expected_error):
    """Vérifie que l’API rejette les données incohérentes entre type et champs utilisés"""
    url = base_url(model_name)
    valid_base = {"ROUND": {"diameter": 16, "height": 5}, 
                  "RECTANGLE": {"length": 10, "width": 5, "rect_height": 3}, 
                  "CUSTOM": {"volume_raw": 1000, "unit": "cm3"}
                  }[pan_type].copy()
    valid_base.update(extra_fields)
    valid_base["pan_type"] = pan_type
    response = api_client.post(url, data=json.dumps(valid_base), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    flat_messages = " ".join(msg for field_errors in response.json().values() for msg in field_errors)
    assert expected_error.lower() in flat_messages.lower()

def test_patch_exclusive_fields_pan_api(api_client, base_url, user):
    """Vérifie qu’on ne peut pas PATCH un Pan pour lui ajouter un champ incohérent avec son type"""
    api_client.force_authenticate(user=user)
    pan = Pan.objects.create(user=user, pan_type="ROUND", diameter=16, height=5)
    url = base_url(model_name) + f"{pan.id}/"
    patch_data = {"volume_raw": 1000}  # volume pas autorisé pour ROUND
    response = api_client.patch(url, data=patch_data, format="json")
    assert response.status_code == 400
    assert "volume" in json.dumps(response.json()).lower()

def test_patch_partial_fields_api(api_client, base_url, user):
    """Vérifie qu’un PATCH partiel est accepté et ne casse pas les champs non fournis"""
    api_client.force_authenticate(user=user)    
    pan = Pan.objects.create(user=user, pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="Test Pan")
    url = base_url("pans") + f"{pan.id}/"
    patch_data = {"pan_brand": "Debuyer"}
    response = api_client.patch(url, data=json.dumps(patch_data), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["pan_brand"] == normalize_case("Debuyer")
    assert response.json()["pan_name"] == normalize_case("Test Pan")  # Non modifié

def test_volume_cm3_cache_is_returned(api_client, base_url):
    """Vérifie que le champ `volume_cm3_cache` est bien présent et exact dans la réponse API"""
    data = {"pan_type": "CUSTOM", "volume_raw": 1.4, "unit": "L", "pan_name": "volume test"}
    response = api_client.post(base_url(model_name), data=data, format="json")
    assert response.status_code == 201
    assert "volume_cm3_cache" in response.json()
    assert response.json()["volume_cm3_cache"] == 1400

@pytest.mark.parametrize("value", [0, -2])
def test_units_in_mold_validation_api(api_client, base_url, value):
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3", "units_in_mold": value}
    response = api_client.post(base_url(model_name), data=data, format="json")
    assert response.status_code == 400
    assert "units_in_mold" in response.json()

def test_units_in_mold_default_api(api_client, base_url):
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3"}
    response = api_client.post(base_url(model_name), data=data, format="json")
    assert response.status_code == 201
    assert response.json()["units_in_mold"] == 1

def test_api_auto_removes_fields_when_type_changes(api_client, base_url):
    """Vérifie que les champs incompatibles avec un type sont ignorés automatiquement (API)"""
    url = base_url(model_name)
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3", "pan_name": "Test custom"}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == 201

    pan_data = response.json()
    assert pan_data["pan_type"] == "CUSTOM"
    # Vérifie que les champs en trop ne sont pas présents ou sont null
    assert pan_data["diameter"] is None
    assert pan_data["height"] is None
    assert pan_data["length"] is None
    assert pan_data["width"] is None
    assert pan_data["rect_height"] is None