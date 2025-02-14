from pastry_app.models import Pan
from ..base_api_test import BaseAPITest
from rest_framework import status

class PanValidationTest(BaseAPITest):
    """Tests de validation et de gestion des erreurs pour le modèle Pan"""
    model = Pan
    model_name = "pan"

    def setUp(self):
        """Préparation : création d’un moule pour tester les doublons"""
        super().setUp()
        self.pan = Pan.objects.create(pan_name="Moule rond 20cm", pan_type="ROUND")

    def test_create_pan_without_name(self):
        """ Vérifie qu'on ne peut PAS créer un moule sans `pan_name`"""
        response = self.create_object({"pan_type": "SQUARE"})  # Pas de `pan_name`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("pan_name", response.json())  # Vérifie que l'erreur mentionne `pan_name`

    def test_create_pan_without_type(self):
        """ Vérifie qu'on ne peut PAS créer un moule sans `pan_type`"""
        response = self.create_object({"pan_name": "Moule carré 15cm"})  # Pas de `pan_type`
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("pan_type", response.json())  # Vérifie que l'erreur mentionne `pan_type`

    def test_create_duplicate_pan(self):
        """ Vérifie qu'on ne peut PAS créer deux moules avec le même `pan_name`"""
        response = self.create_object({"pan_name": "Moule rond 20cm", "pan_type": "ROUND"})  # Déjà existant
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("pan_name", response.json())  # Vérifie que l'erreur mentionne bien `pan_name`

    def test_update_pan_to_duplicate(self):
        """ Vérifie qu'on ne peut PAS modifier un moule pour lui donner un `pan_name` déjà existant"""
        pan2 = Pan.objects.create(pan_name="Moule carré 15cm", pan_type="SQUARE")
        response = self.update_object(pan2.id, {"pan_name": "Moule rond 20cm", "pan_type": "ROUND"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Doit renvoyer une erreur 400
        self.assertIn("pan_name", response.json())  # Vérifie que l'erreur mentionne bien `pan_name`

    def test_get_nonexistent_pan(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de récupérer un moule qui n'existe pas"""
        response = self.get_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404

    def test_delete_nonexistent_pan(self):
        """ Vérifie qu'on obtient une erreur 404 quand on essaie de supprimer un moule qui n'existe pas"""
        response = self.delete_object(9999)  # ID inexistant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # Doit renvoyer une erreur 404
