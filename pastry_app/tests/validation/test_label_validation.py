from pastry_app.models import Label
from ..base_api_test import BaseAPITest
from rest_framework import status

class LabelValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle Label"""
    model = Label
    model_name = "label"

    def test_create_label_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un Label sans `label_name`"""
        response = self.create_object({})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label_name", response.json())

    def test_create_duplicate_label(self):
        """ Vérifie qu'on ne peut PAS créer deux Labels avec le même `label_name`"""
        Label.objects.create(label_name="Vegan")
        response = self.create_object({"label_name": "Vegan"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label_name", response.json())

    def test_update_label_to_duplicate(self):
        """ Vérifie qu'on ne peut PAS modifier un Label pour lui donner un `label_name` déjà existant"""
        label2 = Label.objects.create(label_name="Sans Gluten")
        response = self.update_object(label2.id, {"label_name": "Vegan"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("label_name", response.json())

    def test_get_nonexistent_label(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un Label qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_label(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un Label qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
