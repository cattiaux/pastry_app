from pastry_app.models import CustomPan
from ..base_api_test import BaseAPITest
from rest_framework import status

class CustomPanValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle CustomPan"""
    model = CustomPan
    model_name = "custompan"

    def test_create_custom_pan_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un CustomPan sans `pan_name`"""
        response = self.create_object({"volume": 500})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pan_name", response.json())

    def test_create_custom_pan_without_volume(self):
        """ Vérifie qu'on ne peut PAS créer un CustomPan sans `volume`"""
        response = self.create_object({"pan_name": "Moule spécial"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("volume", response.json())

    def test_create_custom_pan_with_negative_volume(self):
        """ Vérifie qu'on ne peut PAS créer un CustomPan avec un `volume` négatif"""
        response = self.create_object({"pan_name": "Moule invalide", "volume": -500})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("volume", response.json())
