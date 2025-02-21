import pytest, json
from pastry_app.models import Store
from rest_framework import status
from django.core.exceptions import ValidationError
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Store
model_name = "stores"

@pytest.mark.parametrize("field_name", ["store_name"])
@pytest.mark.django_db
def test_required_fields_store_api(api_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    validate_required_field_api(api_client, base_url, model_name, field_name)

# @pytest.mark.parametrize("field_name", ["store_name"])
# @pytest.mark.django_db
# def test_unique_constraint_store_api(api_client, base_url, field_name):
#     """ Vérifie que les contraintes `unique=True` sont bien respectées via l’API. """
#     valid_data = {"store_name": "Monoprix", "city": "Lyon", "zip_code": "69001"}
#     validate_unique_constraint_api(api_client, base_url, model_name, field_name, **valid_data)

@pytest.mark.parametrize("fields, values", [(("store_name", "city", "zip_code"), ("Monoprix", "Lyon", "69001"))])
@pytest.mark.django_db
def test_unique_together_store_api(api_client, base_url, fields, values):
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (unique_together) en API """
    valid_data = dict(zip(fields, values))  # Associe dynamiquement chaque champ à une valeur
    validate_unique_together_api(api_client, base_url, model_name, valid_data)

@pytest.mark.parametrize("field_name", ["store_name", "city"])
@pytest.mark.django_db
def test_min_length_fields_store_api(api_client, base_url, field_name):
    """ Vérifie que la longueur minimale des champs est respectée en API """
    valid_data = {"store_name": "Monoprix", "city": "Lyon"}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer le champ en cours de test des valeurs valides
    validate_min_length_api(api_client, base_url, model_name, field_name, 2, **valid_data)

@pytest.mark.parametrize("field_name, raw_value", [
    ("store_name", "  MONOPRIX  "),
    ("city", "  LYON  "),
])
@pytest.mark.django_db
def test_normalized_fields_store_api(api_client, base_url, field_name, raw_value):
    """ Vérifie que l’API renvoie bien une valeur normalisée. """
    valid_data = {"store_name": "Monoprix", "city": "Lyon", "zip_code": "69001"}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer dynamiquement le champ en cours de test
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.parametrize("fields", [("store_name", "city", "zip_code")])
@pytest.mark.django_db
def test_update_store_to_duplicate_api(api_client, base_url, fields):
    """ Vérifie qu'on ne peut PAS modifier un Store pour lui donner un store (défini par ses champs unique_together) déjà existant """
    # Définir des valeurs initiales pour chaque champ unique
    values1 = ["Monoprix", "Lyon", "69001"]
    values2 = ["Carrefour", "Lyon", "69002"]
    # Construire dynamiquement `valid_data1` et `valid_data2`
    valid_data1 = dict(zip(fields, values1))
    valid_data2 = dict(zip(fields, values2))

    validate_update_to_duplicate_api(api_client, base_url, model_name, valid_data1, valid_data2)

@pytest.mark.django_db
def test_store_requires_city_or_zip_code_api(api_client, base_url):
    """ Vérifie qu'un store ne peut pas être créé sans au moins une `city` ou `zip_code` en API. """
    url = base_url(model_name)
    store_data = {"store_name": "Auchan"}  # Manque city et zip_code

    response = api_client.post(url, store_data, format="json")
    print("Réponse API :", response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Doit échouer
    assert "Si un magasin est renseigné, vous devez indiquer une ville ou un code postal." in response.json().get("non_field_errors", [])

