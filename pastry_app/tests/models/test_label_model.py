from django.test import TestCase
from pastry_app.models import Label
from pastry_app.tests.utils import normalize_case
from django.core.exceptions import ValidationError

class LabelModelTest(TestCase):
    """Tests unitaires du modèle Label"""

    def setUp(self):
        """Création d’un label pour tester le modèle"""
        self.label = Label.objects.create(label_name="Vegan")

    def test_label_creation(self):
        """ Vérifie que l'on peut créer un objet Label"""
        self.assertIsInstance(self.label, Label)
        self.assertEqual(self.label.label_name, normalize_case("Vegan"))

    def test_label_str_method(self):
        """ Vérifie que `__str__()` retourne bien le `label_name`"""
        self.assertEqual(str(self.label), normalize_case("Vegan"))

    def test_label_update(self):
        """ Vérifie que l'on peut modifier un Label"""
        self.label.label_name = "Sans Gluten"
        self.label.save()
        self.label.refresh_from_db()
        self.assertEqual(self.label.label_name, normalize_case("Sans Gluten"))

    def test_label_deletion(self):
        """ Vérifie que l'on peut supprimer un Label"""
        label_id = self.label.id
        self.label.delete()
        self.assertFalse(Label.objects.filter(id=label_id).exists())

    def test_label_name_cannot_be_empty(self):
        """ Vérifie qu'on ne peut pas créer un label avec un nom vide."""
        with self.assertRaises(ValidationError):
            label = Label(label_name="")
            label.full_clean()

    def test_label_name_cannot_be_too_short(self):
        """ Vérifie qu'on ne peut pas créer un label avec un nom trop court."""
        with self.assertRaises(ValidationError):
            label = Label(label_name="A")
            label.full_clean()

    def test_label_name_cannot_be_numeric(self):
        """ Vérifie qu'un label ne peut pas être uniquement composé de chiffres."""
        with self.assertRaises(ValidationError):
            label = Label(label_name="12345")
            label.full_clean()

    def test_label_name_is_normalized(self):
        """ Vérifie que le `label_name` est bien normalisé (minuscule, sans espaces)."""
        label = Label.objects.create(label_name="  Bio  ")
        self.assertEqual(label.label_name, "bio")
