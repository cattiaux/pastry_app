import pytest
from django.utils.timezone import now
from rest_framework import status
from pastry_app.models import IngredientPriceHistory, Ingredient, Store
from pastry_app.tests.base_api_test import api_client, base_url

model_name = "ingredient_prices_history"

@pytest.fixture
def setup_ingredient_price_history(db):
    """ Crée un enregistrement d'historique de prix valide pour un ingrédient. """
    ingredient = Ingredient.objects.create(ingredient_name="Farine")
    store = Store.objects.create(store_name="Auchan", city="Paris", zip_code="75000")
    return IngredientPriceHistory.objects.create(ingredient=ingredient,
        store=store, brand_name="Bio Village", quantity=1, unit="kg", price=2.5, is_promo=False, promotion_end_date=None, date=now().date())


# Lecture
@pytest.mark.django_db
def test_get_ingredientpricehistory_list(api_client, base_url, setup_ingredient_price_history):
    """Vérifie qu'on peut récupérer la liste des `IngredientPriceHistory` existants via `GET /ingredient_prices_history/`."""
    url = base_url(model_name)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) > 0
    assert any(iph["price"] == setup_ingredient_price_history.price for iph in response.json())

@pytest.mark.django_db
def test_get_ingredientpricehistory(api_client, base_url, setup_ingredient_price_history):
    """Vérifie qu'on peut récupérer un `IngredientPriceHistory` existant via `GET /ingredient_prices_history/{id}/`."""
    url = f"{base_url(model_name)}{setup_ingredient_price_history.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["price"] == setup_ingredient_price_history.price

@pytest.mark.django_db
def test_get_nonexistent_ingredient_price_history(api_client, base_url):
    """Vérifie qu'un `GET` sur un `IngredientPriceHistory` inexistant retourne une erreur `404`."""
    url = f"{base_url(model_name)}999999/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Création
@pytest.mark.django_db
def test_create_ingredientpricehistory_api_forbidden(api_client, base_url, setup_ingredient_price_history):
    """ Vérifie que la création d’un `IngredientPriceHistory` est interdite via l’API. """
    url = base_url(model_name)
    valid_data = {
        "ingredient": setup_ingredient_price_history.ingredient.ingredient_name,
        "store": setup_ingredient_price_history.store.id,
        "brand_name": setup_ingredient_price_history.brand_name,
        "quantity": setup_ingredient_price_history.quantity,
        "unit": setup_ingredient_price_history.unit,
        "price": setup_ingredient_price_history.price,
        "is_promo": setup_ingredient_price_history.is_promo,
        "promotion_end_date": setup_ingredient_price_history.promotion_end_date,
    }
    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert any("Method \"POST\" not allowed." in value for value in response.json().values())

# Update
@pytest.mark.django_db
def test_update_ingredientpricehistory_api_forbidden(api_client, base_url, setup_ingredient_price_history):
    """ Vérifie que la mise à jour d’un `IngredientPriceHistory` est interdite via l’API. """
    url = base_url(model_name) + f"{setup_ingredient_price_history.id}/"
    response = api_client.put(url, {"price": 10.0}, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

# Delete
@pytest.mark.django_db
def test_delete_ingredientpricehistory_api_forbidden(api_client, base_url, setup_ingredient_price_history):
    """ Vérifie que la suppression d’un `IngredientPriceHistory` est interdite via l’API. """
    url = base_url(model_name) + f"{setup_ingredient_price_history.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED