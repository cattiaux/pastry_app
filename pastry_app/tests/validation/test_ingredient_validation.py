import pytest, json
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from rest_framework import status
from pastry_app.models import Ingredient, Category
from pastry_app.tests.utils import normalize_case
from pastry_app.tests.base_api_test import api_client, base_url

"""Tests de validation et de gestion des erreurs pour le modèle Ingredient"""

pytestmark = pytest.mark.django_db

# Création
# test_create_ingredient_without_name → Vérifie qu'on ne peut PAS créer un ingrédient sans ingredient_name.
# test_create_duplicate_ingredient → Vérifie qu'on ne peut PAS créer un ingrédient avec un nom déjà existant.
# test_create_ingredient_with_nonexistent_category → Vérifie qu'on ne peut PAS associer une catégorie inexistante.
# test_create_ingredient_with_nonexistent_label → Vérifie qu'on ne peut PAS associer un label inexistant.

# Lecture
# test_get_nonexistent_ingredient → Vérifie qu'on obtient une erreur 404 lorsqu'on tente d'accéder à un ingrédient inexistant.

# Mise à jour
# test_update_ingredient_to_duplicate → Vérifie qu'on ne peut PAS modifier un ingrédient pour lui donner un ingredient_name déjà existant.
# test_update_ingredient_add_nonexistent_category → Vérifie qu'on ne peut PAS ajouter une catégorie inexistante à un ingrédient.
# test_update_ingredient_add_nonexistent_label → Vérifie qu'on ne peut PAS ajouter un label inexistant à un ingrédient.

# Suppression
# test_delete_nonexistent_ingredient → Vérifie qu'on obtient une erreur 404 lorsqu'on tente de supprimer un ingrédient inexistant.

# Contraintes Spécifiques
# test_ingredient_name_cannot_be_empty → Vérifie qu'on ne peut PAS créer un ingrédient avec un ingredient_name vide.
# test_ingredient_name_is_normalized → Vérifie que le ingredient_name est bien normalisé (minuscule, sans espaces inutiles).
# test_cannot_assign_nonexistent_category → Vérifie qu'on ne peut PAS attribuer une catégorie inexistante via une mise à jour.
# test_cannot_assign_nonexistent_label → Vérifie qu'on ne peut PAS attribuer un label inexistant via une mise à jour.

# Définir model_name pour les tests de Ingredient
model_name = "ingredients"

User = get_user_model()

@pytest.fixture
def user():
    admin = User.objects.create_user(username="user1", password="testpass123")
    admin.is_staff = True  # Assure que l'utilisateur est un admin
    admin.save()
    return admin 

