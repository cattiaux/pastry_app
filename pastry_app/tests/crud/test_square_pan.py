from pastry_app.models import SquarePan
from ..base_api_test import BaseAPITest
from rest_framework import status

class SquarePanAPITest(BaseAPITest):
    """Test CRUD sur le modèle SquarePan"""
    model = SquarePan
    model_name = "squarepan"

    def setUp(self):
        """Création d’un moule rectangulaire pour les tests"""
        super().setUp()
        self.square_pan = SquarePan.objects.create(
            pan_name="Moule rectangulaire 20x15cm", width=20, length=15, height=5
        )

    def test_create_square_pan(self):
        """ Test de création d’un moule rectangulaire"""
        response = self.create_object({
            "pan_name": "Moule rectangulaire 25x18cm",
            "width": 25,
            "length": 18,
            "height": 6
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SquarePan.objects.filter(width=25, length=18).exists())

    def test_get_square_pan(self):
        """ Test de récupération d’un moule rectangulaire"""
        response = self.get_object(self.square_pan.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("pan_name"), "Moule rectangulaire 20x15cm")

    def test_update_square_pan(self):
        """ Test de mise à jour d’un moule rectangulaire"""
        response = self.update_object(self.square_pan.id, {
            "pan_name": "Moule rectangulaire 30x20cm",
            "width": 30,
            "length": 20,
            "height": 7
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.square_pan.refresh_from_db()
        self.assertEqual(self.square_pan.width, 30)
        self.assertEqual(self.square_pan.length, 20)

    def test_delete_square_pan(self):
        """ Test de suppression d’un moule rectangulaire"""
        response = self.delete_object(self.square_pan.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SquarePan.objects.filter(id=self.square_pan.id).exists())
