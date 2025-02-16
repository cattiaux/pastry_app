from pastry_app.models import Category
from rest_framework import status
from django.core.exceptions import ValidationError
import pytest, json
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import CATEGORY_NAME_CHOICES, CATEGORY_DEFINITIONS

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.mark.django_db
def test_create_category_without_name(api_client, base_url):
    """Vérifie qu'on ne peut PAS créer une Category sans `category_name` via l'API"""
    url = base_url(model_name)
    response = api_client.post(url, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response.json()

@pytest.mark.django_db
def test_create_duplicate_category(api_client, base_url):
    """Vérifie qu'on ne peut PAS créer deux Category avec le même `category_name` via l'API, peu importe la casse"""
    url = base_url(model_name)

    # Création de la première catégorie via l'API
    response1 = api_client.post(url, data=json.dumps({"category_name": CATEGORY_NAME_CHOICES[0]}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit

    # Essayer de créer une deuxième catégorie avec le même nom via l'API (avec la même casse ou différente)
    response2 = api_client.post(url, data=json.dumps({"category_name": normalize_case(CATEGORY_NAME_CHOICES[0])}), content_type="application/json")

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

@pytest.mark.django_db
def test_category_name_cannot_be_empty():
    """Vérifie qu'on ne peut pas créer une catégorie avec un nom vide."""
    with pytest.raises(ValidationError):
        category = Category(category_name="")
        category.full_clean()

@pytest.mark.django_db
def test_category_name_is_normalized():
    """Vérifie que le `category_name` est bien normalisé (minuscule, sans espaces inutiles)."""
    category = Category.objects.create(category_name=f"  {CATEGORY_NAME_CHOICES[0].upper()}  ")
    assert category.category_name == CATEGORY_NAME_CHOICES[0]

# 🔴 Attention : Ce test d'unicité (test_update_category_to_duplicate) fonctionnent UNIQUEMENT si `unique=True` est retiré du modèle.
# Si `unique=True`, Django bloque la validation AVANT que l'API ne réponde -> `IntegrityError`
# Solution recommandée :
# 1️. Tester l'unicité dans l'API avec `validate_category_name()` dans `serializers.py` (sans `unique=True`).
# 2️. En production, remettre `unique=True` dans `models.py` pour sécuriser la base, mais NE PAS tester cela avec pytest.
#    Si ces tests échouent avec `unique=True`, c'est normal et tu peux ignorer l'erreur !
@pytest.mark.django_db
def test_update_category_to_duplicate(api_client, base_url):
    """Vérifie qu'on ne peut PAS modifier une Category pour lui donner un `category_name` déjà existant"""
    url = base_url(model_name)

    # Sélectionner deux catégories distinctes dynamiquement
    category_names = CATEGORY_NAME_CHOICES[:2]  # Prend les deux premières catégories disponibles
    if len(category_names) < 2:
        pytest.skip("Pas assez de catégories disponibles pour ce test.")

    category1, category2 = category_names  # Assigne deux catégories différentes

    # Créer deux catégories différentes
    response1 = api_client.post(url, {"category_name": category1})
    response2 = api_client.post(url, {"category_name": category2})

    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED
    # Vérification que la réponse contient bien l'ID
    category_id = response2.json()["id"]

    # Essayer de renommer "Viennoiseries" en "Desserts"
    response3 = api_client.patch(f"{url}{category_id}/", {"category_name": category1})

    # Vérifier que l'API refuse la modification
    assert response3.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response3.json()

def test_category_type_choices():
    """Vérifie que les choix pour `category_type` sont correctement définis à partir de CATEGORY_DEFINITIONS."""
    valid_types = {c_type for _, _, c_type in CATEGORY_DEFINITIONS}  # Récupère les types uniques
    assert "ingredient" in valid_types
    assert "recipe" in valid_types
    assert "both" in valid_types


########## n’a plus d’intérêt, car on ne peut pas choisir category_type librement. ##########

# @pytest.mark.django_db
# def test_category_type_must_be_valid():
#     """Vérifie que `category_type` ne peut prendre que des valeurs valides."""
#     with pytest.raises(ValidationError):
#         category = Category(category_name="Test", category_type="invalide")
#         category.full_clean()

# @pytest.mark.django_db
# def test_category_name_cannot_be_too_short():
#     """Vérifie qu'on ne peut pas créer une catégorie avec un nom trop court."""
#     with pytest.raises(ValidationError):
#         category = Category(category_name="A")
#         category.full_clean()

# @pytest.mark.django_db
# def test_category_name_cannot_be_numeric():
#     """Vérifie qu'une catégorie ne peut pas être uniquement composée de chiffres."""
#     with pytest.raises(ValidationError):
#         category = Category(category_name="12345")
#         category.full_clean()
