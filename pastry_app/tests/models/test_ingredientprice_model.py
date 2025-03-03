import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from pastry_app.models import IngredientPrice, Ingredient, Store, IngredientPriceHistory
from pastry_app.tests.utils import *

@pytest.fixture
def ingredient():
    """Crée un ingrédient pour les tests."""
    return Ingredient.objects.create(ingredient_name="Farine")

@pytest.fixture
def store():
    """Crée un magasin pour les tests."""
    return Store.objects.create(store_name="Auchan", city="Paris", zip_code="75000")

@pytest.fixture
def ingredient_price(ingredient, store):
    """Crée un prix valide pour un ingrédient."""
    return IngredientPrice.objects.create(
        ingredient=ingredient,
        brand_name="Bio Village",
        store=store,
        quantity=1.0,
        unit="kg",
        price=2.5
    )

@pytest.mark.django_db
def test_ingredientprice_creation_db(ingredient_price):
    """Vérifie qu'on peut créer un `IngredientPrice` valide."""
    assert isinstance(ingredient_price, IngredientPrice)
    assert ingredient_price.price == 2.5

@pytest.mark.django_db
def test_ingredientprice_update_db(ingredient_price):
    """Vérifie qu'on peut modifier un `IngredientPrice`."""
    ingredient_price.price = 3.0
    ingredient_price.save()
    ingredient_price.refresh_from_db()
    assert ingredient_price.price == 3.0

@pytest.mark.django_db
def test_ingredientprice_deletion_db(ingredient_price):
    """Vérifie que l'on peut supprimer un `IngredientPrice`."""
    price_id = ingredient_price.id
    ingredient_price.delete()
    assert not IngredientPrice.objects.filter(id=price_id).exists()

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, raw_value", [("brand_name", "  BIO VILLAGE  "), ("unit", " Kg")])
def test_normalized_fields_ingredientprice_db(field_name, raw_value, ingredient, store):
    """Vérifie que `brand_name` et `unit` sont bien normalisés avant stockage en base."""
    validate_field_normalization(IngredientPrice, field_name, raw_value, ingredient=ingredient, store=store, quantity=1, 
                                 unit="kg" if field_name != "unit" else raw_value, price=2.5)

@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["price", "quantity","unit"])
def test_required_fields_ingredientprice_db(field_name, ingredient, store):
    """Vérifie que les champs obligatoires ne peuvent pas être vides ou nuls."""
    expected_error = "Le prix, la quantité et l'unité de mesure sont obligatoires."
    for invalid_value in [None, ""]:
        validate_constraint(IngredientPrice, field_name, invalid_value, expected_error, ingredient=ingredient, store=store, unit="kg")

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, valid_other_field, expected_error", [
    ("price", {"quantity": 1}, "Un ingrédient doit avoir un prix strictement supérieur à 0"),
    ("quantity", {"price": 2.5}, "Une quantité ne peut pas être négative ou nulle")
])
def test_positive_values_ingredientprice_db(field_name, expected_error, ingredient, store, valid_other_field):
    """Vérifie que `price` et `quantity` doivent être strictement positifs en fournissant une valeur valide pour l'autre champ."""
    validate_constraint(IngredientPrice, field_name, 0, expected_error, ingredient=ingredient, store=store, unit="kg", **valid_other_field)

@pytest.mark.django_db
@pytest.mark.parametrize("field_name, value, valid_other_field", [
    ("price", 3, {"quantity": 1}),  # Teste un entier valide pour price
    ("quantity", 2, {"price": 2.5}),  # Teste un entier valide pour quantity
])
def test_integer_values_accepted_ingredientprice_db(field_name, value, ingredient, store, valid_other_field):
    """ Vérifie que `price` et `quantity` acceptent des valeurs entières. """
    valid_data = {"ingredient": ingredient, "store": store, "unit": "kg", **valid_other_field}
    valid_data[field_name] = value  # Ajoute la valeur à tester
    obj = IngredientPrice(**valid_data)
    obj.full_clean()  # Vérifie que cela passe sans erreur
    obj.save()  # Enregistre pour être sûr que la BDD accepte aussi
    assert getattr(obj, field_name) == float(value)  # Vérifie la conversion en float

@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["brand_name"])
def test_min_length_ingredientprice_db(field_name, ingredient, store):
    """Vérifie que `brand_name` doit contenir au moins 2 caractères."""
    min_length = 2
    validate_constraint(IngredientPrice, field_name, "a" * (min_length - 1), "doit contenir au moins 2 caractères.", 
                        ingredient=ingredient, store=store, price=2.5, quantity=1, unit="kg")

@pytest.mark.django_db
def test_unit_must_be_valid_db(ingredient, store):
    """Vérifie que `unit` doit être parmi `UNIT_CHOICES`."""
    with pytest.raises(ValidationError, match="L'unité .* n'est pas valide"):
        price = IngredientPrice(ingredient=ingredient, store=store, quantity=1, unit="INVALID_UNIT", price=2.5)  # Unité invalide
        price.full_clean()

@pytest.mark.django_db
def test_price_history_is_created_on_price_change_db(ingredient_price):
    """Vérifie qu'un historique est créé lors d'un changement de prix."""
    old_price = ingredient_price.price
    new_price = 3.0
    ingredient_price.price = new_price
    ingredient_price.save()

    # Vérifier que l'ancien prix est sauvegardé dans l'historique
    history_entry = IngredientPriceHistory.objects.filter(ingredient=ingredient_price.ingredient, store=ingredient_price.store, 
                                                          brand_name=ingredient_price.brand_name, quantity=ingredient_price.quantity, 
                                                          unit=ingredient_price.unit, price=old_price
                                                          ).order_by("-date").first()
    assert history_entry is not None
    assert history_entry.price == old_price

@pytest.mark.django_db
def test_promo_price_must_be_lower_than_normal_price_db(ingredient_price):
    """Vérifie qu’un prix promo doit être inférieur au dernier prix normal."""
    # Utilisation du prix normal existant via la fixture
    normal_ingredientprice = ingredient_price  # Prix normal déjà créé

    # Cas valide : Prix promo inférieur au prix normal
    valid_promo_price = IngredientPrice(ingredient=normal_ingredientprice.ingredient, store=normal_ingredientprice.store, 
                                        quantity=1, unit="kg", price=normal_ingredientprice.price-0.5, is_promo=True) # Prix promo valide (moins cher)
    valid_promo_price.full_clean()  # Ne doit pas lever d'erreur

    # Cas invalide : Prix promo supérieur ou égal au prix normal
    with pytest.raises(ValidationError, match="Le prix promo .* doit être inférieur au dernier prix normal"):
        promo_price = IngredientPrice(ingredient=normal_ingredientprice.ingredient, store=normal_ingredientprice.store, 
                                      quantity=1, unit="kg", price=normal_ingredientprice.price+0.5, is_promo=True) # Prix promo invalide (plus cher)
        promo_price.full_clean()
    
@pytest.mark.django_db
@pytest.mark.parametrize("is_promo, has_store, brand_name, quantity, price, unit", [
    (False, True, "Bio VillaGe ", 1.0, 2.5, "kg"),
    (True, True, "Bio VillaGe ", 1.0, 2.5, "kg"),
    (False, False, "Bio VillaGe ", 1.0, 2.5, "kg"),
    (True, False, "Bio VillaGe ", 1.0, 2.5, "kg"),
])
def test_ingredientprice_str(is_promo, has_store, brand_name, quantity, price, unit, ingredient, store):
    """Vérifie que `__str__()` affiche bien les informations correctement formatées."""
    promo_text = " (Promo)" if is_promo else ""
    store_str = str(store) if has_store else "Non renseigné"
    magasin = store if has_store else None
    expected_str = f"{ingredient.ingredient_name} - {normalize_case(brand_name)} @ {store_str} ({quantity}{unit} pour {price}€{promo_text})"

    validate_model_str(IngredientPrice, expected_str, ingredient=ingredient, brand_name=brand_name, store=magasin, 
                       quantity=quantity, unit=unit, price=price, is_promo=is_promo)

@pytest.mark.parametrize("field_name, invalid_value, is_promo_value, expected_error", [
    ("promotion_end_date", now().date(), False, "Une date de fin de promo nécessite que `is_promo=True`."),
    ("promotion_end_date", now().date().replace(year=now().year-1), True, "La date de fin de promo ne peut pas être dans le passé.")
])
@pytest.mark.django_db
def test_promotion_end_date_constraints_db(field_name, invalid_value, is_promo_value, expected_error, ingredient_price):
    """ Vérifie les contraintes sur `promotion_end_date` en utilisant `validate_constraint`. """
    validate_constraint(IngredientPrice, field_name=field_name, value=invalid_value, expected_error=expected_error, 
                        ingredient=ingredient_price.ingredient, store=ingredient_price.store, brand_name=ingredient_price.brand_name, 
                        quantity=ingredient_price.quantity, unit=ingredient_price.unit, price=ingredient_price.price, is_promo=is_promo_value)

@pytest.mark.django_db
def test_unique_ingredientprice_db(ingredient_price):
    """ Vérifie que deux `IngredientPrice` identiques ne peuvent pas exister en base. """
    expected_error = "Ingredient price with this Ingredient, Store, Brand name, Quantity and Unit already exists."
    validate_unique_together(IngredientPrice, expected_error, ingredient=ingredient_price.ingredient, store=ingredient_price.store, 
                             brand_name=ingredient_price.brand_name, quantity=ingredient_price.quantity, unit=ingredient_price.unit, 
                             price=ingredient_price.price)

@pytest.mark.django_db
@pytest.mark.parametrize("is_promo, promotion_end_date", [(False, "2025-06-01")]) # Cas interdit : date de fin sans promo active
def test_promotion_requires_consistency_db(is_promo, promotion_end_date, ingredient_price):
    """ Vérifie que `is_promo` et `promotion_end_date` doivent être cohérents (modèle). """
    with pytest.raises(ValidationError, match="Une date de fin de promo nécessite que `is_promo=True`."):
        price = IngredientPrice(ingredient=ingredient_price.ingredient, store=ingredient_price.store, price=2.5, 
                                quantity=250, unit="g", is_promo=is_promo, promotion_end_date=promotion_end_date)
        price.full_clean()  # Déclenche la validation

@pytest.mark.django_db
def test_ingredientprice_deletion_creates_history(ingredient_price):
    """ Vérifie que la suppression d’un `IngredientPrice` l’archive dans `IngredientPriceHistory`. """
    old_price = ingredient_price.price
    old_date = ingredient_price.date
    old_ingredient_name = ingredient_price.ingredient.ingredient_name
    ingredient_price.delete()      # Suppression du prix

    # Vérifier que l’archive a bien été créée
    history_entry = IngredientPriceHistory.objects.filter(
        ingredient_name=old_ingredient_name, price=old_price, date=old_date
    ).first()
    assert history_entry is not None, "L’ingredientPrice supprimé aurait dû être archivé."
    assert history_entry.price == old_price, "Le prix archivé ne correspond pas."
    assert history_entry.ingredient_name == old_ingredient_name, "Le nom de l’ingrédient archivé ne correspond pas."

@pytest.mark.django_db
def test_ingredient_deletion_removes_prices(ingredient):
    """ Vérifie que la suppression d’un `Ingredient` supprime ses `IngredientPrice`. """
    ingredient_id = ingredient.id  # Stocker l'ID avant suppression
    ingredient.delete()  # Suppression de l'ingrédient
    # Vérifier que plus aucun prix n'existe pour cet ingrédient
    assert not IngredientPrice.objects.filter(ingredient_id=ingredient_id).exists(), "Les prix liés à cet ingrédient auraient dû être supprimés."
