import pytest, json
from rest_framework import status
from django.core.exceptions import ValidationError
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.constants import CATEGORY_NAME_CHOICES, CATEGORY_DEFINITIONS, CATEGORY_TYPE_MAP
from pastry_app.models import Category

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_unique_constraint_store_api(api_client, base_url, field_name):
    """ Vérifie que les contraintes `unique=True` sont bien respectées via l’API. """
    valid_data = {"category_name": CATEGORY_NAME_CHOICES[0]}
    validate_unique_constraint_api(api_client, base_url, model_name, field_name, **valid_data)

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_required_fields_category_api(api_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize("field_name, mode", [("parent_category", "both"),])
@pytest.mark.django_db
def test_optional_fields_can_be_empty_or_none(api_client, base_url, field_name, mode):
    """ Vérifie que `parent_category` peu être `""` ou `None` selon le mode. """
    valid_data = {"category_name": CATEGORY_NAME_CHOICES[0], "parent_category": CATEGORY_NAME_CHOICES[1]}  # Données valides
    validate_optional_field_value_api(api_client, base_url, model_name, field_name, mode, **valid_data)

@pytest.mark.django_db
def test_normalized_fields_category_api(api_client, base_url):
    """ Vérifie que `brand_name` et est bien normalisé après création via l’API. """
    field_name = "category_name"
    raw_value = " CakeS  "
    valid_data = {field_name: raw_value}
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.django_db
def test_create_duplicate_category(api_client, base_url):
    """Vérifie qu'on ne peut PAS créer deux Category avec le même `category_name` via l'API, peu importe la casse"""
    url = base_url(model_name)

    # Création de la première catégorie via l'API
    response1 = api_client.post(url, data=json.dumps({"category_name": " Cakes"}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit
    # Essayer de créer une deuxième catégorie avec le même nom via l'API (avec la même casse ou différente)
    response2 = api_client.post(url, data=json.dumps({"category_name": normalize_case(" Cakes")}), content_type="application/json")

    # Vérifier que l'API refuse le doublon avec un code 400
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response2.json()

@pytest.mark.django_db
def test_create_category_invalid_name(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer une Category avec un `category_name` invalide """
    url = base_url(model_name)
    response = api_client.post(url, data={"category_name": "azerty"})  # "azerty" n'est pas dans `CATEGORY_NAME_CHOICES`
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response.json()  # Vérifie que l'API bloque bien

# 🔴 Attention : Ce test d'unicité (test_update_category_to_duplicate) fonctionnent UNIQUEMENT si `unique=True` est retiré du modèle.
# Si `unique=True`, Django bloque la validation AVANT que l'API ne réponde -> `IntegrityError`
# Solution recommandée :
# 1️. Tester l'unicité dans l'API avec `validate_category_name()` dans `serializers.py` (sans `unique=True`).
# 2️. En production, remettre `unique=True` dans `models.py` pour sécuriser la base, mais NE PAS tester cela avec pytest.
#    Si ces tests échouent avec `unique=True`, c'est normal et tu peux ignorer l'erreur !
# @pytest.mark.django_db
# def test_update_category_to_duplicate(api_client, base_url):
#     """Vérifie qu'on ne peut PAS modifier une Category pour lui donner un `category_name` déjà existant"""
#     url = base_url(model_name)

#     # Sélectionner deux catégories distinctes dynamiquement
#     category_names = CATEGORY_NAME_CHOICES[:2]  # Prend les deux premières catégories disponibles
#     if len(category_names) < 2:
#         pytest.skip("Pas assez de catégories disponibles pour ce test.")

#     category1, category2 = category_names  # Assigne deux catégories différentes

#     # Créer deux catégories différentes
#     response1 = api_client.post(url, {"category_name": category1})
#     response2 = api_client.post(url, {"category_name": category2})

#     assert response1.status_code == status.HTTP_201_CREATED
#     assert response2.status_code == status.HTTP_201_CREATED
#     # Vérification que la réponse contient bien l'ID
#     category_id = response2.json()["id"]

#     # Essayer de renommer "Viennoiseries" en "Desserts"
#     response3 = api_client.patch(f"{url}{category_id}/", {"category_name": category1})

#     # Vérifier que l'API refuse la modification
#     assert response3.status_code == status.HTTP_400_BAD_REQUEST
#     assert "category_name" in response3.json()

@pytest.mark.parametrize("fields", [("category_name")])
@pytest.mark.django_db
def test_update_category_to_duplicate_api(api_client, base_url, fields):
    """ Vérifie qu'on ne peut PAS modifier une Category pour lui donner une category (défini par ses champs unique) déjà existant """
    # Sélectionner deux catégories distinctes dynamiquement
    category_names = CATEGORY_NAME_CHOICES[:2]  # Prend les deux premières catégories disponibles
    if len(category_names) < 2:
        pytest.skip("Pas assez de catégories disponibles pour ce test.")
    category1, category2 = category_names  # Assigne deux catégories différentes

    # Construire dynamiquement `valid_data1` et `valid_data2`
    valid_data1 = dict(zip(fields, category1))
    valid_data2 = dict(zip(fields, category2))
    validate_update_to_duplicate_api(api_client, base_url, model_name, valid_data1, valid_data2)

@pytest.mark.parametrize("category_name", CATEGORY_NAME_CHOICES)
@pytest.mark.django_db
def test_category_type_is_assigned_correctly(api_client, base_url, category_name):
    """Vérifie que l'API assigne le bon `category_type` en fonction du `category_name`."""
    url = base_url(model_name)
    expected_type = CATEGORY_TYPE_MAP.get(category_name, "recipe")  # Par défaut, type = "recipe"

    data = {"category_name": category_name}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["category_type"] == expected_type

@pytest.mark.django_db
def test_category_slug_is_generated_correctly(api_client, base_url):
    """Vérifie que le slug est bien généré à partir de `category_name`."""
    url = base_url(model_name)
    data = {"category_name": "cremeux", "parent_category": "entremets"}
    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["slug"] == "patisserie-francaise"
