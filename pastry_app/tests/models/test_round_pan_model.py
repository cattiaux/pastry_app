from django.test import TestCase
from pastry_app.models import RoundPan
from pastry_app.tests.utils import normalize_case

class RoundPanModelTest(TestCase):
    """Tests unitaires du modèle RoundPan"""

    def setUp(self):
        """Création d’un moule rond pour tester le modèle"""
        self.round_pan = RoundPan.objects.create(pan_name="Moule rond 20cm", diameter=20)

    def test_round_pan_creation(self):
        """ Vérifie que l'on peut créer un objet RoundPan"""
        self.assertIsInstance(self.round_pan, RoundPan)
        self.assertEqual(self.round_pan.diameter, 20)

    def test_round_pan_str_method(self):
        """ Vérifie que `__str__()` retourne bien `pan_name`"""
        self.assertEqual(str(self.round_pan), "Moule rond 20cm")

    def test_round_pan_diameter_positive(self):
        """ Vérifie que `diameter` doit être strictement positif"""
        with self.assertRaises(Exception):
            RoundPan.objects.create(pan_name="Moule invalide", diameter=-10)

    def test_round_pan_update(self):
        """ Vérifie que l'on peut modifier un RoundPan"""
        self.round_pan.diameter = 25
        self.round_pan.save()
        self.round_pan.refresh_from_db()
        self.assertEqual(self.round_pan.diameter, 25)
