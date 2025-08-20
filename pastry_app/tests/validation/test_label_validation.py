import pytest, json
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import Label
from django.contrib.auth.models import User

# Définir model_name pour les tests de Label
model_name = "labels"
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
def label(user, db):
    """Crée une instance de Label pour les tests."""
    return Label.objects.create(label_name="Bio", label_type="recipe", created_by=user)

@pytest.mark.parametrize("field_name", ["label_name"])
def test_unique_constraint_label_api(admin_client, base_url, field_name, label):
    """ Vérifie que les contraintes `unique=True` sont bien respectées via l’API. """
    valid_data = {"label_name": label.label_name, "label_type": label.label_type} 
    response = validate_unique_constraint_api(admin_client, base_url, model_name, field_name, **valid_data)
    assert field_name in response.json()

@pytest.mark.parametrize("field_name", ["label_name", "label_type"])
def test_required_fields_label_api(admin_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", "This field may not be blank.", "\"\" is not a valid choice."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(admin_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize("field_name, raw_value", [
    ("label_name", " Label Rouge  "),
    ("label_type", "RECIPE"),
])
def test_normalized_fields_label_api(admin_client, base_url, field_name, raw_value):
    """ Vérifie que `label_name` et `label_type` sont bien normalisés après création via l’API. """
    url = base_url(model_name)
    valid_data = {"label_name": "Test Label", "label_type": "recipe"}  # Valeurs par défaut
    valid_data[field_name] = raw_value  # On remplace la valeur du champ testé
    response = admin_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[field_name] == normalize_case(raw_value)  # Vérifie la normalisation

def test_create_duplicate_label_api(admin_client, base_url):
    """Vérifie qu'on ne peut PAS créer deux Label avec le même `label_name` via l'API, peu importe la casse"""
    url = base_url(model_name)

    # Création de la première catégorie via l'API
    response1 = admin_client.post(url, data=json.dumps({"label_name": " Label Rouge", "label_type": "recipe"}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit
    # Essayer de créer une deuxième catégorie avec le même nom via l'API (avec la même casse ou différente)
    response2 = admin_client.post(url, data=json.dumps({"label_name": normalize_case(" Label Rouge"), "label_type": "recipe"}), content_type="application/json")

    # Vérifier que l'API refuse le doublon avec un code 400
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_name" in response2.json()

@pytest.mark.parametrize("invalid_label_type", ["invalid", "123"])
def test_create_label_invalid_type(admin_client, base_url, invalid_label_type):
    """ Vérifie qu'on ne peut PAS créer une Label avec un `label_type` invalide """
    url = base_url(model_name)
    response = admin_client.post(url, data={"label_name": "Vegan", "label_type": invalid_label_type})
    print(response.json())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_type" in response.json()  # Vérifie que l'API bloque bien


# 🔴 Attention : Ce test d'unicité (test_update_label_to_duplicate_api) fonctionnent UNIQUEMENT si `unique=True` est retiré du modèle.
# Si `unique=True`, Django bloque la validation AVANT que l'API ne réponde -> `IntegrityError`
# Solution recommandée :
# 1️. Tester l'unicité dans l'API avec `validate_label_name()` dans `serializers.py` (sans `unique=True`).
# 2️. En production, remettre `unique=True` dans `models.py` pour sécuriser la base, mais NE PAS tester cela avec pytest.
#    Si ces tests échouent avec `unique=True`, c'est normal et tu peux ignorer l'erreur !
def test_update_label_to_duplicate_api(admin_client, base_url, label):
    """ Vérifie qu'on ne peut PAS modifier une Label pour lui donner un `label_name` déjà existant via l'API. """
    valid_data1 = {"label_name": label.label_name, "label_type": label.label_type}
    valid_data2 = {"label_name": "Vegan", "label_type": "recipe"}
    validate_update_to_duplicate_api(admin_client, base_url, model_name, valid_data1, valid_data2)

def test_non_admin_cannot_create_label(api_client, base_url):
    """ Vérifie qu'un utilisateur non admin ne peut pas créer une Label. """
    url = base_url(model_name)
    response = api_client.post(url, data={"label_name": "Test", "label_type": "recipe"}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN