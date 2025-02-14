from pastry_app.models import CustomPan
from ..base_api_test import BaseAPITest
from rest_framework import status

class CustomPanAPITest(BaseAPITest):
    """Test CRUD sur le modèle CustomPan"""
    model = CustomPan
    model_name = "custompan"

    def setUp(self):
        """Création d’un moule personnalisé pour les tests"""
        super().setUp()
        self.custom_pan = CustomPan.objects.create(pan_name="Moule personnalisé", volume=500)

    def test_create_custom_pan(self):
        """ Test de création d’un moule personnalisé"""
        response = self.create_object({
            "pan_name": "Moule spécial",
            "volume": 750
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomPan.objects.filter(volume=750).exists())

    def test_get_custom_pan(self):
        """ Test de récupération d’un moule personnalisé"""
        response = self.get_object(self.custom_pan.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("pan_name"), "Moule personnalisé")

    def test_update_custom_pan(self):
        """ Test de mise à jour d’un moule personnalisé"""
        response = self.update_object(self.custom_pan.id, {
            "pan_name": "Moule haute capacité",
            "volume": 1000
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.custom_pan.refresh_from_db()
        self.assertEqual(self.custom_pan.volume, 1000)

    def test_delete_custom_pan(self):
        """ Test de suppression d’un moule personnalisé"""
        response = self.delete_object(self.custom_pan.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomPan.objects.filter(id=self.custom_pan.id).exists())
