import pytest
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.models import Ingredient, Store, IngredientPrice, IngredientPriceHistory
from pastry_app.constants import UNIT_CHOICES

# Définition du nom du modèle pour l'API
model_name = "ingredient_prices"

pytestmark = pytest.mark.django_db

@pytest.fixture
def ingredient(db):
    """ Crée un ingrédient en base pour éviter les erreurs de validation. """
    return Ingredient.objects.create(ingredient_name="farine")

@pytest.fixture
def store():
    """Crée un magasin pour les tests."""
    return Store.objects.create(store_name="Auchan", city="Paris", zip_code="75000")

@pytest.fixture
def ingredient_price(ingredient, store):
    """Crée un prix valide pour un ingrédient."""
    return IngredientPrice.objects.create(ingredient=ingredient, brand_name="Bio Village", store=store, quantity=1, unit="kg", price=2.5, date= "2024-01-01")

def get_valid_ingredientprice_data(ingredient_price):
    """ Génère un dictionnaire contenant toutes les données valides d'un `IngredientPrice`. """
    return {
        "ingredient": ingredient_price.ingredient.ingredient_name,
        "store": ingredient_price.store.id,
        "brand_name": ingredient_price.brand_name,
        "price": ingredient_price.price,
        "quantity": ingredient_price.quantity,
        "unit": ingredient_price.unit,
        "date": ingredient_price.date
    }

@pytest.mark.parametrize("field_name", ["ingredient", "price", "quantity", "unit"])
def test_required_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie que les champs obligatoires sont bien requis via l’API. """
    # Créer un dictionnaire avec toutes les données valides
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", 
                       "A valid number is required.", "\"\" is not a valid choice."]
    
    # Vérifier avec `None` (champ absent)
    valid_data.pop(field_name)  # Supprimer le champ pour tester son absence
    validate_constraint_api(api_client, base_url, "ingredient_prices", field_name, expected_errors, **valid_data)

    # Vérifier avec `""` (champ vide)
    valid_data[field_name] = ""  # Réinsérer le champ mais vide
    validate_constraint_api(api_client, base_url, "ingredient_prices", field_name, expected_errors, **valid_data)

@pytest.mark.parametrize("field_name", ["price", "quantity"])
def test_invalid_number_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie qu'un champ numérique (`FloatField`, `IntegerField`) refuse des valeurs non valides. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    expected_errors = ["A valid number is required.", "must be a positive number", "Ensure this value is greater than or equal to 0."]  # Message attendu pour un format incorrect
    invalid_values = ["abc", "not_a_number", "2,5", 0, -1]  # Teste des chaînes qui ne sont pas des nombres valides

    for invalid_value in invalid_values:
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **{**valid_data, field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["unit"]) # ChoiceField
def test_invalid_choice_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie que les champs `ChoiceField` et `ForeignKey` refusent une valeur invalide et accepte une valeur valide. """
    # Créer un dictionnaire avec toutes les données valides
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    expected_error = "is not a valid choice."
    for invalid_value in ["", "invalid_choice"]:  # Teste une valeur vide et une valeur incorrecte
        valid_data[field_name] = invalid_value  # Modifier uniquement le champ testé
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_error, **valid_data)

    # Vérifie qu'une valeur valide est acceptée
    valid_unit = UNIT_CHOICES[0][0]  # Prend la première valeur valide
    valid_data[field_name] = UNIT_CHOICES[0][0] # Prend la première valeur valide
    response = api_client.post(base_url(model_name), valid_data, format="json")
    assert response.status_code == 201, f"L'API aurait dû accepter `{valid_unit}`, mais a retourné {response.status_code}."

@pytest.mark.parametrize("field_name", ["brand_name"])
def test_min_length_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie que `brand_name` doit avoir une longueur minimale de 2 caractères via l’API. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    valid_data.pop(field_name)
    min_length = 2
    error_message = f"doit contenir au moins {min_length} caractères."
    validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

@pytest.mark.parametrize("field_name, raw_value", [("brand_name", "  BIO VILLAGE  "),])
def test_normalized_fields_ingredientprice_api(api_client, base_url, field_name, raw_value, ingredient_price):
    """ Vérifie que `brand_name` et est bien normalisé après création via l’API. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    valid_data.pop(field_name)
    valid_data["quantity"] = 10  # Pour éviter de créer un même ingredientPrice que la fixture est avoir l'erreur 'must make a unique set.'
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.parametrize(("fields"), [("ingredient", "store", "quantity", "price", "unit")])
def test_unique_together_ingredientprice_api(api_client, base_url, fields, ingredient_price):
    """ Vérifie qu'on ne peut pas créer deux `IngredientPrice` identiques via l’API (unique_together). """
    # Utilisation des fixtures pour obtenir les valeurs dynamiques
    values = (ingredient_price.ingredient.ingredient_name, ingredient_price.store.id, 10, 100, "kg")
    valid_data = dict(zip(fields, values))  # Associe dynamiquement chaque champ à une valeur
    validate_unique_together_api(api_client, base_url, model_name, valid_data)

