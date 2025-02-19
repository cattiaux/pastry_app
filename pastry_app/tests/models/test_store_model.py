import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Store
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Store
model_name = "stores"

@pytest.fixture
def store():
    """ Crée un magasin par défaut pour les tests. """
    return Store.objects.create(store_name="Monoprix", city="Lyon", zip_code="69001")

@pytest.mark.django_db
def test_store_creation(store):
    """ Vérifie qu'on peut créer un magasin valide """
    assert isinstance(store, Store)
    assert store.store_name == normalize_case("Monoprix")

@pytest.mark.django_db
def test_store_update(store):
    """ Vérifie que l'on peut modifier un Store"""
    # Sélectionner un store différent de `store`
    store_update_name = "Carrefour"
    store.store_name = store_update_name
    store.save()
    store.refresh_from_db()
    assert store.store_name == normalize_case(store_update_name)

@pytest.mark.django_db
def test_store_deletion(store):
    """ Vérifie que l'on peut supprimer un Store"""
    store_id = store.id
    store.delete()
    assert not Store.objects.filter(id=store_id).exists()

@pytest.mark.parametrize("field_name", ["store_name"])
@pytest.mark.django_db
def test_required_fields_store(field_name):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    validate_required_field(Store, field_name, "field cannot be null", city="Paris")

@pytest.mark.parametrize("field_name, valid_data", [
        ("store_name", {"zip_code": "59100"}),  # Vérifie store_name en ajoutant un code postal valide
        ("city", {"store_name": "Monoprix"})    # Vérifie city en ajoutant un store_name valide
])
@pytest.mark.django_db
def test_min_length_fields_store(field_name, valid_data):
    """ Vérifie que les champs ont une longueur minimale de 2 caractères """
    validate_min_length(Store, field_name, 2, "doit contenir au moins 2 caractères.", **valid_data)

@pytest.mark.parametrize("fields", [("store_name", "city", "zip_code")])
@pytest.mark.django_db
def test_unique_constraint_store(fields, store):
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (unique_together) """
    # Construire dynamiquement `valid_data` avec les valeurs de la fixture `store`
    valid_data = {field: getattr(store, field) for field in fields}
    validate_unique_together(Store, "Ce magasin existe déjà.", create_initial=False, **valid_data)

@pytest.mark.django_db
def test_store_requires_city_or_zip_code():
    """ Vérifie qu'un magasin doit avoir au moins une `city` ou `zip_code` """
    with pytest.raises(ValidationError, match="Si un magasin est renseigné, vous devez indiquer une ville ou un code postal."):
        store = Store(store_name="Auchan")  # Aucun `city` ni `zip_code`
        store.full_clean()
