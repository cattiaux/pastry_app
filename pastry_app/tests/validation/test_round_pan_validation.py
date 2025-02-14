from enchante.models import RoundPan
from ..base_api_test import BaseAPITest
from rest_framework import status

class RoundPanValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle RoundPan"""
    model = RoundPan
    model_name = "roundpan"

    def test_create_round_pan_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un RoundPan sans `pan_name`"""
        response = self.create_object({"diameter": 20})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pan_name", response.json())

    def test_create_round_pan_without_diameter(self):
        """ Vérifie qu'on ne peut PAS créer un RoundPan sans `diameter`"""
        response = self.create_object({"pan_name": "Moule rond sans diamètre"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("diameter", response.json())

    def test_create_round_pan_with_negative_diameter(self):
        """ Vérifie qu'on ne peut PAS créer un RoundPan avec un `diameter` négatif"""
        response = self.create_object({"pan_name": "Moule invalide", "diameter": -20})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("diameter", response.json())
