from pastry_app.models import Label, Ingredient, Recipe, IngredientLabel, RecipeLabel
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url, update_object#, create_object, get_object, delete_object
import pytest, json
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import LABEL_NAME_CHOICES, LABEL_TYPE_MAP

# Définir model_name pour les tests de Label
model_name = "labels"

@pytest.fixture(params=LABEL_NAME_CHOICES)
def setup_label(request):
    """Création d’un label avant chaque test (dynamique), parmi les choix disponibles de LABEL_NAME_CHOICES"""
    return Label.objects.create(label_name=request.param)

@pytest.mark.django_db
def test_create_label(setup_label, api_client, base_url):
    """Test de création d’un label"""
    url = base_url(model_name)

    # Sélectionner un label différent de `setup_label`
    label_name = next((name for name in LABEL_NAME_CHOICES if name != setup_label.label_name), None)
    if not label_name:
        pytest.skip("Pas assez de labels disponibles pour le test.")

    data = {"label_name": label_name, "label_type": "both"}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_201_CREATED
    assert Label.objects.filter(label_name=normalize_case(label_name)).exists()

@pytest.mark.django_db
def test_label_type_assignment(api_client, base_url):
    """Vérifie que l'API assigne le bon `label_type` en fonction du `label_name`"""
    url = base_url(model_name)

    # Sélectionner un label valide
    label_name, expected_type = next(iter(LABEL_TYPE_MAP.items()))  # Prend un élément valide

    data = {"label_name": label_name}
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    # Vérifier que la création fonctionne bien et que `label_type` est bien assigné
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["label_type"] == expected_type

@pytest.mark.django_db
def test_get_label(setup_label, api_client, base_url):
    """Test de récupération d’un label"""
    label_id = setup_label.id
    url = base_url(model_name)+f"{label_id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("label_name") == normalize_case(setup_label.label_name)

@pytest.mark.django_db
def test_update_label(setup_label, api_client, base_url):
    """Test de mise à jour d’un label avec le bon `label_type`"""
    url = base_url(model_name)
    label_id = setup_label.id

    # Sélectionner un label différent de `setup_label`
    label_name = next((name for name in LABEL_NAME_CHOICES if name != setup_label.label_name), None)
    if not label_name:
        pytest.skip("Pas assez de labels disponibles pour le test.")

    label_type = LABEL_TYPE_MAP[label_name]  # Récupérer le bon type
    data = {"label_name": label_name, "label_type": label_type}
    response = update_object(api_client, url, label_id, data=json.dumps(data))
    assert response.status_code == status.HTTP_200_OK # Vérifier que la mise à jour fonctionne
    setup_label.refresh_from_db()
    assert setup_label.label_name == label_name
    assert setup_label.label_type == label_type  # Vérifier que `label_type` est correct

@pytest.mark.django_db
def test_delete_label(setup_label, api_client, base_url):
    """Test de suppression d’un label"""
    label_id = setup_label.id
    url = base_url(model_name)+f"{label_id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Label.objects.filter(id=label_id).exists()

@pytest.mark.django_db
def test_get_nonexistent_label(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un Label qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.get(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_nonexistent_label(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un Label qui n'existe pas"""
    url = base_url(model_name)+f"9999/" # ID inexistant
    response = api_client.delete(url)  
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_label_with_linked_objects(setup_label, api_client, base_url):
    """Vérifie qu'on ne peut pas supprimer un Label utilisé par un Ingredient OU une Recipe"""

    # Sélectionner un label différente de `setup_label`
    label_name = next((name for name in LABEL_NAME_CHOICES if name != setup_label.label_name), None)
    if not label_name:
        pytest.skip("Pas assez de labels disponibles pour le test.")
    label = Label.objects.create(label_name=label_name)

    # Créer et ajouter un ingrédient qui utilise ce label
    ingredient = Ingredient.objects.create(ingredient_name="Beurre")
    IngredientLabel.objects.create(ingredient=ingredient, label=label)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # ingredient.labels.add(label) # Ajout via ManyToManyField (sans on_delete=PROTECT et avec l'utilisation de sqlite).

    url = base_url(model_name) + f"{label.id}/"
    response = api_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Ce label est utilisé" in response.json()["error"]
    assert Label.objects.filter(id=label.id).exists()  # Vérifie que le label est toujours en base

    # Supprimer l'ingrédient et vérifier que la suppression est toujours bloquée si une recette existe
    ingredient.delete()

    # Créer et ajouter une recette qui utilise ce label
    recipe = Recipe.objects.create(recipe_name="Tarte aux pommes")
    RecipeLabel.objects.create(recipe=recipe, label=label)  # Ajout via table intermédiaire (conséquence de on_delete=PROTECT et l'utilisation de postgresql au lieu de sqlite)
    # recipe.labels.add(label) # Ajout via ManyToManyField (sans on_delete=PROTECT et avec l'utilisation de sqlite).

    response = api_client.delete(url)

    # Vérifie que PostgreSQL bloque la suppression
    assert response.status_code == status.HTTP_400_BAD_REQUEST  # Vérifie que l'API bloque bien la suppression
    assert "Ce label est utilisé" in response.json()["error"]
    assert Label.objects.filter(id=label.id).exists()  # Vérifie que le label est toujours en base
