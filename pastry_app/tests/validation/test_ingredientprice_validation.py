import pytest
from rest_framework import status
from django.utils.timezone import now
from django.forms.models import model_to_dict
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *
from pastry_app.serializers import IngredientPriceSerializer
from pastry_app.models import Ingredient, Store, IngredientPrice, IngredientPriceHistory
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
    return IngredientPrice.objects.create(ingredient=ingredient, brand_name="Bio Village", store=store, quantity=1, unit="kg", price=2.5, date= "2025-01-01")

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
@pytest.mark.django_db
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
@pytest.mark.django_db
def test_invalid_number_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie qu'un champ numérique (`FloatField`, `IntegerField`) refuse des valeurs non valides. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    expected_errors = ["A valid number is required.", "must be a positive number", "Ensure this value is greater than or equal to 0."]  # Message attendu pour un format incorrect
    invalid_values = ["abc", "not_a_number", "2,5", 0, -1]  # Teste des chaînes qui ne sont pas des nombres valides

    for invalid_value in invalid_values:
        validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **{**valid_data, field_name: invalid_value})

@pytest.mark.parametrize("field_name", ["unit"]) # ChoiceField
@pytest.mark.django_db
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
@pytest.mark.django_db
def test_min_length_fields_ingredientprice_api(api_client, base_url, field_name, ingredient_price):
    """ Vérifie que `brand_name` doit avoir une longueur minimale de 2 caractères via l’API. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    valid_data.pop(field_name)
    min_length = 2
    error_message = f"doit contenir au moins {min_length} caractères."
    validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

@pytest.mark.parametrize("field_name, raw_value", [("brand_name", "  BIO VILLAGE  "),])
@pytest.mark.django_db
def test_normalized_fields_ingredientprice_api(api_client, base_url, field_name, raw_value, ingredient_price):
    """ Vérifie que `brand_name` et est bien normalisé après création via l’API. """
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    valid_data.pop(field_name)
    valid_data["quantity"] = 10  # Pour éviter de créer un même ingredientPrice que la fixture est avoir l'erreur 'must make a unique set.'
    validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data)

@pytest.mark.parametrize(("fields"), [("ingredient", "store", "quantity", "price", "unit")])
@pytest.mark.django_db
def test_unique_together_ingredientprice_api(api_client, base_url, fields, ingredient_price):
    """ Vérifie qu'on ne peut pas créer deux `IngredientPrice` identiques via l’API (unique_together). """
    # Utilisation des fixtures pour obtenir les valeurs dynamiques
    values = (ingredient_price.ingredient.ingredient_name, ingredient_price.store.id, 10, 100, "kg")
    valid_data = dict(zip(fields, values))  # Associe dynamiquement chaque champ à une valeur
    validate_unique_together_api(api_client, base_url, model_name, valid_data)

@pytest.mark.parametrize("new_price", [3.0, 4.5]) 
@pytest.mark.django_db
def test_update_ingredientprice_api(api_client, base_url, ingredient_price, new_price):
    """ Vérifie que l’API interdit la mise à jour des prix d’ingrédients. """
    url = f"{base_url(model_name)}{ingredient_price.id}/"
    response = api_client.put(url, {"price": new_price}, format="json")  # Essai d'update

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json()["error"] == "La mise à jour des prix est interdite. Créez un nouvel enregistrement."

@pytest.mark.django_db
def test_price_update_creates_new_ingredientprice(api_client, base_url, ingredient_price):
    """ Vérifie qu'un changement de prix crée un nouvel `IngredientPrice` et archive l'ancien. """
    url = base_url(model_name)
    valid_data = get_valid_ingredientprice_data(ingredient_price)
    valid_data["price"] = ingredient_price.price + 1.0  # Simule une augmentation de prix

    # Création d'un prix identique avec un prix différent
    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED  # Vérifie que le nouveau prix est bien créé

   # Vérifier que l'ancienne version de IngredientPrice a bien été archivée
    archived = IngredientPriceHistory.objects.filter(ingredient=ingredient_price.ingredient, store=ingredient_price.store, brand_name=ingredient_price.brand_name, 
                                                     quantity=ingredient_price.quantity, unit=ingredient_price.unit, price=ingredient_price.price, is_promo=ingredient_price.is_promo
                                                     ).exists()
    assert archived, "L'ancien prix n'a pas été archivé dans IngredientPriceHistory !" # Vérifier que l'ancien prix est archivé

@pytest.mark.django_db
@pytest.mark.parametrize("is_promo, promotion_end_date", [(False, "2025-06-01")])  # Date de fin sans promo active
def test_promotion_requires_consistency_api(api_client, base_url, is_promo, promotion_end_date, ingredient, store):
    """ Vérifie que `is_promo` et `promotion_end_date` doivent être cohérents (API). """
    url = base_url("ingredient_prices")
    data = {"ingredient": ingredient.ingredient_name, "store": store.id, "price": 2.5, "quantity": 1, 
            "unit": "kg", "is_promo": is_promo, "promotion_end_date": promotion_end_date}
    response = api_client.post(url, data, format="json")
    assert response.status_code == 400  # Vérifier que l'API bloque bien la requête
    assert "Une date de fin de promotion nécessite que `is_promo=True`." in response.json().get("non_field_errors", [])
