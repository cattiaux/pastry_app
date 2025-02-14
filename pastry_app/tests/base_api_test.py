import pytest
from rest_framework.test import APIClient

@pytest.fixture()
def api_client():
    """ Client API pour effectuer les requêtes dans les tests.
        Configuration commune à tous les tests CRUD """
    return APIClient()

@pytest.fixture()
def base_url():
    """Fixture qui retourne une fonction pour générer l'URL de base d'un modèle"""
    def _base_url(model_name):
        return f"/api/{model_name}/"
    return _base_url

# # Fonction pour créer un objet via l'API
# def create_object(api_client, base_url, data):
#     """Créer un objet via l'API"""
#     return api_client.post(base_url, data, content_type="application/json")

# # Fonction pour récupérer un objet via l'API
# def get_object(api_client, base_url, obj_id):
#     """Récupérer un objet via l'API"""
#     return api_client.get(f"{base_url}{obj_id}/")

# Fonction pour mettre à jour un objet via l'API
def update_object(api_client, base_url, obj_id, data, partial=True):
    """Mettre à jour un objet via l'API (PATCH par défaut)"""
    method = api_client.patch if partial else api_client.put
    return method(f"{base_url}{obj_id}/", data, content_type="application/json")

# Fonction pour supprimer un objet via l'API
# def delete_object(api_client, base_url, obj_id):
#     """Supprimer un objet via l'API"""
#     return api_client.delete(f"{base_url}{obj_id}/")
