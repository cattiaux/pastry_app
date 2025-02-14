from pastry_app.models import RoundPan
from ..base_api_test import BaseAPITest
from rest_framework import status

class RoundPanAPITest(BaseAPITest):
    """Test CRUD sur le modèle RoundPan"""
    model = RoundPan
    model_name = "roundpan"

    def setUp(self):
        """Création d’un moule rond pour les tests"""
        super().setUp()
        self.round_pan = RoundPan.objects.create(pan_name="Moule rond 20cm", diameter=20)

    def test_create_round_pan(self):
        """ Test de création d’un moule rond"""
        response = self.create_object({
            "pan_name": "Moule rond 25cm",
            "diameter": 25
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RoundPan.objects.filter(diameter=25).exists())

    def test_get_round_pan(self):
        """ Test de récupération d’un moule rond"""
        response = self.get_object(self.round_pan.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("pan_name"), "Moule rond 20cm")

    def test_update_round_pan(self):
        """ Test de mise à jour d’un moule rond"""
        response = self.update_object(self.round_pan.id, {
            "pan_name": "Moule rond 30cm",
            "diameter": 30
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.round_pan.refresh_from_db()
        self.assertEqual(self.round_pan.diameter, 30)

    def test_delete_round_pan(self):
        """ Test de suppression d’un moule rond"""
        response = self.delete_object(self.round_pan.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RoundPan.objects.filter(id=self.round_pan.id).exists())
