from django.test import TestCase
from pastry_app.models import Pan
from pastry_app.tests.utils import normalize_case
from django.core.exceptions import ValidationError

class PanModelTest(TestCase):
    """Tests unitaires du modèle Pan"""

    def setUp(self):
        """Création d’un moule pour tester le modèle"""
        self.pan = Pan.objects.create(pan_name="Moule rond 20cm", pan_type="ROUND")

    def test_pan_creation(self):
        """🔍 Vérifie que l'on peut créer un objet Pan"""
        self.assertIsInstance(self.pan, Pan)
        self.assertEqual(self.pan.pan_name, normalize_case("Moule rond 20cm"))
        self.assertEqual(self.pan.pan_type, "ROUND")

    def test_pan_str_method(self):
        """ Vérifie que `__str__()` retourne bien le `pan_name`"""
        self.assertEqual(str(self.pan), normalize_case("Moule rond 20cm"))

    def test_pan_update(self):
        """ Vérifie que l'on peut modifier un moule"""
        self.pan.pan_name = "Moule carré 15cm"
        self.pan.save()
        self.pan.refresh_from_db()
        self.assertEqual(self.pan.pan_name, normalize_case("Moule carré 15cm"))

    def test_pan_deletion(self):
        """ Vérifie que l'on peut supprimer un moule"""
        pan_id = self.pan.id
        self.pan.delete()
        self.assertFalse(Pan.objects.filter(id=pan_id).exists())

    def test_pan_name_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer un moule sans `pan_name`"""
        with self.assertRaises(Exception):  # Django va lever une exception
            Pan.objects.create(pan_name=None, pan_type="ROUND")

    def test_pan_type_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer un moule sans `pan_type`"""
        with self.assertRaises(Exception):
            Pan.objects.create(pan_name="Moule spécial", pan_type=None)

    def test_pan_name_must_be_unique(self):
        """ Vérifie qu'on ne peut pas créer deux moules avec le même `pan_name`"""
        with self.assertRaises(ValidationError):
            duplicate_pan = Pan(pan_name="Moule rond 20cm", pan_type="square")
            duplicate_pan.full_clean() 

    def test_invalid_pan_type(self):
        """ Vérifie qu'on ne peut pas attribuer une valeur invalide à `pan_type`"""
        with self.assertRaises(Exception):
            Pan.objects.create(pan_name="Moule inconnu", pan_type="TRIANGLE")  # Supposons que "TRIANGLE" est invalide