@pytest.mark.parametrize("is_promo, promotion_end_date", [(False, "2025-06-01")])  # Date de fin sans promo active
def test_promotion_requires_consistency_api(api_client, base_url, is_promo, promotion_end_date, ingredient, store):
    """ Vérifie que `is_promo` et `promotion_end_date` doivent être cohérents (API). """
    url = base_url(model_name)
    data = {"ingredient": ingredient.ingredient_name, "store": store.id, "price": 2.5, "quantity": 1, 
            "unit": "kg", "is_promo": is_promo, "promotion_end_date": promotion_end_date}
    response = api_client.post(url, data, format="json")
    assert response.status_code == 400  # Vérifier que l'API bloque bien la requête
    assert "Une date de fin de promotion nécessite que `is_promo=True`." in response.json().get("non_field_errors", [])

def test_patch_price_api_archives_old_version(api_client, base_url, ingredient_price):
    """Vérifie que l’API PATCH sur le prix (date plus récente) archive bien l’ancienne version."""
    url = f"{base_url(model_name)}{ingredient_price.id}/"
    new_price = ingredient_price.price + 2.0
    new_date = (ingredient_price.date.replace(year=ingredient_price.date.year + 1)
                if ingredient_price.date else "2025-06-30")
    response = api_client.patch(url, {"price": new_price, "date": new_date}, format="json")
    print(response.json())
    assert response.status_code == 200
    # Vérifier que l’archive existe
    archived = IngredientPriceHistory.objects.filter(
        ingredient=ingredient_price.ingredient,
        store=ingredient_price.store,
        brand_name=ingredient_price.brand_name,
        quantity=ingredient_price.quantity,
        unit=ingredient_price.unit,
        price=ingredient_price.price,  # old price
        date=ingredient_price.date,
    ).exists()
    assert archived, "L’ancienne version devrait être archivée après update API prix (date plus récente)."

def test_patch_price_api_archives_new_value_if_older(api_client, base_url, ingredient_price):
    """Vérifie que PATCH sur le prix avec une date plus ancienne archive la nouvelle valeur, l’objet reste inchangé."""
    url = f"{base_url(model_name)}{ingredient_price.id}/"
    new_price = ingredient_price.price + 2.0
    past_date = ingredient_price.date.replace(year=ingredient_price.date.year - 1)
    response = api_client.patch(url, {"price": new_price, "date": past_date}, format="json")
    assert response.status_code == 200
    # Vérifier que la nouvelle version existe dans l’historique
    archived = IngredientPriceHistory.objects.filter(
        ingredient=ingredient_price.ingredient,
        store=ingredient_price.store,
        brand_name=ingredient_price.brand_name,
        quantity=ingredient_price.quantity,
        unit=ingredient_price.unit,
        price=new_price,
        date=past_date,
    ).exists()
    assert archived, "La nouvelle version rétroactive doit être archivée."
    # Vérifier que l’instance courante n’a pas changé
    ingredient_price.refresh_from_db()
    assert ingredient_price.price != new_price

def test_patch_tuple_unique_field_forbidden(api_client, base_url, ingredient_price, store):
    """Vérifie qu’un PATCH sur un champ du tuple unique retourne une 400 (forbidden)."""
    url = f"{base_url(model_name)}{ingredient_price.id}/"
    # new_store = store
    new_store = Store.objects.create(store_name="Monoprix", city="Lyon", zip_code="69000")

    response = api_client.patch(url, {"store": new_store.id}, format="json")
    assert response.status_code == 400
    assert "ne peut pas être modifié" in str(response.data)

def test_patch_soft_fields_ok(api_client, base_url, ingredient_price):
    """Vérifie qu’un PATCH sur is_promo/date/promotion_end_date fonctionne sans archivage."""
    url = f"{base_url('ingredient_prices')}{ingredient_price.id}/"
    resp = api_client.patch(url, {"is_promo": True}, format="json")
    assert resp.status_code == 200
    resp2 = api_client.patch(url, {"promotion_end_date": "2026-02-01", "is_promo": True}, format="json")
    assert resp2.status_code == 200

def test_api_delete_no_archive(api_client, base_url, ingredient_price):
    """Vérifie que la suppression via l’API ne crée PAS d’archive."""
    url = f"{base_url(model_name)}{ingredient_price.id}/"
    resp = api_client.delete(url)
    assert resp.status_code == 204
    from pastry_app.models import IngredientPriceHistory
    archived = IngredientPriceHistory.objects.filter(
        ingredient=ingredient_price.ingredient,
        store=ingredient_price.store,
        brand_name=ingredient_price.brand_name,
        quantity=ingredient_price.quantity,
        unit=ingredient_price.unit,
        price=ingredient_price.price,
        date=ingredient_price.date,
    ).exists()
    assert not archived, "Aucune archive ne doit être créée à la suppression via l’API."



