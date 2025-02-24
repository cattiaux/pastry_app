import pytest
from rest_framework import status
from pastry_app.models import Store
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import normalize_case

model_name = "stores" 

# Création
# test_create_store → Vérifie qu'on peut créer un magasin avec des données valides.
# test_create_duplicate_store → Vérifie qu'on ne peut pas créer deux magasins avec les mêmes store_name, city et zip_code.

# Lecture
# test_get_store → Vérifie qu'on peut récupérer un magasin existant via GET /stores/{id}/.
# test_get_store_list → Vérifie qu'on peut récupérer la liste des magasins via GET /stores/.
# test_get_nonexistent_store → Vérifie qu'un GET sur un magasin inexistant retourne une erreur 404.

# Mise à jour
# test_update_store_field → Vérifie qu'on peut modifier uniquement un field spécifique via PATCH /stores/{id}/.

# Suppression
# test_delete_store → Vérifie qu'on peut supprimer un magasin existant via DELETE /stores/{id}/.
# test_delete_nonexistent_store → Vérifie qu'une tentative de suppression d'un magasin inexistant retourne 404.

# Fixture de création d'un magasin
@pytest.fixture
def setup_store(db):
    """Crée un magasin par défaut pour les tests."""
    return Store.objects.create(store_name="Carrefour", city="Roubaix", zip_code="59100")

# Création
@pytest.mark.django_db
def test_create_store(api_client, base_url):
    """Vérifie qu'on peut créer un magasin avec des données valides."""
    url = base_url(model_name)
    store_data = {"store_name": "Auchan", "city": "Lyon", "zip_code": "69001"}
    
    response = api_client.post(url, store_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["store_name"] == normalize_case("Auchan")

@pytest.mark.django_db
def test_create_duplicate_store(api_client, base_url, setup_store):
    """Vérifie qu'on ne peut pas créer deux magasins avec les mêmes `store_name`, `city` et `zip_code`."""
    url = base_url(model_name)
    store_data = {"store_name": setup_store.store_name, "city": setup_store.city, "zip_code": setup_store.zip_code}

    response = api_client.post(url, store_data, format="json")  # Deuxième tentative
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # Vérifier que le message d'erreur apparaît sous la bonne clé
    response_data = response.json()
    assert "error" in response_data  # Vérifie que l'erreur est bien présente
    assert response_data["error"] == "Ce magasin existe déjà."

# Lecture
@pytest.mark.django_db
def test_get_store(api_client, base_url, setup_store):
    """Vérifie qu'on peut récupérer un magasin existant via `GET /stores/{id}/`."""
    url = f"{base_url(model_name)}{setup_store.id}/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["store_name"] == setup_store.store_name

@pytest.mark.parametrize("additional_stores", [
    [{"store_name": "Monoprix", "city": "Lyon", "zip_code": "69001"},
     {"store_name": "Carrefour", "zip_code": "75001"}, # Sans `city`
     {"store_name": "Intermarché", "city": "Toulouse"}]  # Sans `zip_code`
])
@pytest.mark.django_db
def test_get_store_list(api_client, base_url, setup_store, additional_stores):
    """Vérifie qu'on peut récupérer la liste des magasins via `GET /stores/`."""
    url = base_url(model_name)
    # Création des magasins additionnels
    for store_data in additional_stores:
        Store.objects.create(**store_data)

    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Vérification que chaque magasin attendu est bien retourné
    all_stores = additional_stores + [{"store_name": setup_store.store_name, "city": setup_store.city, "zip_code": setup_store.zip_code}]
    for store_data in all_stores:
        assert any(s["store_name"] == normalize_case(store_data["store_name"]) for s in data)

@pytest.mark.django_db
def test_get_nonexistent_store(api_client, base_url):
    """Vérifie qu'un `GET` sur un magasin inexistant retourne une erreur `404`."""
    url = f"{base_url(model_name)}999999/"  # ID inexistant
    response = api_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

# Mise à jour
@pytest.mark.parametrize("field_name, new_value", [
    ("store_name", "Super U"),
    ("city", "Marseille"),
    ("zip_code", "75001"),
])
@pytest.mark.django_db
def test_update_store_field(api_client, base_url, setup_store, field_name, new_value):
    """Vérifie qu'on peut modifier individuellement `store_name`, `city` ou `zip_code` via PATCH /stores/{id}/."""
    url = f"{base_url(model_name)}{setup_store.id}/"
    updated_data = {field_name: new_value}

    response = api_client.patch(url, updated_data, format="json")
    print("Réponse API :", response.json()) 
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[field_name] == normalize_case(new_value)

# Suppression
@pytest.mark.django_db
def test_delete_store(api_client, base_url, setup_store):
    """Vérifie qu'on peut supprimer un magasin existant via `DELETE /stores/{id}/`."""
    url = f"{base_url(model_name)}{setup_store.id}/"
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.django_db
def test_delete_nonexistent_store(api_client, base_url):
    """Vérifie qu'une tentative de suppression d'un magasin inexistant retourne `404`."""
    url = f"{base_url(model_name)}999999/"  # ID inexistant
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND