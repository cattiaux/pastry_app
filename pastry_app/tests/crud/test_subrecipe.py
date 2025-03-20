import pytest, json
from rest_framework import status
from pastry_app.models import Recipe, SubRecipe
from pastry_app.tests.base_api_test import api_client, base_url

# Définir model_name pour SubRecipe
model_name = "sub_recipes"

@pytest.fixture
def subrecipe():
    """ Crée une sous-recette d'une recette"""
    recipe1 = Recipe.objects.create(recipe_name="Tarte aux pommes")
    recipe2 = Recipe.objects.create(recipe_name="Crème pâtissière")
    return SubRecipe.objects.create(recipe=recipe1, sub_recipe=recipe2, quantity=200, unit="g")

@pytest.mark.django_db
def test_create_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on peut créer une `SubRecipe` via l'API """
    valid_data = {"recipe": subrecipe.recipe.id, "sub_recipe": subrecipe.sub_recipe.id, "quantity": 100, "unit": "g"}
    response = api_client.post(base_url(model_name), data=valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["recipe"] == subrecipe.recipe.id
    assert response.json()["sub_recipe"] == subrecipe.sub_recipe.id
    assert response.json()["quantity"] == 100
    assert response.json()["unit"] == "g"

@pytest.mark.django_db
def test_get_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on peut récupérer une `SubRecipe` via l'API """
    response = api_client.get(base_url(model_name) + f"{subrecipe.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == subrecipe.id
    assert response.json()["recipe"] == subrecipe.recipe.id
    assert response.json()["sub_recipe"] == subrecipe.sub_recipe.id

@pytest.mark.django_db
def test_list_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on peut récupérer la liste des `RecipeStep`. """
    new_recipe = Recipe.objects.create(recipe_name="Praliné noisettes")
    new_subrecipe2 = SubRecipe.objects.create(recipe=subrecipe.recipe, sub_recipe=new_recipe, quantity=200, unit="g")
    url = base_url(model_name) + f"{subrecipe.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 1  # Vérifie qu'on récupère bien des données

@pytest.mark.django_db
def test_update_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on peut modifier `sub_recipe`, `quantity` et `unit` d'une `SubRecipe` """
    new_sub_recipe = Recipe.objects.create(recipe_name="Crème chantilly")
    update_data = {"sub_recipe": new_sub_recipe.id, "quantity": 500, "unit": "kg"}
    url = base_url(model_name) + f"{subrecipe.id}/"
    response = api_client.patch(url, data=update_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["sub_recipe"] == new_sub_recipe.id
    assert response.json()["quantity"] == 500
    assert response.json()["unit"] == "kg"

@pytest.mark.django_db
def test_cannot_update_recipe_field_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on ne peut pas modifier `recipe` dans `SubRecipe` via l'API """
    url = base_url(model_name) + f"{subrecipe.id}/"
    response = api_client.patch(url, data={"recipe": subrecipe.recipe.id}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "recipe" in response.json()

@pytest.mark.django_db
def test_delete_subrecipe_api(api_client, base_url, subrecipe):
    """ Vérifie qu'on peut supprimer une `SubRecipe` via l'API """
    response = api_client.delete(base_url(model_name) + f"{subrecipe.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not SubRecipe.objects.filter(id=subrecipe.id).exists()  # Vérifie que la `SubRecipe` a bien été supprimée

@pytest.mark.django_db
def test_delete_nonexistent_subrecipe(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une SubRecipe qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_get_nonexistent_subrecipe(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une SubRecipe qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND