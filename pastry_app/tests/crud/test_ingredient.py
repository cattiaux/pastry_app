import pytest, json
from django.contrib.auth import get_user_model
from rest_framework import status
from pastry_app.models import Ingredient, Category, Label, Recipe, RecipeIngredient
from pastry_app.tests.utils import normalize_case
from pastry_app.tests.base_api_test import api_client, base_url

"""Test CRUD sur le modèle Ingredient"""

# Création	
# - test_create_ingredient
# - test_create_ingredient_with_category
# - test_create_ingredient_with_label

# Lecture
# - test_get_ingredient
# - test_get_nonexistent_ingredient

# Mise à jour
# - test_update_ingredient_name
# - test_update_ingredient_add_category
# - test_update_ingredient_remove_category
# - test_update_ingredient_add_label
# - test_update_ingredient_remove_label

# Suppression
# - test_delete_ingredient
# - test_delete_ingredient_used_in_recipe
# - test_delete_nonexistent_ingredient

# Définir model_name pour les tests de Category
model_name = "ingredients"

pytestmark = pytest.mark.django_db
User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def setup_ingredient(db, user):
    """Création d’un ingrédient pour les tests"""
    return Ingredient.objects.create(ingredient_name="Chocolat", visibility="public", user=user)

@pytest.fixture
def category():
    """Crée une catégorie valide pour les tests."""
    return Category.objects.create(category_name="Fruits", category_type="ingredient")

@pytest.fixture
def label():
    """Crée un label valide pour les tests."""
    return Label.objects.create(label_name="Bio", label_type="recipe")

@pytest.fixture
def recipe():
    """Crée une recette pour les tests."""
    return Recipe.objects.create(recipe_name="Tarte aux pommes", chef_name="Martin")

def test_create_ingredient(api_client, base_url):
    """Test de création d’un ingrédient"""
    url = base_url(model_name)
    ingredient_name = "Noisette"
    data = {"ingredient_name": ingredient_name}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Ingredient.objects.filter(ingredient_name=normalize_case(ingredient_name)).exists()

def test_get_ingredient(api_client, base_url, setup_ingredient):
    """Test de récupération d’un ingrédient existant"""
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["ingredient_name"] == normalize_case(setup_ingredient.ingredient_name)

def test_update_ingredient_name(api_client, base_url, setup_ingredient, user):
    """Test de mise à jour d’un ingrédient"""
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    ingredient_name="Cacao "
    data = {"ingredient_name": ingredient_name}
    api_client.force_authenticate(user=user)
    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_200_OK
    setup_ingredient.refresh_from_db()
    assert setup_ingredient.ingredient_name == normalize_case(ingredient_name)

def test_delete_ingredient(api_client, base_url, setup_ingredient, user):
    """Test de suppression d’un ingrédient"""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Ingredient.objects.filter(id=setup_ingredient.id).exists()

def test_create_ingredient_with_category(api_client, base_url, category):
    """Test de création d’un ingrédient avec une catégorie existante."""
    url = base_url(model_name)
    ingredient_name = "Noisette "
    data = {"ingredient_name": ingredient_name, "categories": [category.id]}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Ingredient.objects.filter(ingredient_name=normalize_case(ingredient_name), categories=category).exists()

def test_create_ingredient_with_label(api_client, base_url, label):
    """Test de création d’un ingrédient avec un label existant."""
    url = base_url(model_name)
    ingredient_name = "Noisette "
    data = {"ingredient_name": ingredient_name, "labels": [label.id]}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Ingredient.objects.filter(ingredient_name=normalize_case(ingredient_name), labels=label).exists()

def test_get_nonexistent_ingredient(api_client, base_url):
    """Test de récupération d’un ingrédient inexistant."""
    url = base_url(model_name) + "9999/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_update_ingredient_add_category(api_client, base_url, setup_ingredient, category, user):
    """Test d’ajout d’une catégorie à un ingrédient existant."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    data = {"categories": [category.id]}

    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_200_OK
    setup_ingredient.refresh_from_db()
    assert category in setup_ingredient.categories.all()

def test_update_ingredient_add_label(api_client, base_url, setup_ingredient, label, user):
    """Test d’ajout d’un label à un ingrédient existant."""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    data = {"labels": [label.id]}

    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_200_OK
    setup_ingredient.refresh_from_db()
    assert label in setup_ingredient.labels.all()

def test_update_ingredient_remove_category(api_client, base_url, setup_ingredient, category, user):
    """Test de suppression d’une catégorie associée à un ingrédient."""
    api_client.force_authenticate(user=user)
    setup_ingredient.categories.add(category)  # Ajouter la catégorie initialement
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    data = {"categories": []}  # On vide la liste

    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_200_OK
    setup_ingredient.refresh_from_db()
    assert category not in setup_ingredient.categories.all()

def test_update_ingredient_remove_label(api_client, base_url, setup_ingredient, label, user):
    """Test de suppression d’une catégorie associée à un ingrédient."""
    api_client.force_authenticate(user=user)
    setup_ingredient.labels.add(label)  # Ajouter le label initialement
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    data = {"labels": []}  # On vide la liste

    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_200_OK
    setup_ingredient.refresh_from_db()
    assert label not in setup_ingredient.labels.all()

def test_delete_ingredient_used_in_recipe(api_client, base_url, setup_ingredient, recipe, user):
    """Vérifie qu’on ne peut PAS supprimer un ingrédient utilisé dans une recette."""
    api_client.force_authenticate(user=user)
    RecipeIngredient.objects.create(recipe=recipe, ingredient=setup_ingredient, quantity=100, unit="g")
    url = base_url(model_name) + f"{setup_ingredient.id}/"
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ne peut pas être supprimé" in response.json()["error"]

def test_delete_nonexistent_ingredient(api_client, base_url):
    """Vérifie qu’on obtient une erreur 404 quand on essaie de supprimer un ingrédient qui n’existe pas."""
    url = base_url(model_name) + "9999/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND