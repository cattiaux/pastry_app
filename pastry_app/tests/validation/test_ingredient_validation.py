import pytest
import json
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework import status
from pastry_app.models import Ingredient, Category, Label
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import CATEGORY_NAME_CHOICES, LABEL_NAME_CHOICES

"""Tests de validation et de gestion des erreurs pour le modèle Ingredient"""

# Définir model_name pour les tests de Ingredient
model_name = "ingredients"

@pytest.mark.django_db
def test_create_ingredient_without_name(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un ingrédient sans `ingredient_name`"""
    url = base_url(model_name)
    response = api_client.post(url, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ingredient_name" in response.json() # Vérifie que l'erreur concerne bien `ingredient_name`

@pytest.mark.django_db
def test_create_duplicate_ingredient(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer deux ingrédients avec le même `ingredient_name`"""
    url = base_url(model_name)

    # Création de la première instance d'Ingredient via l'API
    response1 = api_client.post(url, data=json.dumps({"ingredient_name": "Test ingredient"}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit

    # Essayer de créer un deuxième ingrédient avec le même nom via l'API (avec la même casse ou différente)
    response2 = api_client.post(url, data=json.dumps({"ingredient_name": normalize_case(" Test  Ingredient ")}), content_type="application/json")

    # Vérifier que l'API refuse le doublon avec un code 400
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "ingredient_name" in response2.json()

def test_create_ingredient_with_nonexistent_category(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un ingrédient avec une catégorie inexistante et que le message est clair """
    url = base_url(model_name)
    data = {"ingredient_name": "Nouvel Ingrédient", "categories": [9999]}  # ID inexistant
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "categories" in response.json()
    assert "n'existe pas" in response.json()["categories"][0]  # Vérification du message

def test_create_ingredient_with_nonexistent_label(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un ingrédient avec un label inexistant et que le message est clair """
    url = base_url(model_name)
    data = {"ingredient_name": "Nouvel Ingrédient", "labels": [9999]}  # ID inexistant
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "labels" in response.json()
    assert "n'existe pas" in response.json()["labels"][0]  # Vérification du message

    @pytest.mark.django_db
def test_update_ingredient_to_duplicate(api_client, base_url):
    """ Vérifie qu'on ne peut PAS modifier un ingrédient en lui donnant un `ingredient_name` déjà existant"""
    url = base_url(model_name)
    # Sélectionner deux catégories distinctes dynamiquement
    category_names = CATEGORY_NAME_CHOICES[:2]  # Prend les deux premières catégories disponibles
    if len(category_names) < 2:
        pytest.skip("Pas assez de catégories disponibles pour ce test.")
    category1, category2 = category_names  # Assigne deux catégories différentes
    # Créer deux catégories différentes
    response1 = api_client.post(url, {"category_name": category1})
    response2 = api_client.post(url, {"category_name": category2})
    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED
    # Vérification que la réponse contient bien l'ID
    category_id = response2.json()["id"]
    # Essayer de renommer "Viennoiseries" en "Desserts"
    response3 = api_client.patch(f"{url}{category_id}/", {"category_name": category1})
    # Vérifier que l'API refuse la modification
    assert response3.status_code == status.HTTP_400_BAD_REQUEST
    assert "category_name" in response3.json()

    """ Vérifie qu'on ne peut PAS modifier un ingrédient en lui donnant un `ingredient_name` déjà existant"""
    ingredient2 = Ingredient.objects.create(ingredient_name="Vanille")
    url = base_url(model_name) + f"{ingredient2.id}/"
    data = {"ingredient_name": normalize_case(ingredient.ingredient_name)}
    response = api_client.patch(url, data=json.dumps(data), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ingredient_name" in response.json()

@pytest.mark.django_db
def test_get_nonexistent_ingredient(api_client, base_url):
    """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un ingrédient qui n'existe pas"""
    url = base_url(model_name) + "9999/"  # ID inexistant
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND  # Doit renvoyer une erreur 404

@pytest.mark.django_db
def test_delete_nonexistent_ingredient(api_client, base_url):
    """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un ingrédient qui n'existe pas"""
    url = base_url(model_name) + "9999/"  # ID inexistant
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND  # Doit renvoyer une erreur 404

@pytest.mark.django_db
def test_ingredient_name_cannot_be_empty():
    """ Vérifie qu'on ne peut pas créer un ingrédient avec un `ingredient_name` vide"""
    with pytest.raises(ValidationError):
        ingredient = Ingredient(ingredient_name="")
        ingredient.full_clean() # Vérifie la validation avant la sauvegarde

# def test_cannot_assign_nonexistent_category(self):
#     """ Vérifie qu'on ne peut pas assigner une catégorie qui n'existe pas."""
#     ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    
#     with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
#         with transaction.atomic():  # Force Django à exécuter immédiatement la requête SQL
#             ingredient.categories.set([9999])  # 9999 est un ID qui n'existe pas

# def test_cannot_assign_nonexistent_label(self):
#     """ Vérifie qu'on ne peut pas assigner un label qui n'existe pas."""
#     ingredient = Ingredient.objects.create(ingredient_name="Chocolat")
    
#     with self.assertRaises(IntegrityError):  # La base de données doit lever une erreur
#         with transaction.atomic():  # Force Django à exécuter immédiatement la requête SQL
#             ingredient.labels.set([9999])  # 9999 est un ID qui n’existe pas