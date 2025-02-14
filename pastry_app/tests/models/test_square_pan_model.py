from django.test import TestCase
from pastry_app.models import SquarePan
from pastry_app.tests.utils import normalize_case

class SquarePanModelTest(TestCase):
    """Tests unitaires du modèle SquarePan"""

    def setUp(self):
        """Création d’un moule rectangulaire pour tester le modèle"""
        self.square_pan = SquarePan.objects.create(
            pan_name="Moule rectangulaire 20x15cm",
            width=20,
            length=15,
            height=5
        )

    def test_square_pan_creation(self):
        """ Vérifie que l'on peut créer un objet SquarePan"""
        self.assertIsInstance(self.square_pan, SquarePan)
        self.assertEqual(self.square_pan.width, 20)
        self.assertEqual(self.square_pan.length, 15)
        self.assertEqual(self.square_pan.height, 5)

    def test_square_pan_str_method(self):
        """ Vérifie que `__str__()` retourne bien `pan_name`"""
        self.assertEqual(str(self.square_pan), "Moule rectangulaire 20x15cm")

    def test_square_pan_dimensions_positive(self):
        """ Vérifie que `width`, `length` et `height` doivent être strictement positifs"""
        with self.assertRaises(Exception):
            SquarePan.objects.create(pan_name="Moule invalide", width=-5, length=10, height=5)

        with self.assertRaises(Exception):
            SquarePan.objects.create(pan_name="Moule invalide", width=5, length=-10, height=5)

        with self.assertRaises(Exception):
            SquarePan.objects.create(pan_name="Moule invalide", width=5, length=10, height=-5)

    def test_square_pan_update(self):
        """ Vérifie que l'on peut modifier un SquarePan"""
        self.square_pan.width = 25
        self.square_pan.length = 18
        self.square_pan.save()
        self.square_pan.refresh_from_db()
        self.assertEqual(self.square_pan.width, 25)
        self.assertEqual(self.square_pan.length, 18)

    def test_square_pan_deletion(self):
        """ Vérifie que l'on peut supprimer un SquarePan"""
        pan_id = self.square_pan.id
        self.square_pan.delete()
        self.assertFalse(SquarePan.objects.filter(id=pan_id).exists())
