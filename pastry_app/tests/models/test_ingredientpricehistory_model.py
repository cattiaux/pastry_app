import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from pastry_app.models import Ingredient, Store, IngredientPriceHistory
from pastry_app.tests.utils import *

@pytest.fixture
def ingredient_price_history(db):
    """ Crée un enregistrement d'historique de prix valide pour un ingrédient. """
    ingredient = Ingredient.objects.create(ingredient_name="Farine")
    store = Store.objects.create(store_name="Auchan", city="Paris", zip_code="75000")
    return IngredientPriceHistory.objects.create(ingredient=ingredient,
        store=store, brand_name="Bio Village", quantity=1, unit="kg", price=2.5, is_promo=False, promotion_end_date=None, date=now().date())

@pytest.mark.django_db
@pytest.mark.parametrize("is_promo, has_store, brand_name, quantity, price, unit", [
    (False, True, "FeRrero ", 1.0, 2.5, "Kg"),
    (True, True, " KINDER ", 1.0, 2.0, "kg"),
    (False, False, "Bio VillaGe ", 1.0, 2.5, "kg"),
    (True, False, "Bio VillaGe ", 1.0, 2.5, "kg"),
])
def test_ingredientpricehistory_str(is_promo, has_store, brand_name, quantity, price, unit, ingredient_price_history):
    """ Vérifie que la méthode __str__() retourne la bonne valeur. """
    promo_text = " (Promo)" if is_promo else ""
    store_str = str(ingredient_price_history.store) if has_store else "Non renseigné"
    magasin = ingredient_price_history.store if has_store else None
    expected_str = f"{ingredient_price_history.ingredient.ingredient_name} - {normalize_case(brand_name)} @ {store_str} ({quantity}{normalize_case(unit)} pour {price}€{promo_text})"

    validate_model_str(IngredientPriceHistory, expected_str, ingredient=ingredient_price_history.ingredient, brand_name=brand_name, store=magasin, 
                       quantity=quantity, unit=unit, price=price, is_promo=is_promo)

@pytest.mark.django_db
def test_create_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'un enregistrement historique est bien enregistré en base. """
    assert IngredientPriceHistory.objects.filter(id=ingredient_price_history.id).exists()

@pytest.mark.django_db
def test_unique_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas créer deux historiques identiques. """
    expected_error = "Ingredient price history with this Ingredient, Store, Brand name, Quantity and Unit already exists."
    validate_unique_together(
        IngredientPriceHistory, expected_error,
        ingredient=ingredient_price_history.ingredient,
        store=ingredient_price_history.store,
        brand_name=ingredient_price_history.brand_name,
        quantity=ingredient_price_history.quantity,
        unit=ingredient_price_history.unit,
        price=ingredient_price_history.price,
        date=ingredient_price_history.date,
    )

@pytest.mark.django_db
def test_ingredientpricehistory_update_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas modifier un enregistrement d'historique existant. """
    ingredient_price_history.price = 30.0
    ingredient_price_history.save()
    ingredient_price_history.refresh_from_db()
    assert ingredient_price_history.price == 30.0

@pytest.mark.django_db
def test_ingredientpricehistory_deletion_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas supprimer un enregistrement d'historique. """
    price_id = ingredient_price_history.id
    ingredient_price_history.delete()
    assert not IngredientPriceHistory.objects.filter(id=price_id).exists()

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, raw_value", [("brand_name", "  BIO VILLAGE  "), ("unit", " Kg")])
def test_normalized_fields_ingredientpricehistory_db(field_name, raw_value, ingredient_price_history):
    """Vérifie que `brand_name` et "unit" sont bien normalisés avant stockage en base."""
    validate_field_normalization(IngredientPriceHistory, field_name, raw_value, ingredient=ingredient_price_history.ingredient, 
                                 store=ingredient_price_history.store, quantity=1, unit="kg" if field_name != "unit" else raw_value, price=2.5)

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, valid_other_field, expected_error", [
    ("price", {"quantity": 1}, "Un ingrédient doit avoir un prix strictement supérieur à 0"),
    ("quantity", {"price": 2.5}, "Une quantité ne peut pas être négative ou nulle")
])
def test_positive_values_ingredientprice_db(field_name, expected_error, ingredient_price_history, valid_other_field):
    """Vérifie que `price` et `quantity` doivent être strictement positifs en fournissant une valeur valide pour l'autre champ."""
    validate_constraint(IngredientPriceHistory, field_name, 0, expected_error, ingredient=ingredient_price_history.ingredient, 
                        store=ingredient_price_history.store, unit="kg", **valid_other_field)

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, value, valid_other_field", [
    ("price", 3, {"quantity": 1}),  # Teste un entier valide pour price
    ("quantity", 2, {"price": 2.5}),  # Teste un entier valide pour quantity
])
def test_integer_values_accepted_ingredientpricehistory_db(field_name, value, ingredient_price_history, valid_other_field):
    """ Vérifie que `price` et `quantity` acceptent des valeurs entières. """
    valid_data = {"ingredient": ingredient_price_history.ingredient, "store": ingredient_price_history.store, "unit": "kg", **valid_other_field}
    valid_data[field_name] = value  # Ajoute la valeur à tester
    obj = IngredientPriceHistory(**valid_data)
    obj.full_clean()  # Vérifie que cela passe sans erreur
    obj.save()  # Enregistre pour être sûr que la BDD accepte aussi
    assert getattr(obj, field_name) == float(value)  # Vérifie la conversion en float

