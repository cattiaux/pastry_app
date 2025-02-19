import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Store
from pastry_app.tests.utils import *

@pytest.mark.django_db
def test_create_store():
    """ Vérifie qu'on peut créer un magasin valide """
    store = Store.objects.create(store_name="Carrefour", city="Paris", zip_code="75001")
    assert store.store_name == "Carrefour"
    assert store.city == "Paris"
    assert store.zip_code == "75001"

@pytest.mark.parametrize("field_name", ["store_name"])
@pytest.mark.django_db
def test_required_fields_store(field_name):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    validate_required_field(Store, field_name, "Ce champ est obligatoire.", city="Paris")

@pytest.mark.parametrize("field_name", ["store_name"])
@pytest.mark.django_db
def test_min_length_fields_store(field_name):
    """ Vérifie que les champs ont une longueur minimale de 2 caractères """
    validate_min_length(Store, field_name, 2, "Ce champ doit contenir au moins 2 caractères.", city="Paris")

@pytest.mark.django_db
def test_store_requires_city_or_zip_code():
    """ Vérifie qu'un magasin doit avoir au moins une `city` ou `zip_code` """
    with pytest.raises(ValidationError, match="Si un magasin est renseigné, vous devez indiquer une ville ou un code postal."):
        store = Store(store_name="Auchan")  # Aucun `city` ni `zip_code`
        store.full_clean()

@pytest.mark.parametrize("fields", [("store_name", "city", "zip_code")])
@pytest.mark.django_db
def test_unique_constraint_store(fields):
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (unique_together) """
    validate_unique_together(Store, "Ce magasin existe déjà.", **{fields[0]: "Monoprix", fields[1]: "Lyon", fields[2]: "69001"})