from pastry_app.models import Label
from ..base_api_test import BaseAPITest
from rest_framework import status

class LabelAPITest(BaseAPITest):
    """Test CRUD sur le modèle Label"""
    model = Label
    model_name = "label"

    def setUp(self):
        """Création d’un label pour les tests"""
        super().setUp()
        self.label = Label.objects.create(label_name="Vegan")

    def test_create_label(self):
        """ Test de création d’un label"""
        response = self.create_object({"label_name": "Sans Gluten"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Label.objects.filter(label_name="Sans Gluten").exists())

    def test_get_label(self):
        """ Test de récupération d’un label"""
        response = self.get_object(self.label.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("label_name"), "Vegan")

    def test_update_label(self):
        """ Test de mise à jour d’un label"""
        response = self.update_object(self.label.id, {"label_name": "Végétarien"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.label.refresh_from_db()
        self.assertEqual(self.label.label_name, "Végétarien")

    def test_delete_label(self):
        """ Test de suppression d’un label"""
        response = self.delete_object(self.label.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Label.objects.filter(id=self.label.id).exists())
