import pytest, json
from rest_framework import status
from pastry_app.models import Label, Ingredient, Recipe, IngredientLabel, RecipeLabel
from pastry_app.tests.base_api_test import api_client, base_url, update_object
from pastry_app.tests.utils import normalize_case
from django.contrib.auth.models import User

# Définir model_name pour les tests de Label
model_name = "labels"

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)  # Authentifie le client API avec l'admin
    return api_client

@pytest.fixture
def setup_label(db):
    """Crée un label par défaut pour les tests."""
    return Label.objects.create(label_name="Bio", label_type="recipe")

@pytest.mark.django_db
def test_create_label(admin_client, base_url, setup_label):
    """Test de création d’un label."""
    url = base_url(model_name)
    data = {"label_name": "Label Rouge", "label_type": "recipe"}
    response = admin_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert Label.objects.filter(label_name=normalize_case("Label Rouge")).exists()

@pytest.mark.django_db
def test_get_label(api_client, base_url, setup_label):
    """Test de récupération d’un label"""
    url = base_url(model_name) + f"{setup_label.id}/"
    response = api_client.get(url)
    print(response.json())
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("label_name") == normalize_case(setup_label.label_name)

@pytest.mark.django_db
def test_list_categories(api_client, base_url, setup_label):
    """Test que l'API retourne bien la liste des labels."""
    url = base_url(model_name)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0  # Vérifie que l'API retourne au moins un label

@pytest.mark.django_db
def test_delete_label(setup_label, admin_client, base_url):
    """Test de suppression d’un label"""
    label_id = setup_label.id
    url = base_url(model_name)+f"{label_id}/"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Label.objects.filter(id=label_id).exists()

@pytest.mark.django_db
def test_get_nonexistent_label(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un Label qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_nonexistent_label(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un Label qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_label_with_linked_objects(admin_client, base_url, setup_label):
    """Vérifie qu'on ne peut pas supprimer un Label utilisé par un Ingredient OU une Recipe"""

    # Créer et ajouter un ingrédient qui utilise ce label
    ingredient = Ingredient.objects.create(ingredient_name="Beurre")
    IngredientLabel.objects.create(ingredient=ingredient, label=setup_label)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # Créer et ajouter une recette qui utilise cet label
    recipe = Recipe.objects.create(recipe_name="Tarte aux pommes")
    RecipeLabel.objects.create(recipe=recipe, label=setup_label)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)

    url = base_url(model_name) + f"{setup_label.id}/"
    response = admin_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Ce label est utilisé" in response.json()["error"]
    assert Label.objects.filter(id=setup_label.id).exists()  # Vérifie que le label est toujours en base

@pytest.mark.django_db
def test_non_admin_cannot_delete_label(api_client, base_url, setup_label):
    """ Vérifie qu'un utilisateur non admin ne peut pas supprimer un Label. """
    url = base_url(model_name) + f"{setup_label.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN 