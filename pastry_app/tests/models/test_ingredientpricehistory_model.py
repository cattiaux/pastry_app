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
def test_ingredientpricehistory_str(ingredient_price_history):
    """ Vérifie que la méthode __str__() retourne la bonne valeur. """
    print("modèle store : ", ingredient_price_history.store)
    expected_str = f"""{ingredient_price_history.ingredient} - {ingredient_price_history.brand_name} @ {ingredient_price_history.store} ({ingredient_price_history.quantity}{ingredient_price_history.unit} pour {ingredient_price_history.price}€)"""
    print(expected_str)
    validate_model_str(ingredient_price_history, expected_str)

# @pytest.mark.django_db
# def test_ingredientpricehistory_str_db(ingredient_price_history):
#     """Vérifie que la méthode __str__ d'IngredientPriceHistory fonctionne correctement."""
#     expected_str = (
#         f"{ingredient_price_history.ingredient} - {ingredient_price_history.brand_name or 'Sans marque'} "
#         f"@ {ingredient_price_history.store or 'Magasin inconnu'} "
#         f"({ingredient_price_history.quantity}{ingredient_price_history.unit} pour {ingredient_price_history.price}€)"
#     )
#     assert str(ingredient_price_history) == expected_str

@pytest.mark.django_db
def test_create_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'un enregistrement historique est bien enregistré en base. """
    assert IngredientPriceHistory.objects.filter(id=ingredient_price_history.id).exists()


@pytest.mark.django_db
def test_unique_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas créer deux historiques identiques. """
    expected_error = "Ingredient price history with this Ingredient, Store, Brand name, Quantity, Unit, Date and Price already exists."
    validate_unique_together(
        IngredientPriceHistory, expected_error,
        ingredient=ingredient_price_history.ingredient,
        store=ingredient_price_history.store,
        brand_name=ingredient_price_history.brand_name,
        quantity=ingredient_price_history.quantity,
        unit=ingredient_price_history.unit,
        price=ingredient_price_history.price,
        is_promo=ingredient_price_history.is_promo,
        promotion_end_date=ingredient_price_history.promotion_end_date,
        date=ingredient_price_history.date
    )

@pytest.mark.django_db
def test_update_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas modifier un enregistrement d'historique existant. """
    with pytest.raises(ValidationError, match="L'historique des prix ne peut pas être modifié."):
        ingredient_price_history.price = 99.99
        ingredient_price_history.full_clean()

@pytest.mark.django_db
def test_delete_ingredientpricehistory_db(ingredient_price_history):
    """ Vérifie qu'on ne peut pas supprimer un enregistrement d'historique. """
    with pytest.raises(ValidationError, match="Les entrées de l'historique des prix ne peuvent pas être supprimées."):
        ingredient_price_history.delete()
