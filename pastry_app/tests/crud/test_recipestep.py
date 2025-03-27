import pytest
from rest_framework import status
from pastry_app.models import Recipe, RecipeStep
from pastry_app.tests.base_api_test import api_client, base_url, update_object

# Définir model_name pour les tests de RecipeStep
model_name = "recipesteps"
pytestmark = pytest.mark.django_db

@pytest.fixture
def setup_recipe():
    """ Crée une recette de test. """
    return Recipe.objects.create(recipe_name="Tarte aux fraises", chef_name="Chef Test")

@pytest.fixture
def setup_recipestep(setup_recipe):
    """ Crée un RecipeStep lié à la recette de test. """
    return RecipeStep.objects.create(recipe=setup_recipe, step_number=1, instruction="Préparer la pâte.")

def test_create_recipestep(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on peut créer un `RecipeStep` via l'API. """
    url = base_url(model_name)
    valid_data = {"recipe": setup_recipestep.recipe.id, "step_number": setup_recipestep.step_number+1, "instruction": setup_recipestep.instruction}
    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert RecipeStep.objects.filter(recipe=setup_recipestep.recipe.id, step_number=setup_recipestep.step_number+1).exists()

def test_list_recipestep(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on peut récupérer la liste des `RecipeStep`. """
    url = base_url(model_name) + f"{setup_recipestep.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0  # Vérifie qu'on récupère bien des données

def test_get_recipestep(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on peut récupérer un `RecipeStep` spécifique. """
    url = f"{base_url(model_name)}{setup_recipestep.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == setup_recipestep.id

def test_partial_update_recipestep(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on peut modifier un `RecipeStep` via l'API via PATCH """
    url = base_url(model_name)+f"{setup_recipestep.id}/"
    updated_data = {"instruction": "Mélanger doucement."}
    response = api_client.patch(url, updated_data, format="json")
    print(response.json())
    assert response.status_code == status.HTTP_200_OK  # Vérifie que la mise à jour fonctionne

    # Vérifie en base que la modification a bien été enregistrée
    setup_recipestep.refresh_from_db()
    assert setup_recipestep.instruction == "Mélanger doucement." 

def test_delete_recipestep(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on peut supprimer un `RecipeStep` via l'API. """
    # Crée une nouvelle étape pour éviter l'erreur de supprimer la seule étape existante
    new_step = RecipeStep.objects.create(recipe=setup_recipestep.recipe, step_number=2, instruction="Etape 2")
    url = base_url(model_name)+f"{new_step.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not RecipeStep.objects.filter(id=new_step.id).exists()

def test_cannot_delete_last_recipestep_api(api_client, base_url, setup_recipestep):
    """ Vérifie qu'on ne peut pas supprimer le dernier `RecipeStep` d'une recette. """
    url = f"{base_url(model_name)}{setup_recipestep.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Une recette doit contenir au moins une étape." in response.json()["detail"]

def test_delete_nonexistent_recipestep(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer une RecipeStep qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_get_nonexistent_recipestep(admin_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer une RecipeStep qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = admin_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND