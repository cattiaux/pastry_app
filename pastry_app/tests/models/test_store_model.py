import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Store
from pastry_app.tests.utils import *

pytestmark = pytest.mark.django_db

@pytest.fixture
def store():
    """ Crée un magasin par défaut pour les tests. """
    return Store.objects.create(store_name="Monoprix", city="Lyon", zip_code="69001", address="1 rue de la République")

def test_store_creation(store):
    """ Vérifie qu'on peut créer un magasin valide """
    assert isinstance(store, Store)
    assert store.store_name == normalize_case("Monoprix")

def test_store_update(store):
    """ Vérifie que l'on peut modifier un Store"""
    # Sélectionner un store différent de `store`
    store_update_name = "Carrefour"
    store.store_name = store_update_name
    store.save()
    store.refresh_from_db()
    assert store.store_name == normalize_case(store_update_name)

def test_store_deletion(store):
    """ Vérifie que l'on peut supprimer un Store"""
    store_id = store.id
    store.delete()
    assert not Store.objects.filter(id=store_id).exists()

@pytest.mark.parametrize("field_name", ["store_name"])
def test_required_fields_store(field_name):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    for invalid_value in [None, ""]:
        validate_constraint(Store, field_name, invalid_value, "field cannot be null", city="Paris")

@pytest.mark.parametrize("field_name, valid_data", [
        ("store_name", {"zip_code": "59100"}),  # Vérifie store_name en ajoutant un code postal valide
        ("city", {"store_name": "Monoprix"}),    # Vérifie city en ajoutant un store_name valide
        ("address", {"store_name": "Monoprix"})    # Vérifie city en ajoutant un store_name valide
])
def test_min_length_fields_store(field_name, valid_data):
    """ Vérifie que les champs ont une longueur minimale de 2 caractères """
    min_length = 2
    validate_constraint(Store, field_name, "a" * (min_length - 1), "doit contenir au moins 2 caractères.", **valid_data)

@pytest.mark.parametrize("fields", [("store_name", "city", "zip_code", "address")])
def test_unique_constraint_store(fields, store):
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (UniqueConstraint) """
    # Construire dynamiquement `valid_data` avec les valeurs de la fixture `store`
    valid_data = {field: getattr(store, field) for field in fields}
    validate_unique_together(Store, "Ce magasin existe déjà.", **valid_data)

@pytest.mark.parametrize("city, zip_code, address", [(None, None, None), ("", "", "")])
def test_store_requires_city_or_zip_code_or_address(city, zip_code, address):
    """ Vérifie qu'un store ne peut pas être créé sans au moins une `city`, un `zip_code` ou une `address` (modèle). """
    with pytest.raises(ValidationError, match="Si un magasin est renseigné, vous devez indiquer une ville, un code postal ou une adresse."):
        store = Store(store_name="Auchan", city=city, zip_code=zip_code, address=address)
        store.full_clean()  # Déclenche la validation

@pytest.mark.parametrize("field_name, raw_value", [
    ("store_name", "  MONOPRIX  "),
    ("city", "  LYON  "),
    ("address", "  123 Rue de la République  "),
])
def test_normalized_fields_store(field_name, raw_value):
    """ Vérifie que les champs sont bien normalisés avant stockage en base. """
    valid_data = {"store_name": "Monoprix", "city": "Lyon", "zip_code": "69001", "address": "1 boulevard de Fourmies"}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer dynamiquement le champ en cours de test
    validate_field_normalization(Store, field_name, raw_value, **valid_data)
