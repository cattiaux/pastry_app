from django.test import TestCase
from pastry_app.models import CustomPan
from pastry_app.tests.utils import normalize_case

class CustomPanModelTest(TestCase):
    """Tests unitaires du modèle CustomPan"""

    def setUp(self):
        """Création d’un moule personnalisé pour tester le modèle"""
        self.custom_pan = CustomPan.objects.create(pan_name="Moule personnalisé", volume=500)

    def test_custom_pan_creation(self):
        """ Vérifie que l'on peut créer un objet CustomPan"""
        self.assertIsInstance(self.custom_pan, CustomPan)
        self.assertEqual(self.custom_pan.volume, 500)

    def test_custom_pan_str_method(self):
        """ Vérifie que `__str__()` retourne bien `pan_name`"""
        self.assertEqual(str(self.custom_pan), normalize_case("Moule personnalisé"))

    def test_custom_pan_volume_positive(self):
        """ Vérifie que `volume` doit être strictement positif"""
        with self.assertRaises(Exception):
            CustomPan.objects.create(pan_name="Moule invalide", volume=-100)

    def test_custom_pan_update(self):
        """ Vérifie que l'on peut modifier un CustomPan"""
        self.custom_pan.volume = 750
        self.custom_pan.save()
        self.custom_pan.refresh_from_db()
        self.assertEqual(self.custom_pan.volume, 750)
