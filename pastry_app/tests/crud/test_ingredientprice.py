import pytest
from rest_framework import status
from pastry_app.models import Ingredient, IngredientPrice, Store
from pastry_app.tests.base_api_test import api_client, base_url

model_name = "ingredient_prices"

# Création
# test_create_ingredient_price → Vérifie qu'on peut créer un IngredientPrice avec des données valides.
# test_create_duplicate_ingredient_price → Vérifie qu'on ne peut pas créer deux IngredientPrice identiques avec la même combinaison (ingredient, store, brand_name, quantity, unit).

# Lecture
# test_get_ingredient_price → Vérifie qu'on peut récupérer un IngredientPrice existant via GET /ingredient_prices/{id}/.
# test_get_ingredient_price_list → Vérifie qu'on peut récupérer la liste des IngredientPrice existants via GET /ingredient_prices/.
# test_get_nonexistent_ingredient_price → Vérifie qu'un GET sur un IngredientPrice inexistant retourne une erreur 404.

# Mise à jour
# test_update_ingredient_price → Vérifie qu'on ne peut pas mettre à jour un IngredientPrice via PATCH /ingredient_prices/{id}/ (405 METHOD NOT ALLOWED).

# Suppression
# test_delete_ingredient_price → Vérifie qu'on peut supprimer un IngredientPrice existant via DELETE /ingredient_prices/{id}/.
# test_delete_nonexistent_ingredient_price → Vérifie qu'une tentative de suppression d'un IngredientPrice inexistant retourne 404.

# Fixtures
@pytest.fixture
def ingredient(db):
    """ Crée un ingrédient en base pour éviter les erreurs de validation. """
    return Ingredient.objects.create(ingredient_name="farine")

@pytest.fixture
def store():
    """Crée un magasin pour les tests."""
    return Store.objects.create(store_name="Auchan", city="Paris", zip_code="75000")

@pytest.fixture
def setup_ingredient_price(db, ingredient, store):
    """Crée un prix d'ingrédient valide en base pour les tests."""
    return IngredientPrice.objects.create(ingredient=ingredient, brand_name="Bio Village", store=store, quantity=1, unit="kg", price=2.5)

def get_valid_data_ingredientprice(setup_ingredient_price):
    """ Génère un dictionnaire contenant toutes les données valides d'un `IngredientPrice`. """
    return {
        "ingredient": setup_ingredient_price.ingredient.ingredient_name,
        "store": setup_ingredient_price.store.id,
        "brand_name": setup_ingredient_price.brand_name,
        "price": setup_ingredient_price.price,
        "quantity": setup_ingredient_price.quantity,
        "unit": setup_ingredient_price.unit,
        "date": setup_ingredient_price.date
    }


# Création
@pytest.mark.django_db
def test_create_ingredientprice(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on peut créer un `IngredientPrice` avec des données valides."""
    url = base_url(model_name)
    valid_data = get_valid_data_ingredientprice(setup_ingredient_price)
    valid_data["brand_name"] = "toto" # changer le nom de la marque pour éviter une erreur 'must make a unique set' avec la fixture

    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["price"] == valid_data["price"]

@pytest.mark.django_db
def test_create_duplicate_ingredientprice(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on ne peut pas créer deux `IngredientPrice` identiques."""
    url = base_url(model_name)
    duplicate_data = get_valid_data_ingredientprice(setup_ingredient_price)
    duplicate_data["price"] = setup_ingredient_price.price  # Même prix

    response = api_client.post(url, duplicate_data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json()

# Lecture
@pytest.mark.django_db
def test_get_ingredientprice(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on peut récupérer un `IngredientPrice` existant via `GET /ingredient_prices/{id}/`."""
    url = f"{base_url(model_name)}{setup_ingredient_price.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["price"] == setup_ingredient_price.price

@pytest.mark.django_db
def test_get_ingredientprice_list(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on peut récupérer la liste des `IngredientPrice` existants via `GET /ingredient_prices/`."""
    url = base_url(model_name)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert any(ip["price"] == setup_ingredient_price.price for ip in response.json())

@pytest.mark.django_db
def test_get_nonexistent_ingredient_price(api_client, base_url):
    """Vérifie qu'un `GET` sur un `IngredientPrice` inexistant retourne une erreur `404`."""
    url = f"{base_url(model_name)}999999/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Mise à jour
@pytest.mark.django_db
def test_update_ingredientprice(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on ne peut pas mettre à jour un `IngredientPrice`."""
    url = f"{base_url(model_name)}{setup_ingredient_price.id}/"
    updated_data = {"price": 3.0}

    response = api_client.patch(url, updated_data, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED  # Update interdit

# Suppression
@pytest.mark.django_db
def test_delete_ingredientprice(api_client, base_url, setup_ingredient_price):
    """Vérifie qu'on peut supprimer un `IngredientPrice` existant via `DELETE /ingredient_prices/{id}/`."""
    url = f"{base_url(model_name)}{setup_ingredient_price.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.django_db
def test_delete_nonexistent_ingredientprice(api_client, base_url):
    """Vérifie qu'une tentative de suppression d'un `IngredientPrice` inexistant retourne `404`."""
    url = f"{base_url(model_name)}999999/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
