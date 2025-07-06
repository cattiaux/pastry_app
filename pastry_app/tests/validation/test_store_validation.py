import pytest
from rest_framework import status
from django.contrib.auth import get_user_model
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.serializers import IngredientSerializer, IngredientPriceSerializer, StoreSerializer

# Définir model_name pour les tests de Store
model_name = "stores"

pytestmark = pytest.mark.django_db
User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.mark.parametrize("field_name", ["store_name"])
def test_required_fields_store_api(api_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize(("fields, values"), [(("store_name", "city", "zip_code"), ("Monoprix", "Lyon", "69001"))])
def test_unique_together_store_api(api_client, base_url, fields, values):
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (unique_together) en API """
    valid_data = dict(zip(fields, values))  # Associe dynamiquement chaque champ à une valeur
    validate_unique_together_api(api_client, base_url, model_name, valid_data, error_message="Ce magasin existe déjà.")

@pytest.mark.parametrize("field_name", ["store_name", "city"])
def test_min_length_fields_store_api(api_client, base_url, field_name):
    """ Vérifie que la longueur minimale des champs est respectée en API """
    valid_data = {"store_name": "Monoprix", "city": "Lyon"}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer le champ en cours de test des valeurs valides
    min_length = 2
    error_message = f"doit contenir au moins {min_length} caractères."
    validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

@pytest.mark.parametrize("field_name, raw_value", [
    ("store_name", "  MONOPRIX  "),
    ("city", "  LYON  "),
])
def test_normalized_fields_store_api(api_client, base_url, field_name, raw_value):
    """ Vérifie que l’API renvoie bien une valeur normalisée. """
    valid_data = {"store_name": "Monoprix ", "city": "Lyon", "zip_code": "69001"}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer dynamiquement le champ en cours de test
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.parametrize("fields", [("store_name", "city", "zip_code")])
def test_update_store_to_duplicate_api(api_client, base_url, fields, user):
    """ Vérifie qu'on ne peut PAS modifier un Store pour lui donner un store (défini par ses champs unique_together) déjà existant """
    api_client.force_authenticate(user=user)
    # Définir des valeurs initiales pour chaque champ unique
    values1 = ["Monoprix", "Lyon", "69001"]
    values2 = ["Carrefour", "Lyon", "69002"]
    # Construire dynamiquement `valid_data1` et `valid_data2`
    valid_data1 = dict(zip(fields, values1))
    valid_data2 = dict(zip(fields, values2))
    validate_update_to_duplicate_api(api_client, base_url, model_name, valid_data1, valid_data2, create_initiate=False, user=user)

@pytest.mark.parametrize("related_models", [
    [
        ("stores", StoreSerializer, {}, {"store_name": "Auchan", "city": "Paris", "zip_code": None, "visibility": "public"}),
        ("ingredients", IngredientSerializer, {}, {"ingredient_name": "blabla"}),
        ("ingredient_prices", IngredientPriceSerializer, {"store": "stores", "ingredient": "ingredients"}, {"price": 2.5, "date": "2024-02-20", "quantity": 1, "unit": "kg", "brand_name": None}),
    ]
])
def test_delete_store_used_in_prices(api_client, base_url, related_models, user):
    """ Vérifie qu'un Store utilisé dans des prix d'ingrédients ne peut pas être supprimé. """
    api_client.force_authenticate(user=user)
    expected_error = "Ce magasin est associé à des prix d'ingrédients et ne peut pas être supprimé."
    validate_protected_delete_api(api_client, base_url, model_name, related_models, expected_error, user=user)

def test_store_requires_city_or_zip_code_api(api_client, base_url):
    """ Vérifie qu'un store ne peut pas être créé sans au moins une `city` ou `zip_code` en API. """
    url = base_url(model_name)
    store_data = {"store_name": "Auchan", "city": None, "zip_code": None}  # Manque city et zip_code

    response = api_client.post(url, store_data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Doit échouer
    assert "Si un magasin est renseigné, vous devez indiquer une ville ou un code postal." in response.json().get("non_field_errors", [])

@pytest.mark.parametrize("field_name, mode", [
    ("city", "empty"),
    ("zip_code", "empty"),
    ("city", "none"),
    ("zip_code", "none"),
])
def test_optional_fields_can_be_empty_or_none(api_client, base_url, field_name, mode):
    """ Vérifie que `city` et `zip_code` peuvent être `""` ou `None`, selon le mode. """
    valid_data = {"store_name": "Auchan", "city": "Marseille", "zip_code": "13001"}  # Données valides
    validate_optional_field_value_api(api_client, base_url, model_name, field_name, mode, **valid_data)