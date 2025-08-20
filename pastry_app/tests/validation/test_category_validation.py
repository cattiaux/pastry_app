import pytest, json
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import Category
from django.contrib.auth.models import User

# Définir model_name pour les tests de Category
model_name = "categories"
pytestmark = pytest.mark.django_db

@pytest.fixture
def user():
    admin =User.objects.create_user(username="user1", password="testpass123")
    admin.is_staff = True  # Assure que l'utilisateur est un admin
    admin.save()
    return admin 

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)  # Authentifie le client API avec l'admin
    return api_client

@pytest.fixture
def category(user, db):
    """Crée une instance de Category pour les tests."""
    return Category.objects.create(category_name="Desserts", category_type="recipe", created_by=user)

@pytest.mark.parametrize("field_name", ["category_name"])
def test_unique_constraint_category_api(admin_client, base_url, field_name, category):
    """ Vérifie que les contraintes `unique=True` sont bien respectées via l’API. """
    valid_data = {"category_name": category.category_name, "category_type": category.category_type} 
    response = validate_unique_constraint_api(admin_client, base_url, model_name, field_name, **valid_data)
    assert field_name in response.json()

@pytest.mark.parametrize("field_name", ["category_name", "category_type"])
def test_required_fields_category_api(admin_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", "This field may not be blank.", "\"\" is not a valid choice."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(admin_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["parent_category"])
def test_optional_fields_api(admin_client, base_url, field_name, user):
    """ Vérifie que `parent_category` peut être `None`"""
    url = base_url(model_name)
    valid_data = {"category_name": "azerty", "category_type": "recipe"}  # Données valides
    valid_data[field_name] = None
    response = admin_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED  # Doit réussir
    assert response.json()[field_name] == None  # Vérification

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
def test_create_category_invalid_type(admin_client, base_url, invalid_category_type):
    """ Vérifie qu'on ne peut PAS créer une Category avec un `category_type` invalide """
    url = base_url(model_name)
    response = admin_client.post(url, data={"category_name": "Viennoiseries", "category_type": invalid_category_type})
    print(response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_type" in response.json()  # Vérifie que l'API bloque bien

def test_update_category_to_duplicate_api(admin_client, base_url, category):
    """ Vérifie qu'on ne peut PAS modifier une Category pour lui donner un `category_name` déjà existant via l'API. """
    valid_data1 = {"category_name": category.category_name, "category_type": category.category_type}
    valid_data2 = {"category_name": "Viennoiseries", "category_type": "recipe"}
    validate_update_to_duplicate_api(admin_client, base_url, model_name, valid_data1, valid_data2)

def test_create_category_with_invalid_parent(admin_client, base_url):
    """ Vérifie qu'on ne peut PAS créer une Category avec un `parent_category` qui n'existe pas. """
    url = base_url(model_name)
    response = admin_client.post(url, data={"category_name": "Ganaches", "category_type": "recipe", "parent_category": "Inexistant"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "parent_category" in response.json()  # Vérifie que l'API bloque bien

def test_non_admin_cannot_create_category(api_client, base_url):
    """ Vérifie qu'un utilisateur non admin ne peut pas créer une Category. """
    url = base_url(model_name)
    response = api_client.post(url, data={"category_name": "Test", "category_type": "recipe"}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.parametrize("delete_subcategories, expected_count", [("true", 0), ("false", 1)])
def test_delete_category_with_subcategories(admin_client, base_url, delete_subcategories, expected_count, user):
    """Vérifie que la suppression d'une catégorie détache ou supprime ses sous-catégories selon l'option."""
    parent = Category.objects.create(category_name="Parent", category_type="recipe", created_by=user)
    child = Category.objects.create(category_name="Child", category_type="recipe", parent_category=parent, created_by=user)

    url = base_url("categories") + f"{parent.id}/?delete_subcategories={delete_subcategories}"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert Category.objects.filter(id=parent.id).count() == 0  # Parent supprimé
    assert Category.objects.filter(id=child.id).count() == expected_count  # Détaché ou supprimé selon le paramètre

@pytest.mark.parametrize(
    "parent_type,child_type,should_pass",
    [
        ("ingredient", "ingredient", True),
        ("ingredient", "recipe", False),
        ("ingredient", "both", False),
        ("recipe", "recipe", True),
        ("recipe", "ingredient", False),
        ("recipe", "both", False),
        ("both", "ingredient", True),
        ("both", "recipe", True),
        ("both", "both", True),
    ]
)
def test_category_parent_type_api(admin_client, base_url, parent_type, child_type, should_pass, user):
    url = base_url(model_name)
    parent = Category.objects.create(category_name=f"Parent {parent_type}", category_type=parent_type, created_by=user)
    payload = {"category_name": f"Child {child_type}", "category_type": child_type, "parent_category": parent.category_name}
    resp = admin_client.post(url, payload, format="json")
    if should_pass:
        assert resp.status_code in [200, 201], f"API should allow {child_type} parent {parent_type}, got {resp.status_code} - {resp.json()}"
    else:
        assert resp.status_code == 400, f"API should reject {child_type} parent {parent_type}, got {resp.status_code} - {resp.json()}"