@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["brand_name"])
def test_min_length_ingredientpricehistory_db(field_name, ingredient_price_history):
    """Vérifie que `brand_name` doit contenir au moins 2 caractères."""
    min_length = 2
    validate_constraint(IngredientPriceHistory, field_name, "a" * (min_length - 1), "doit contenir au moins 2 caractères.", 
                        ingredient=ingredient_price_history.ingredient, store=ingredient_price_history.store, price=2.5, quantity=1, unit="kg")
    
@pytest.mark.django_db
def test_unit_must_be_valid_db(ingredient_price_history):
    """Vérifie que `unit` doit être parmi `UNIT_CHOICES`."""
    with pytest.raises(ValidationError, match="L'unité .* n'est pas valide"):
        price = IngredientPriceHistory(ingredient=ingredient_price_history.ingredient, store=ingredient_price_history.store, 
                                       quantity=1, unit="INVALID_UNIT", price=2.5)  # Unité invalide
        price.full_clean()

@pytest.mark.parametrize("field_name, invalid_value, is_promo_value, expected_error", [
    ("promotion_end_date", now().date(), False, "Une date de fin de promo nécessite que `is_promo=True`."),
    ("promotion_end_date", now().date().replace(year=now().year-1), True, "La date de fin de promo ne peut pas être dans le passé.")
])
@pytest.mark.django_db
def test_promotion_end_date_constraints_db(field_name, invalid_value, is_promo_value, expected_error, ingredient_price_history):
    """ Vérifie les contraintes sur `promotion_end_date` en utilisant `validate_constraint`. """
    validate_constraint(IngredientPriceHistory, field_name=field_name, value=invalid_value, expected_error=expected_error, 
                        ingredient=ingredient_price_history.ingredient, store=ingredient_price_history.store, 
                        brand_name=ingredient_price_history.brand_name, quantity=ingredient_price_history.quantity, 
                        unit=ingredient_price_history.unit, price=ingredient_price_history.price, is_promo=is_promo_value)
    
@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["price", "quantity","unit"])
def test_required_fields_ingredientpricehistory_db(field_name, ingredient_price_history):
    """Vérifie que les champs obligatoires ne peuvent pas être vides ou nuls."""
    expected_error = "Le prix, la quantité et l'unité de mesure sont obligatoires."
    for invalid_value in [None, ""]:
        validate_constraint(IngredientPriceHistory, field_name, invalid_value, expected_error, ingredient=ingredient_price_history.ingredient, 
                            store=ingredient_price_history.store, unit="kg")
        
@pytest.mark.django_db
@pytest.mark.parametrize("is_promo, promotion_end_date", [(False, "2025-06-01")]) # Cas interdit : date de fin sans promo active
def test_promotion_requires_consistency_db(is_promo, promotion_end_date, ingredient_price_history):
    """ Vérifie que `is_promo` et `promotion_end_date` doivent être cohérents (modèle). """
    with pytest.raises(ValidationError, match="Une date de fin de promo nécessite que `is_promo=True`."):
        price = IngredientPriceHistory(ingredient=ingredient_price_history.ingredient, store=ingredient_price_history.store, price=2.5, 
                                quantity=250, unit="g", is_promo=is_promo, promotion_end_date=promotion_end_date)
        price.full_clean()  # Déclenche la validation