def test_create_ingredient_without_name(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un ingrédient sans `ingredient_name`"""
    url = base_url(model_name)
    response = api_client.post(url, data=json.dumps({}), content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ingredient_name" in response.json() # Vérifie que l'erreur concerne bien `ingredient_name`

def test_create_duplicate_ingredient(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer deux ingrédients avec le même `ingredient_name`"""
    url = base_url(model_name)
    ingredient_name = "Test ingredient"
    # Création de la première instance d'Ingredient via l'API
    response1 = api_client.post(url, data=json.dumps({"ingredient_name": ingredient_name}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit

    # Essayer de créer un deuxième ingrédient avec le même nom via l'API (avec la même casse ou différente)
    response2 = api_client.post(url, data=json.dumps({"ingredient_name": normalize_case(ingredient_name)}), content_type="application/json")

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
    assert "object does not exist" in response.json()["categories"][0]  # Vérification du message

def test_create_ingredient_with_nonexistent_label(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un ingrédient avec un label inexistant et que le message est clair """
    url = base_url(model_name)
    data = {"ingredient_name": "Nouvel Ingrédient", "labels": [9999]}  # ID inexistant
    response = api_client.post(url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "labels" in response.json()
    assert "object does not exist" in response.json()["labels"][0]  # Vérification du message

def test_update_ingredient_to_duplicate(api_client, base_url, user):
    """ Vérifie qu'on ne peut PAS modifier un ingrédient en lui donnant un `ingredient_name` déjà existant"""
    api_client.force_authenticate(user=user)
    url = base_url(model_name)

    # Sélectionner deux noms d’ingrédients dynamiquement
    ingredient_names = ["Chocolat", "Vanille"]  # On pourrait les récupérer d’une constante si nécessaire
    ingredient1, ingredient2 = ingredient_names

    # Créer deux ingrédients via l'API
    response1 = api_client.post(url, {"ingredient_name": ingredient1})
    response2 = api_client.post(url, {"ingredient_name": ingredient2})

    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED

    # Récupérer l'ID du second ingrédient
    ingredient_id = response2.json()["id"]

    # Essayer de renommer "Vanille" en "Chocolat"
    response3 = api_client.patch(f"{url}{ingredient_id}/", {"ingredient_name": ingredient1})

    # Vérifier que l'API refuse la modification
    assert response3.status_code == status.HTTP_400_BAD_REQUEST
    assert "ingredient_name" in response3.json()

def test_get_nonexistent_ingredient(api_client, base_url):
    """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un ingrédient qui n'existe pas"""
    url = base_url(model_name) + "9999/"  # ID inexistant
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND  # Doit renvoyer une erreur 404

def test_delete_nonexistent_ingredient(api_client, base_url):
    """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un ingrédient qui n'existe pas"""
    url = base_url(model_name) + "9999/"  # ID inexistant
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND  # Doit renvoyer une erreur 404

def test_ingredient_name_cannot_be_empty():
    """ Vérifie qu'on ne peut pas créer un ingrédient avec un `ingredient_name` vide"""
    ingredient = Ingredient(ingredient_name="")
    with pytest.raises(ValidationError, match="This field cannot be blank"):
        ingredient.full_clean(exclude=['categories', 'labels']) # Vérifie la validation avant la sauvegarde

def test_cannot_assign_nonexistent_category(api_client, base_url, user):
    """ Vérifie qu'on ne peut PAS assigner une catégorie qui n'existe pas """
    api_client.force_authenticate(user=user)
    url = base_url(model_name)

    # Création d'un ingrédient via l'API
    response = api_client.post(url, {"ingredient_name": "Chocolat"})
    assert response.status_code == status.HTTP_201_CREATED  # Vérifie la création réussie
    ingredient_id = response.json()["id"]

    # Essayer d’assigner une catégorie inexistante
    update_url = f"{url}{ingredient_id}/"
    data = {"categories": [9999]}  # ID inexistant
    response = api_client.patch(update_url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "categories" in response.json()
    assert "object does not exist" in response.json()["categories"][0]

def test_cannot_assign_nonexistent_label(api_client, base_url, user):
    """ Vérifie qu'on ne peut PAS assigner un label qui n'existe pas """
    api_client.force_authenticate(user=user)
    url = base_url(model_name)

    # Création d'un ingrédient via l'API
    response = api_client.post(url, {"ingredient_name": "Chocolat"})
    assert response.status_code == status.HTTP_201_CREATED  # Vérifie la création réussie
    ingredient_id = response.json()["id"]

    # Essayer d’assigner un label inexistant
    update_url = f"{url}{ingredient_id}/"
    data = {"labels": [9999]}  # ID inexistant
    response = api_client.patch(update_url, data=json.dumps(data), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "labels" in response.json()
    assert "object does not exist" in response.json()["labels"][0]

def test_ingredient_name_is_normalized():
    """ Vérifie que le `ingredient_name` est bien normalisé (minuscule, sans espaces inutiles). """
    ingredient_name = "  Chocolat  Noir "
    ingredient = Ingredient.objects.create(ingredient_name=ingredient_name)
    assert ingredient.ingredient_name == normalize_case(ingredient_name)

def test_category_type_for_ingredient_api(api_client, base_url, user):
    # Création des catégories
    cat_ingredient = Category.objects.create(category_name="Cat Ingredient", category_type="ingredient", created_by=user)
    cat_recipe = Category.objects.create(category_name="Cat Recipe", category_type="recipe", created_by=user)
    cat_both = Category.objects.create(category_name="Cat Both", category_type="both", created_by=user)

    api_client.force_authenticate(user=user)     # Création d'un user admin pour pouvoir POST
    url = base_url(model_name)
    
    data = {"ingredient_name": "My Ingredient", "categories": [cat_ingredient.id, cat_recipe.id]}  # Ajoute une catégorie de type interdit
    response = api_client.post(url, data, format="json")
    assert response.status_code == 400   # Doit être refusé par la validation DRF
    assert "n'est pas valide pour un ingrédient" in str(response.data)

    data2 = {"ingredient_name": "My Ingredient", "categories": [cat_ingredient.id, cat_both.id]}
    response = api_client.post(url, data2, format="json")
    assert response.status_code in [200, 201]
