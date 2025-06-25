import pytest, json
from rest_framework import status
from pastry_app.models import Category, Ingredient, Recipe, IngredientCategory, RecipeCategory
from pastry_app.tests.base_api_test import api_client, base_url, update_object
from pastry_app.tests.utils import normalize_case
from django.contrib.auth.models import User
 
# Définir model_name pour les tests de Category
model_name = "categories"

pytestmark = pytest.mark.django_db

@pytest.fixture
def admin_client(api_client, db):
    """Crée un utilisateur admin et authentifie les requêtes API avec lui."""
    admin_user = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
    api_client.force_authenticate(user=admin_user)  # Authentifie le client API avec l'admin
    return api_client

@pytest.fixture
def setup_category(db):
    """Crée une catégorie par défaut pour les tests."""
    return Category.objects.create(category_name="Desserts", category_type="recipe")

def test_create_category(admin_client, base_url, setup_category):
    """Test de création d’une catégorie avec un `parent_category` valide"""
    url = base_url(model_name)
    data = {"category_name": "Pâtisseries", "category_type": "recipe", "parent_category": setup_category.category_name}
    response = admin_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert Category.objects.filter(category_name=normalize_case("Pâtisseries")).exists()
    assert response.json()["parent_category"] == setup_category.category_name  # Vérifie bien le slug

def test_get_category(api_client, base_url, setup_category):
    """Test de récupération d’une catégorie"""
    url = base_url(model_name) + f"{setup_category.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("category_name") == normalize_case(setup_category.category_name)

def test_list_categories(api_client, base_url, setup_category):
    """Test que l'API retourne bien la liste des catégories."""
    url = base_url(model_name)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0  # Vérifie que l'API retourne au moins une catégorie

def test_update_category_parent(admin_client, base_url, setup_category):
    """Test de mise à jour d’une catégorie en changeant son `parent_category`"""
    # Création d'une nouvelle catégorie pour servir de parent
    new_parent = Category.objects.create(category_name="Viennoiseries", category_type="recipe")

    url = base_url(model_name)
    category_id = setup_category.id

    # Mise à jour de `parent_category` avec le nom de la nouvelle catégorie
    data = {"parent_category": new_parent.category_name}
    response = update_object(admin_client, url, category_id, data=json.dumps(data))
    assert response.status_code == status.HTTP_200_OK  # Vérifie que la mise à jour fonctionne

    # Vérifie en base que la modification a bien été enregistrée
    setup_category.refresh_from_db()
    assert setup_category.parent_category == new_parent  # Vérifie que le parent a bien changé

def test_partial_update_category(admin_client, base_url, setup_category):
    """Test la mise à jour partielle d'une catégorie via PATCH."""
    url = base_url(model_name) + f"{setup_category.id}/"
    new_category = Category.objects.create(category_name="Tartes", category_type="recipe")
    response = admin_client.patch(url, data=json.dumps({"parent_category": new_category.category_name}), content_type="application/json")
    assert response.status_code == status.HTTP_200_OK
    setup_category.refresh_from_db()
    assert setup_category.parent_category == new_category  # Vérifie que c'est bien l'objet
    assert setup_category.parent_category.category_name == normalize_case("Tartes")  # Vérifie que c'est bien le bon nom

def test_delete_category(setup_category, admin_client, base_url):
    """Test de suppression d’une catégorie"""
    category_id = setup_category.id
    url = base_url(model_name)+f"{category_id}/"
    response = admin_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Category.objects.filter(id=category_id).exists()

def test_get_nonexistent_category(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une Category qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_nonexistent_category(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une Category qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.parametrize("parent_category_value, expected_status", [
    (None, status.HTTP_201_CREATED),  # `None` doit être accepté
    ("Desserts", status.HTTP_201_CREATED),  # Un `parent_category` valide doit être accepté
    ("Inexistant", status.HTTP_400_BAD_REQUEST)  # Un slug qui n'existe pas doit être rejeté
])
def test_parent_category_validation(admin_client, base_url, parent_category_value, expected_status, setup_category):
    """Vérifie que `parent_category` doit être soit `None`, soit un slug valide existant."""
    url = base_url(model_name)
    data = {"category_name": "Boulangerie", "category_type": "recipe", "parent_category": parent_category_value}
    response = admin_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == expected_status
    if expected_status == status.HTTP_400_BAD_REQUEST:
        assert "parent_category" in response.json()

def test_delete_category_with_linked_objects(admin_client, base_url, setup_category):
    """Vérifie qu'on ne peut pas supprimer une Category utilisée par un Ingredient OU une Recipe"""

    # Créer et ajouter un ingrédient qui utilise cette catégorie
    ingredient = Ingredient.objects.create(ingredient_name="Beurre")
    IngredientCategory.objects.create(ingredient=ingredient, category=setup_category)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # Créer et ajouter une recette qui utilise cette catégorie
    recipe = Recipe.objects.create(recipe_name="Tarte aux pommes", chef_name="Martin")
    RecipeCategory.objects.create(recipe=recipe, category=setup_category)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)

    url = base_url(model_name) + f"{setup_category.id}/"
    response = admin_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Cette catégorie est utilisée" in response.json()["error"]
    assert Category.objects.filter(id=setup_category.id).exists()  # Vérifie que la catégorie est toujours en base

def test_non_admin_cannot_delete_category(api_client, base_url, setup_category):
    """ Vérifie qu'un utilisateur non admin ne peut pas supprimer une Category. """
    url = base_url(model_name) + f"{setup_category.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN 
