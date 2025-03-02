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
