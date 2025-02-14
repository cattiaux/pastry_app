from pastry_app.models import Pan
from ..base_api_test import BaseAPITest
from rest_framework import status

class PanAPITest(BaseAPITest):
    """Test CRUD sur le modèle Pan"""
    model = Pan
    model_name = "pan"

    def setUp(self):
        """Création d’un moule pour les tests"""
        super().setUp()
        self.pan = Pan.objects.create(pan_name="Moule rond 20cm", pan_type="ROUND")

    def test_create_pan(self):
        """Test de création d’un moule"""
        response = self.create_object({"pan_name": "Moule carré 15cm", "pan_type": "SQUARE"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Pan.objects.filter(pan_name="Moule carré 15cm").exists())

    def test_get_pan(self):
        """Test de récupération d’un moule"""
        response = self.get_object(self.pan.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.assertEqual(response.json().get("pan_name"), "Moule rond 20cm")  
        self.assertEqual(response.json().get("pan_type"), "ROUND") 

    def test_update_pan(self):
        """Test de mise à jour d’un moule"""
        response = self.update_object(self.pan.id, {"pan_name": "Moule rond 25cm", "pan_type": "ROUND"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)  
        self.pan.refresh_from_db()
        self.assertEqual(self.pan.pan_name, "Moule rond 25cm")

    def test_delete_pan(self):
        """Test de suppression d’un moule"""
        response = self.delete_object(self.pan.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT) 
        self.assertFalse(Pan.objects.filter(id=self.pan.id).exists())
