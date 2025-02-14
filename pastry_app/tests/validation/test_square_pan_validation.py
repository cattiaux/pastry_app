from pastry_app.models import SquarePan
from ..base_api_test import BaseAPITest
from rest_framework import status

class SquarePanValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle SquarePan"""
    model = SquarePan
    model_name = "squarepan"

    def test_create_square_pan_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un SquarePan sans `pan_name`"""
        response = self.create_object({"width": 20, "length": 15, "height": 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pan_name", response.json())

    def test_create_square_pan_without_dimensions(self):
        """ Vérifie qu'on ne peut PAS créer un SquarePan sans `width`, `length` ou `height`"""
        response = self.create_object({"pan_name": "Moule sans dimensions"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("width", response.json())
        self.assertIn("length", response.json())
        self.assertIn("height", response.json())

    def test_create_square_pan_with_negative_dimensions(self):
        """ Vérifie qu'on ne peut PAS créer un SquarePan avec des dimensions négatives"""
        response = self.create_object({
            "pan_name": "Moule invalide",
            "width": -10,
            "length": 15,
            "height": 5
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("width", response.json())
