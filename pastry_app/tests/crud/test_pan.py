import pytest
from rest_framework import status
from pastry_app.models import Pan
from pastry_app.tests.base_api_test import api_client, base_url

model_name = "pans"

@pytest.fixture
def pan():
    """Crée un moule personnalisé (CUSTOM)"""
    return Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="test pan", pan_brand="debuyer")

@pytest.mark.django_db
def test_create_pan_api(api_client, base_url):
    """Vérifie qu'on peut créer un `Pan` via l'API"""
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3", "pan_name": "moule test", "pan_brand": "silikomart"}
    response = api_client.post(base_url(model_name), data=data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["pan_name"] == "moule test"

@pytest.mark.django_db
def test_get_pan_detail_api(api_client, base_url, pan):
    """Vérifie qu'on peut récupérer un `Pan` via l'API"""
    response = api_client.get(base_url(model_name) + f"{pan.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == pan.id
    assert response.json()["pan_type"] == "CUSTOM"

@pytest.mark.django_db
def test_list_pans_api(api_client, base_url, pan):
    """Vérifie qu'on peut lister les `Pan`"""
    another = Pan.objects.create(pan_type="CUSTOM", volume_raw=800, unit="cm3", pan_name="autre pan")
    response = api_client.get(base_url(model_name))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) >= 2

@pytest.mark.django_db
def test_patch_update_pan_api(api_client, base_url, pan):
    """Vérifie qu'on peut modifier un `Pan`"""
    update_data = {"pan_brand": "matfer"}
    url = base_url(model_name) + f"{pan.id}/"
    response = api_client.patch(url, data=update_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["pan_brand"] == "matfer"

@pytest.mark.django_db
def test_put_update_pan_api(api_client, base_url, pan):
    """Vérifie qu'on peut remplacer un Pan via PUT"""
    url = base_url(model_name) + f"{pan.id}/"
    new_data = {"pan_type": "CUSTOM", "volume_raw": 1500, "unit": "cm3", "pan_name": "moule mis à jour"}
    response = api_client.put(url, data=new_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["volume_raw"] == 1500
    assert response.json()["pan_name"] == "moule mis à jour"

@pytest.mark.django_db
def test_delete_pan_api(api_client, base_url, pan):
    """Vérifie qu'on peut supprimer un `Pan` via l'API"""
    response = api_client.delete(base_url(model_name) + f"{pan.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Pan.objects.filter(id=pan.id).exists()

@pytest.mark.django_db
def test_get_nonexistent_pan(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand le Pan n'existe pas"""
    response = api_client.get(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
def test_delete_nonexistent_pan(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 à la suppression d’un Pan inexistant"""
    response = api_client.delete(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
