import pytest
from django.core.exceptions import ValidationError
from pastry_app.models import Store

@pytest.mark.django_db
def test_create_store():
    """ Vérifie qu'on peut créer un magasin valide """
    store = Store.objects.create(store_name="Carrefour", city="Paris", zip_code="75001")
    assert store.store_name == "Carrefour"
    assert store.city == "Paris"
    assert store.zip_code == "75001"

@pytest.mark.django_db
def test_store_name_cannot_be_empty():
    """ Vérifie qu'un magasin ne peut pas avoir un `store_name` vide """
    with pytest.raises(ValidationError, match="Le nom du magasin est obligatoire"):
        store = Store(store_name="", city="Paris")
        store.full_clean()  # Nécessaire pour déclencher `clean()`

@pytest.mark.django_db
def test_store_name_must_be_min_2_chars():
    """ Vérifie qu'un magasin doit avoir un nom d'au moins 2 caractères """
    with pytest.raises(ValidationError, match="Le nom du magasin doit contenir au moins 2 caractères."):
        store = Store(store_name="A", city="Paris")
        store.full_clean()

@pytest.mark.django_db
def test_store_requires_city_or_zip_code():
    """ Vérifie qu'un magasin doit avoir au moins une `city` ou `zip_code` """
    with pytest.raises(ValidationError, match="Si un magasin est renseigné, vous devez indiquer une ville ou un code postal."):
        store = Store(store_name="Auchan")  # Aucun `city` ni `zip_code`
        store.full_clean()

@pytest.mark.django_db
def test_store_unique_together_constraint():
    """ Vérifie qu'on ne peut pas créer deux magasins identiques (`store_name`, `city`, `zip_code`) """
    Store.objects.create(store_name="Monoprix", city="Lyon", zip_code="69001")
    
    with pytest.raises(ValidationError, match="Ce magasin existe déjà."):
        duplicate_store = Store(store_name="Monoprix", city="Lyon", zip_code="69001")
        duplicate_store.full_clean()  # Déclenche la validation unique_together 
