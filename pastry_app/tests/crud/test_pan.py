import pytest
from rest_framework import status
from django.contrib.auth import get_user_model
from pastry_app.models import Pan
from pastry_app.tests.base_api_test import api_client, base_url

model_name = "pans"

pytestmark = pytest.mark.django_db
User = get_user_model()

@pytest.fixture
def user():
    return User.objects.create_user(username="user1", password="testpass123")

@pytest.fixture
def pan(user):
    """Crée un moule personnalisé (CUSTOM)"""
    return Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="test pan", pan_brand="debuyer", units_in_mold=3, user=user)

def test_create_pan_api(api_client, base_url):
    """Vérifie qu'on peut créer un `Pan` via l'API"""
    data = {"pan_type": "CUSTOM", "volume_raw": 1000, "unit": "cm3", "pan_name": "moule test", "pan_brand": "silikomart"}
    response = api_client.post(base_url(model_name), data=data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["pan_name"] == "moule test"

def test_get_pan_detail_api(api_client, base_url, pan):
    """Vérifie qu'on peut récupérer un `Pan` via l'API"""
    pan.visibility = "public"
    pan.save()
    response = api_client.get(base_url(model_name) + f"{pan.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == pan.id
    assert response.json()["pan_type"] == "CUSTOM"

def test_list_pans_api(api_client, base_url, pan):
    """Vérifie qu'on peut lister les `Pan`"""
    pan.visibility = "public"
    pan.save()
    another = Pan.objects.create(pan_type="CUSTOM", volume_raw=800, unit="cm3", pan_name="autre pan", visibility="public")
    response = api_client.get(base_url(model_name))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) >= 2

def test_patch_update_pan_api(api_client, base_url, pan, user):
    """Vérifie qu'on peut modifier un `Pan`"""
    api_client.force_authenticate(user=user)
    update_data = {"pan_brand": "matfer"}
    url = base_url(model_name) + f"{pan.id}/"
    response = api_client.patch(url, data=update_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["pan_brand"] == "matfer"

def test_put_update_pan_api(api_client, base_url, pan, user):
    """Vérifie qu'on peut remplacer un Pan via PUT"""
    api_client.force_authenticate(user=user)
    url = base_url(model_name) + f"{pan.id}/"
    new_data = {"pan_type": "CUSTOM", "volume_raw": 1500, "unit": "cm3", "pan_name": "moule mis à jour", "number_of_pans": 4}
    response = api_client.put(url, data=new_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["volume_raw"] == 1500
    assert response.json()["pan_name"] == "moule mis à jour"

def test_delete_pan_api(api_client, base_url, pan, user):
    """Vérifie qu'on peut supprimer un `Pan` via l'API"""
    api_client.force_authenticate(user=user)
    response = api_client.delete(base_url(model_name) + f"{pan.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Pan.objects.filter(id=pan.id).exists()

def test_get_nonexistent_pan(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 quand le Pan n'existe pas"""
    response = api_client.get(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_nonexistent_pan(api_client, base_url):
    """Vérifie qu'on obtient une erreur 404 à la suppression d’un Pan inexistant"""
    response = api_client.delete(base_url(model_name) + "9999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
