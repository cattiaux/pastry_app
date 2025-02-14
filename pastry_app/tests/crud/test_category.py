from pastry_app.models import Category, Ingredient, Recipe, IngredientCategory, RecipeCategory
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url, update_object#, create_object, get_object, delete_object
import pytest, json
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import CATEGORY_NAME_CHOICES, CATEGORY_TYPE_MAP

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.fixture(params=CATEGORY_NAME_CHOICES)
def setup_category(request):
    """Création d’une catégorie avant chaque test (dynamique), parmi les choix disponibles de CATEGORY_NAME_CHOICES"""
    return Category.objects.create(category_name=request.param)

@pytest.mark.django_db
def test_create_category(setup_category, api_client, base_url):
    """Test de création d’une catégorie"""
    url = base_url(model_name)

    # Sélectionner une catégorie différente de `setup_category`
    category_name = next((name for name in CATEGORY_NAME_CHOICES if name != setup_category.category_name), None)
    if not category_name:
        pytest.skip("Pas assez de catégories disponibles pour le test.")

    data = {"category_name": category_name, "category_type": "both"}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert Category.objects.filter(category_name=normalize_case(category_name)).exists()

@pytest.mark.django_db
def test_category_type_assignment(api_client, base_url):
    """Vérifie que l'API assigne le bon `category_type` en fonction du `category_name`"""
    url = base_url(model_name)

    # Sélectionner une catégorie valide
    category_name, expected_type = next(iter(CATEGORY_TYPE_MAP.items()))  # Prend un élément valide

    data = {"category_name": category_name}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    # Vérifier que la création fonctionne bien et que `category_type` est bien assigné
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["category_type"] == expected_type

@pytest.mark.django_db
def test_get_category(setup_category, api_client, base_url):
    """Test de récupération d’une catégorie"""
    category_id = setup_category.id
    url = base_url(model_name)+f"{category_id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("category_name") == normalize_case(setup_category.category_name)

@pytest.mark.django_db
def test_update_category(setup_category, api_client, base_url):
    """Test de mise à jour d’une catégorie avec le bon `category_type`"""
    url = base_url(model_name)
    category_id = setup_category.id

    # Sélectionner une catégorie différente de `setup_category`
    category_name = next((name for name in CATEGORY_NAME_CHOICES if name != setup_category.category_name), None)
    if not category_name:
        pytest.skip("Pas assez de catégories disponibles pour le test.")

    category_type = CATEGORY_TYPE_MAP[category_name]  # Récupérer le bon type
    data = {"category_name": category_name, "category_type": category_type}
    response = update_object(api_client, url, category_id, data=json.dumps(data))
    assert response.status_code == status.HTTP_200_OK # Vérifier que la mise à jour fonctionne
    setup_category.refresh_from_db()
    assert setup_category.category_name == category_name
    assert setup_category.category_type == category_type  # Vérifier que `category_type` est correct

@pytest.mark.django_db
def test_delete_category(setup_category, api_client, base_url):
    """Test de suppression d’une catégorie"""
    category_id = setup_category.id
    url = base_url(model_name)+f"{category_id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Category.objects.filter(id=category_id).exists()

@pytest.mark.django_db
def test_get_nonexistent_category(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une Category qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_nonexistent_category(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une Category qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_category_with_linked_objects(setup_category, api_client, base_url):
    """Vérifie qu'on ne peut pas supprimer une Category utilisée par un Ingredient OU une Recipe"""

    # Sélectionner une catégorie différente de `setup_category`
    category_name = next((name for name in CATEGORY_NAME_CHOICES if name != setup_category.category_name), None)
    if not category_name:
        pytest.skip("Pas assez de catégories disponibles pour le test.")
    category = Category.objects.create(category_name=category_name)

    # Créer et ajouter un ingrédient qui utilise cette catégorie
    ingredient = Ingredient.objects.create(ingredient_name="Beurre")
    IngredientCategory.objects.create(ingredient=ingredient, category=category)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # ingredient.categories.add(category) # Ajout via ManyToManyField (sans on_delete=PROTECT et avec l'utilisation de sqlite).

    url = base_url(model_name) + f"{category.id}/"
    response = api_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Cette catégorie est utilisée" in response.json()["error"]
    assert Category.objects.filter(id=category.id).exists()  # Vérifie que la catégorie est toujours en base

    # Supprimer l'ingrédient et vérifier que la suppression est toujours bloquée si une recette existe
    ingredient.delete()

    # Créer et ajouter une recette qui utilise cette catégorie
    recipe = Recipe.objects.create(recipe_name="Tarte aux pommes")
    RecipeCategory.objects.create(recipe=recipe, category=category)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # recipe.categories.add(category) # Ajout via ManyToManyField (sans on_delete=PROTECT et avec l'utilisation de sqlite).

    response = api_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Cette catégorie est utilisée" in response.json()["error"]
    assert Category.objects.filter(id=category.id).exists()  # Vérifie que la catégorie est toujours en base



########## n’a plus d’intérêt, car on ne peut pas choisir category_type librement. ##########

# @pytest.mark.django_db
# def test_create_category_with_type(api_client, base_url):
#     """Test de création d’une catégorie avec un `category_type` valide"""
#     url = base_url(model_name)
#     data = {"category_name": "Viennoiseries", "category_type": "ingredient"}
#     response = api_client.post(url, data=json.dumps(data), content_type="application/json")
#     assert response.status_code == status.HTTP_201_CREATED
#     assert response.data["category_type"] == "ingredient"

# @pytest.mark.django_db
# def test_update_category_type(setup_category, api_client, base_url):
#     """Test de mise à jour du `category_type` d’une catégorie"""
#     url = base_url(model_name)
#     category_id = setup_category.id
#     data = {"category_type": "recipe"}
#     response = update_object(api_client, url, category_id, data=json.dumps(data))
#     assert response.status_code == status.HTTP_200_OK
#     setup_category.refresh_from_db()
#     assert setup_category.category_type == "recipe"