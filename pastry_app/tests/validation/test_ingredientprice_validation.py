import pytest
from rest_framework import status
from django.utils.timezone import now
from django.forms.models import model_to_dict
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.serializers import IngredientPriceSerializer
from pastry_app.models import Ingredient, Store, IngredientPrice
from pastry_app.constants import UNIT_CHOICES
# Définition du nom du modèle pour l'API
model_name = "ingredient_prices"

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
    return IngredientPrice.objects.create(ingredient=ingredient, brand_name="Bio Village", store=store, quantity=1, unit="kg", price=2.5)

@pytest.mark.parametrize("field_name", ["price", "quantity", "unit"])
@pytest.mark.django_db
def test_required_fields_ingredientprice_api(api_client, base_url, field_name):
    """ Vérifie que les champs obligatoires sont bien requis via l’API. """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", "A valid number is required.", "\"\" is not a valid choice."]
    for invalid_value in [None, ""]:  # Teste `None` et `""`
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **{field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["price", "quantity"])
@pytest.mark.django_db
def test_invalid_number_fields_ingredientprice_api(api_client, base_url, field_name, ingredient, store):
    """ Vérifie qu'un champ numérique (`FloatField`, `IntegerField`) refuse des valeurs non valides. """
    valid_data = {"ingredient": ingredient.ingredient_name, "store": store.id, "date": "2025-02-26", "quantity": 1, "price": 2.5, "unit": "kg", "brand_name":""}
    expected_errors = ["A valid number is required.", "must be a positive number", "Ensure this value is greater than or equal to 0."]  # Message attendu pour un format incorrect
    invalid_values = ["abc", "not_a_number", "2,5", 0, -1]  # Teste des chaînes qui ne sont pas des nombres valides
    print("Valid data envoyé :", {**valid_data, field_name: invalid_values})
    for invalid_value in invalid_values:
        validate_constraint_api(api_client, base_url, "ingredient_prices", field_name, expected_errors, **{**valid_data, field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["unit"]) # ChoiceField
@pytest.mark.django_db
def test_invalid_choice_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie que les champs `ChoiceField` et `ForeignKey` refusent une valeur invalide et accepte une valeur valide. """
    expected_error = "is not a valid choice."
    for invalid_value in ["", "invalid_choice"]:  # Teste une valeur vide et une valeur incorrecte
        validate_constraint_api(api_client, base_url, "ingredient_prices", field_name, expected_error, **{field_name: invalid_value})

    # Vérifie qu'une valeur valide est acceptée
    valid_unit = UNIT_CHOICES[0][0]  # Prend la première valeur valide
    # Données valides basées sur la fixture `ingredient_price`
    valid_data = {"ingredient": ingredient_price.ingredient.ingredient_name, "store": ingredient_price.store.id, "date": ingredient_price.date, 
        "quantity": ingredient_price.quantity, "price": ingredient_price.price, "brand_name":ingredient_price.brand_name}
    response = api_client.post(base_url("ingredient_prices"), {**valid_data, field_name: valid_unit}, format="json")

    assert response.status_code == 201, f"L'API aurait dû accepter `{valid_unit}`, mais a retourné {response.status_code}."

@pytest.mark.parametrize("field_name", ["brand_name"])
@pytest.mark.django_db
def test_min_length_fields_ingredientprice_api(api_client, base_url, field_name, ingredient, store):
    """ Vérifie que `brand_name` doit avoir une longueur minimale de 2 caractères via l’API. """
    valid_data = {"ingredient": ingredient.ingredient_name, "store": store.id, "price": 2.5, "quantity": 1, "unit": "kg"}  # Valeurs valides
    min_length = 2
    error_message = f"doit contenir au moins {min_length} caractères."
    validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

@pytest.mark.parametrize("field_name, raw_value", [("brand_name", "  BIO VILLAGE  "),])
@pytest.mark.django_db
def test_normalized_fields_ingredientprice_api(api_client, base_url, field_name, raw_value, ingredient, store):
    """ Vérifie que `brand_name` et est bien normalisé après création via l’API. """
    valid_data = {"ingredient": ingredient.ingredient_name, "store": store.id, "price": 2.5, "quantity": 1, "unit": "kg"}  # Valeurs valides
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.parametrize(("fields", "values"), [(("ingredient", "store", "quantity", "price", "unit"), (1, 1, 1, 2.5, "kg"))])
@pytest.mark.django_db
def test_unique_together_ingredientprice_api(api_client, base_url, fields, values):
    """ Vérifie qu'on ne peut pas créer deux `IngredientPrice` identiques via l’API (unique_together). """
    valid_data = dict(zip(fields, values))  # Associe dynamiquement chaque champ à une valeur
    validate_unique_together_api(api_client, base_url, model_name, valid_data)

@pytest.mark.parametrize("fields", [("ingredient", "store", "quantity", "unit")])
@pytest.mark.django_db
def test_update_ingredientprice_to_duplicate_api(api_client, base_url, fields):
    """ Vérifie qu'on ne peut PAS modifier un `IngredientPrice` pour dupliquer un autre. """
    values1 = [1, 1, 1, "kg"]
    values2 = [1, 2, 2, "g"]  # Différent
    valid_data1 = dict(zip(fields, values1))
    valid_data2 = dict(zip(fields, values2))

    validate_update_to_duplicate_api(api_client, base_url, model_name, valid_data1, valid_data2)

@pytest.mark.parametrize("related_models", [
    [("ingredient_prices", IngredientPriceSerializer, {}, {"ingredient": 1, "store": 1, "price": 2.5, "quantity": 1, "unit": "kg"}),]
])
@pytest.mark.django_db
def test_delete_ingredientprice_with_history(api_client, base_url, related_models):
    """ Vérifie qu'un `IngredientPrice` utilisé dans l'historique ne peut pas être supprimé. """
    expected_error = "Ce prix d’ingrédient est utilisé dans l'historique et ne peut pas être supprimé."
    validate_protected_delete_api(api_client, base_url, model_name, related_models, expected_error)
