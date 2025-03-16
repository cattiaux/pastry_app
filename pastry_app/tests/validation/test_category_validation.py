import pytest, json
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import Category
from django.contrib.auth.models import User

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)  # Authentifie le client API avec l'admin
    return api_client

@pytest.fixture
def category(db):
    """Crée une instance de Category pour les tests."""
    return Category.objects.create(category_name="Desserts", category_type="recipe")

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_unique_constraint_category_api(admin_client, base_url, field_name, category):
    """ Vérifie que les contraintes `unique=True` sont bien respectées via l’API. """
    valid_data = {"category_name": category.category_name, "category_type": category.category_type} 
    response = validate_unique_constraint_api(admin_client, base_url, model_name, field_name, **valid_data)
    assert field_name in response.json()

@pytest.mark.parametrize("field_name", ["category_name", "category_type"])
@pytest.mark.django_db
def test_required_fields_category_api(admin_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", "This field may not be blank.", "\"\" is not a valid choice."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(admin_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["parent_category"])
@pytest.mark.django_db
def test_optional_fields_api(admin_client, base_url, field_name):
    """ Vérifie que `parent_category` peut être `None`"""
    url = base_url(model_name)
    valid_data = {"category_name": "azerty", "category_type": "recipe"}  # Données valides
    valid_data[field_name] = None
    response = admin_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED  # Doit réussir
    assert response.json()[field_name] == None  # Vérification

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, raw_value", [
    ("category_name", " CakeS  "),
    ("category_type", "RECIPE"),
])
def test_normalized_fields_category_api(admin_client, base_url, field_name, raw_value):
    """ Vérifie que `category_name` et `category_type` sont bien normalisés après création via l’API. """
    url = base_url(model_name)
    valid_data = {"category_name": "Test Category", "category_type": "recipe"}  # Valeurs par défaut
    valid_data[field_name] = raw_value  # On remplace la valeur du champ testé

    response = admin_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[field_name] == normalize_case(raw_value)  # Vérifie la normalisation

@pytest.mark.django_db
def test_create_duplicate_category_api(admin_client, base_url):
    """Vérifie qu'on ne peut PAS créer deux Category avec le même `category_name` via l'API, peu importe la casse"""
    url = base_url(model_name)

    # Création de la première catégorie via l'API
    response1 = admin_client.post(url, data=json.dumps({"category_name": " Cakes", "category_type": "recipe"}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit
    # Essayer de créer une deuxième catégorie avec le même nom via l'API (avec la même casse ou différente)
    response2 = admin_client.post(url, data=json.dumps({"category_name": normalize_case(" Cakes"), "category_type": "recipe"}), content_type="application/json")

    # Vérifier que l'API refuse le doublon avec un code 400
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response2.json()

@pytest.mark.parametrize("invalid_category_type", ["invalid", "123"])
@pytest.mark.django_db
def test_create_category_invalid_type(admin_client, base_url, invalid_category_type):
    """ Vérifie qu'on ne peut PAS créer une Category avec un `category_type` invalide """
    url = base_url(model_name)
    response = admin_client.post(url, data={"category_name": "Viennoiseries", "category_type": invalid_category_type})
    print(response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_type" in response.json()  # Vérifie que l'API bloque bien


# 🔴 Attention : Ce test d'unicité (test_update_category_to_duplicate_api) fonctionnent UNIQUEMENT si `unique=True` est retiré du modèle.
# Si `unique=True`, Django bloque la validation AVANT que l'API ne réponde -> `IntegrityError`
# Solution recommandée :
# 1️. Tester l'unicité dans l'API avec `validate_category_name()` dans `serializers.py` (sans `unique=True`).
# 2️. En production, remettre `unique=True` dans `models.py` pour sécuriser la base, mais NE PAS tester cela avec pytest.
#    Si ces tests échouent avec `unique=True`, c'est normal et tu peux ignorer l'erreur !
@pytest.mark.django_db
def test_update_category_to_duplicate_api(admin_client, base_url, category):
    """ Vérifie qu'on ne peut PAS modifier une Category pour lui donner un `category_name` déjà existant via l'API. """
    valid_data1 = {"category_name": category.category_name, "category_type": category.category_type}
    valid_data2 = {"category_name": "Viennoiseries", "category_type": "recipe"}
    validate_update_to_duplicate_api(admin_client, base_url, model_name, valid_data1, valid_data2)

@pytest.mark.django_db
def test_create_category_with_invalid_parent(admin_client, base_url):
    """ Vérifie qu'on ne peut PAS créer une Category avec un `parent_category` qui n'existe pas. """
    url = base_url(model_name)
    response = admin_client.post(url, data={"category_name": "Ganaches", "category_type": "recipe", "parent_category": "Inexistant"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "parent_category" in response.json()  # Vérifie que l'API bloque bien

@pytest.mark.django_db
def test_non_admin_cannot_create_category(api_client, base_url):
    """ Vérifie qu'un utilisateur non admin ne peut pas créer une Category. """
    url = base_url(model_name)
    response = api_client.post(url, data={"category_name": "Test", "category_type": "recipe"}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
@pytest.mark.parametrize("delete_subcategories, expected_count", [("true", 0), ("false", 1)])
def test_delete_category_with_subcategories(admin_client, base_url, delete_subcategories, expected_count):
    """Vérifie que la suppression d'une catégorie détache ou supprime ses sous-catégories selon l'option."""
    parent = Category.objects.create(category_name="Parent", category_type="recipe")
    child = Category.objects.create(category_name="Child", category_type="recipe", parent_category=parent)

    url = base_url("categories") + f"{parent.id}/?delete_subcategories={delete_subcategories}"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert Category.objects.filter(id=parent.id).count() == 0  # Parent supprimé
    assert Category.objects.filter(id=child.id).count() == expected_count  # Détaché ou supprimé selon le paramètre