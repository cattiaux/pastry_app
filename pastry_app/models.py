from math import pi
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .utils_pure import normalize_case
from .constants import UNIT_CHOICES

User = get_user_model()

class BaseModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.name = self.name.lower() if self.name else None
        super().save(*args, **kwargs)

class Pan(models.Model):
    PAN_TYPE_CHOICES = [
        ('ROUND', 'Rond'),
        ('RECTANGLE', 'Rectangulaire'),
        ('CUSTOM', 'Silicone / Forme libre'),
    ]
    UNIT_CHOICES = [
        ('cm3', 'cm³'),
        ('L', 'Litres'),
    ]

    pan_name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    pan_type = models.CharField(max_length=20, choices=PAN_TYPE_CHOICES)
    pan_brand = models.CharField(max_length=100, blank=True, null=True)
    units_in_mold = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # Utilisateur
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pans", blank=True, null=True)  # null=True pour migrer en douceur
    guest_id = models.CharField(max_length=64, blank=True, null=True, db_index=True) 
    visibility = models.CharField(max_length=10, choices=[('private', 'Privée'), ('public', 'Publique')], default='private')
    is_default = models.BooleanField(default=False)

    # Dimensions pour ROUND
    diameter = models.FloatField(validators=[MinValueValidator(0.1)], blank=True, null=True)
    height = models.FloatField(validators=[MinValueValidator(0.1)], blank=True, null=True)

    # Dimensions pour RECTANGLE
    length = models.FloatField(validators=[MinValueValidator(0.1)], blank=True, null=True)
    width = models.FloatField(validators=[MinValueValidator(0.1)], blank=True, null=True)
    rect_height = models.FloatField(validators=[MinValueValidator(0.1)], blank=True, null=True)

    # Volume manuel pour les CUSTOM
    volume_raw = models.FloatField(validators=[MinValueValidator(1)], blank=True, null=True)
    is_total_volume = models.BooleanField(default=False, help_text="True si volume_raw est le volume total (toutes empreintes confondues), False si c'est le volume unitaire.")
    unit = models.CharField(max_length=4, choices=UNIT_CHOICES, blank=True, null=True)

    # Cache du volume (mis à jour à chaque save)
    volume_cm3_cache = models.FloatField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['pan_name', 'pan_type']
        constraints = [models.UniqueConstraint(fields=["pan_name"], name="unique_pan_name")]
    
    def __str__(self):
        return f"{self.pan_name or 'Moule'} ({self.pan_type})"

    @property
    def volume_cm3(self):
        """Retourne le volume en cm³ (converti si nécessaire). Hypothèse : clean() a déjà validé les champs nécessaires."""
        if self.pan_type == 'ROUND':
            radius = self.diameter / 2
            return pi * radius ** 2 * self.height
        elif self.pan_type == 'RECTANGLE':
            return self.length * self.width * self.rect_height
        elif self.pan_type == 'CUSTOM':
            volume = self.volume_raw * 1000 if self.unit == 'L' else self.volume_raw
            if not self.is_total_volume and self.units_in_mold:
                volume *= self.units_in_mold
            return volume
        return None

    def generate_default_name(self):
        """Génère un nom lisible basé sur les dimensions si aucun nom n'est fourni."""
        if self.pan_type == "ROUND":
            return f"Cercle {int(self.diameter)}x{int(self.height)}cm"
        elif self.pan_type == "RECTANGLE":
            return f"Rectangle {int(self.length)}x{int(self.width)}x{int(self.rect_height)}cm"
        elif self.pan_type == "CUSTOM":
            return f"Moule {int(self.volume_cm3)}cm³"
        return "Moule"

    def clean(self):
        """Validation métier avant sauvegarde."""
        if self.user and self.guest_id:
            raise ValidationError("Une recette ne peut pas avoir à la fois un user et un guest_id.")

        # Normalisation
        if self.pan_name:
            self.pan_name = normalize_case(self.pan_name)
        if self.pan_brand:
            self.pan_brand = normalize_case(self.pan_brand)

        # units_in_mold n'existe que pour les moules CUSTOM
        if self.pan_type != 'CUSTOM' and self.units_in_mold != 1:
            raise ValidationError("units_in_mold ne doit être différent de 1 que pour les moules CUSTOM.")
    
        # Si une seule unité dans le moule, alors c'est forcément le volume total
        if self.units_in_mold == 1:
            self.is_total_volume = True

        # Nettoyage des champs incohérents selon le type
        if self.pan_type == 'ROUND':
            self.length = None
            self.width = None
            self.rect_height = None
            self.volume_raw = None
            self.unit = None

        elif self.pan_type == 'RECTANGLE':
            self.diameter = None
            self.height = None
            self.volume_raw = None
            self.unit = None

        elif self.pan_type == 'CUSTOM':
            self.diameter = None
            self.height = None
            self.length = None
            self.width = None
            self.rect_height = None

        # Validations texte
        if self.pan_name and len(self.pan_name) < 2:
            raise ValidationError("Le nom du moule doit contenir au moins 2 caractères.")
        if self.pan_brand and len(self.pan_brand) < 2:
            raise ValidationError("Le nom de la marque doit contenir au moins 2 caractères.")

        # Validation métier selon pan_type
        if not self.pan_type:
            raise ValidationError("Le type de moule est requis.")

        # Champs obligatoires selon pan_type
        if self.pan_type == 'ROUND':
            if not self.diameter or not self.height:
                raise ValidationError("Un moule rond doit avoir un diamètre et une hauteur.")
            if any([self.length, self.width, self.rect_height, self.volume_raw]):
                raise ValidationError("Un moule rond ne doit pas contenir de dimensions rectangulaires ou de volume personnalisé.")

        elif self.pan_type == 'RECTANGLE':
            if not self.length or not self.width or not self.rect_height:
                raise ValidationError("Un moule rectangulaire doit avoir une longueur, une largeur et une hauteur.")
            if any([self.diameter, self.height, self.volume_raw]):
                raise ValidationError("Un moule rectangulaire ne doit pas contenir de dimensions rondes ou de volume personnalisé.")

        elif self.pan_type == 'CUSTOM':
            if not self.volume_raw:
                raise ValidationError("Un moule personnalisé doit avoir un volume saisi.")
            if not self.unit:
                raise ValidationError("L'unité du volume est requise pour les moules personnalisés.")
            if any([self.diameter, self.height, self.length, self.width, self.rect_height]):
                raise ValidationError("Un moule personnalisé ne doit pas contenir de dimensions rondes ou rectangulaires.")

        else:
            raise ValidationError(f"Type de moule inconnu : {self.pan_type}")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.pan_name:
            self.pan_name = normalize_case(self.generate_default_name())
        self.volume_cm3_cache = self.volume_cm3
        super().save(*args, **kwargs)

class Category(models.Model):
    """
    ⚠️ IMPORTANT ⚠️
    - Actuellement, `category_name` N'A PAS `unique=True` pour éviter les conflits en développement.
    - Une fois en production, AJOUTER `unique=True` sur `category_name`.
    """
    CATEGORY_CHOICES = [('ingredient', 'Ingrédient'), ('recipe', 'Recette'), ('both', 'Les deux'),]
    # Note : `unique=True` dans le field 'category_name' empêche les doublons en base, mais bloque l'API avant même qu'elle ne puisse gérer l'erreur.
    # Pour l'unicité avec pytest, enlève `unique=True` et gère l'unicité dans `serializers.py`.
    category_name = models.CharField(max_length=200,  verbose_name="category_name")#, unique=True) #unique=True à activer en production
    category_type = models.CharField(max_length=10, choices=CATEGORY_CHOICES, blank=False, null=False)
    parent_category = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subcategories")

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.category_name} [{self.category_type}]"

    def clean(self):
        """ Vérifie les règles métier lors de la création et de l’update. """
        # Normalisation du `category_name`
        self.category_name = normalize_case(self.category_name)

        # Normalisation du `parent_category`
        if self.parent_category:
            normalized_parent = normalize_case(self.parent_category.category_name)
            self.parent_category = Category.objects.filter(category_name__iexact=normalized_parent).first()

        # Normalisation du `category_type`
        if self.category_type:
            self.category_type = normalize_case(self.category_type)
            if self.category_type not in dict(self.CATEGORY_CHOICES):
                raise ValidationError(f"`category_type` doit être l'une des valeurs suivantes: {', '.join(dict(self.CATEGORY_CHOICES).keys())}.")

        # Vérifier que `category_type` est valide
        if not self.category_type:
            raise ValidationError("Le champ `category_type` est obligatoire pour une nouvelle catégorie.")
        elif self.category_type not in dict(self.CATEGORY_CHOICES):
            raise ValidationError(f"`category_type` doit être l'une des valeurs suivantes: {', '.join(dict(self.CATEGORY_CHOICES).keys())}.")

        # Vérification type parent
        if self.parent_category:
            parent_type = self.parent_category.category_type
            this_type = self.category_type
            # Catégorie BOTH : parent obligatoirement BOTH ou None
            if this_type == "both" and parent_type != "both":
                raise ValidationError("Une catégorie 'both' ne peut avoir qu'une catégorie parente 'both' ou aucune.")
            # Catégorie INGREDIENT ou RECIPE : parent = même type ou BOTH ou None
            if this_type in ("ingredient", "recipe") and parent_type not in (this_type, "both"):
                raise ValidationError(f"Une catégorie '{this_type}' ne peut avoir pour parent qu'une catégorie '{this_type}' ou 'both', jamais '{parent_type}'.")

        # Vérifier qu'on ne met pas à jour un `category_name` existant
        existing_category = Category.objects.exclude(id=self.id).filter(category_name__iexact=self.category_name).exists()
        if existing_category:
            raise ValidationError("Une catégorie avec ce nom existe déjà.")

    def save(self, *args, **kwargs):
        """ Validation avant sauvegarde : nettoyage, validation. """
        self.full_clean()

        # Empêche la création d'une catégorie par un utilisateur non-admin
        request = kwargs.pop("request", None)
        if request and not request.user.is_staff:
            raise ValidationError("Seuls les administrateurs peuvent créer ou modifier des catégories.")

        if not self.category_type:
            raise ValidationError("Le type de catégorie est obligatoire.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Empêche la suppression d'une catégorie par un utilisateur non-admin."""
        request = kwargs.pop("request", None)
        if request and not request.user.is_staff:
            raise ValidationError("Seuls les administrateurs peuvent supprimer des catégories.")

        super().delete(*args, **kwargs)

class Label(models.Model):
    """
    ⚠️ IMPORTANT ⚠️
    - Actuellement, `label_name` N'A PAS `unique=True` pour éviter les conflits en développement.
    - Une fois en production, AJOUTER `unique=True` sur `label_name`.
    """
    LABEL_CHOICES = [
        ('ingredient', 'Ingrédient'),
        ('recipe', 'Recette'),
        ('both', 'Les deux'),
    ]
    # Note : `unique=True` dans le field 'label_name' empêche les doublons en base, mais bloque l'API avant même qu'elle ne puisse gérer l'erreur.
    # Pour l'unicité avec pytest, enlève `unique=True` et gère l'unicité dans `serializers.py`.
    label_name = models.CharField(max_length=200,  verbose_name="label_name", unique=True) #unique=True à activer en production
    label_type = models.CharField(max_length=10, choices=LABEL_CHOICES, default='both')

    def __str__(self):
        return f"{self.label_name} [{self.label_type}]"

    def clean(self):
        """ Vérifie les règles métier lors de la création et de l’update. """
        # Normalisation du `label_name`
        self.label_name = normalize_case(self.label_name)

        # Normalisation du `label_type`
        if self.label_type:
            self.label_type = normalize_case(self.label_type)
            if self.label_type not in dict(self.LABEL_CHOICES):
                raise ValidationError(f"`label_type` doit être l'une des valeurs suivantes: {', '.join(dict(self.LABEL_CHOICES).keys())}.")

        # Vérifier que `label_type` est valide
        if not self.label_type:
            raise ValidationError("Le champ `label_type` est obligatoire pour un nouveau label.")
        elif self.label_type not in dict(self.LABEL_CHOICES):
            raise ValidationError(f"`label_type` doit être l'une des valeurs suivantes: {', '.join(dict(self.LABEL_CHOICES).keys())}.")

        # Vérifier qu'on ne met pas à jour un `label_name` existant
        existing_label = Label.objects.exclude(id=self.id).filter(label_name__iexact=self.label_name).exists()
        if existing_label:
            raise ValidationError("Un label avec ce nom existe déjà.")

    def save(self, *args, **kwargs):
        """ Validation avant sauvegarde : nettoyage, validation. """
        self.full_clean()

        # Empêche la création d'un label par un utilisateur non-admin
        request = kwargs.pop("request", None)
        if request and not request.user.is_staff:
            raise ValidationError("Seuls les administrateurs peuvent créer ou modifier des labels.")

        if not self.label_type:
            raise ValidationError("Le type de label est obligatoire.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Empêche la suppression d'un label par un utilisateur non-admin."""
        request = kwargs.pop("request", None)
        if request and not request.user.is_staff:
            raise ValidationError("Seuls les administrateurs peuvent supprimer des labels.")

        super().delete(*args, **kwargs)

class IngredientCategory(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

class RecipeCategory(models.Model):
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

    class Meta:
        verbose_name = "recipe category"
        verbose_name_plural = "categories"

class IngredientLabel(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE)
    label = models.ForeignKey("Label", on_delete=models.PROTECT)  # Empêche la suppression d'un label utilisé

class RecipeLabel(models.Model):
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    label = models.ForeignKey("Label", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

    class Meta:
        verbose_name = "recipe labels"
        verbose_name_plural = "labels"

class Recipe(models.Model):
    RECIPE_TYPE_CHOICES = [("BASE", "Recette de base"), ("VARIATION", "Variante"),]

    # Informations principales
    parent_recipe = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="versions")
    recipe_name = models.CharField(max_length=200)
    chef_name = models.CharField(max_length=100, null=True, blank=True)
    context_name = models.CharField(max_length=100, null=True, blank=True, default="")
    source = models.CharField(max_length=255, null=True, blank=True)
    recipe_type = models.CharField(max_length=20, choices=RECIPE_TYPE_CHOICES, default="BASE")
    servings_min = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    servings_max = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    pan_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], 
                                               help_text="Nombre d'exemplaires de ce moule utilisés dans cette recette (ex: 6 cercles individuels).")
    total_recipe_quantity = models.FloatField(null=True, blank=True, 
                                              help_text="Quantité totale en g produite par cette recette (ex: 1200 pour 1200g de crème pâtissière)")

    # Relations
    categories = models.ManyToManyField(Category, through="RecipeCategory", related_name="recipes") 
    labels = models.ManyToManyField(Label, through="RecipeLabel", related_name="recipes")
    ingredients = models.ManyToManyField("Ingredient", through="RecipeIngredient", related_name="recipes")
    pan = models.ForeignKey(Pan, null=True, blank=True, on_delete=models.SET_NULL)

    # Contenu
    description = models.TextField(blank=True, null=True)
    trick = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="recipes/", null=True, blank=True)
    adaptation_note = models.CharField(max_length=255, blank=True, null=True)
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Utilisateur
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipes", blank=True, null=True)  # null=True pour migrer en douceur
    guest_id = models.CharField(max_length=64, blank=True, null=True, db_index=True) 
    visibility = models.CharField(max_length=10, choices=[('private', 'Privée'), ('public', 'Publique')], default='private')
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['recipe_name', 'chef_name']
        constraints = [
            models.UniqueConstraint(fields=["recipe_name", "chef_name", "context_name"], name="unique_recipe_per_context"),
            ]

    def __str__(self):
        base = f"{self.recipe_name} ({self.chef_name})"
        if self.context_name:
            return f"{base} - {self.context_name}"
        return base

    @property
    def servings_avg(self):
        if self.servings_min and self.servings_max:
            return (self.servings_min + self.servings_max) / 2
        if self.servings_min:
            return self.servings_min
        if self.servings_max:
            return self.servings_max
        return None

    def compute_and_set_total_quantity(self, force=False, user=None, guest_id=None, save=True):
        """
        Calcule la quantité totale produite par la recette en grammes,
        en convertissant chaque ingrédient selon son unité (avec fallback sur la table de correspondance).
        Si user/guest_id sont passés, privilégie leurs mappings.
        - Ne remplit le champ que s'il est vide ou si force=True.
        - Retourne la quantité calculée.
        - Par défaut, maj le champ et save, sauf si save=False.
        """
        if self.total_recipe_quantity is None or force:
            total = 0
            errors = []
            for rec_ing in self.recipe_ingredients.all():
                qte = rec_ing.quantity
                unit = rec_ing.unit
                if unit == "g":
                    total += qte
                elif unit == "mg":
                    total += qte / 1000
                elif unit == "kg":
                    total += qte * 1000
                else:
                    # Cherche correspondance unité→g (priorité user/guest puis globale)
                    ref = IngredientUnitReference.objects.filter(ingredient=rec_ing.ingredient, unit=unit, 
                                                                is_hidden=False, user=user, guest_id=guest_id
                    ).first() or IngredientUnitReference.objects.filter(ingredient=rec_ing.ingredient, unit=unit, 
                                                                        is_hidden=False, user__isnull=True, guest_id__isnull=True).first()
                    if ref:
                        total += qte * ref.weight_in_grams
                    else:
                        errors.append(f"Pas de correspondance unité→g pour '{rec_ing.ingredient.ingredient_name}' ({unit})")
            if errors:
                raise ValidationError("Impossible de calculer la quantité totale : " + "; ".join(errors))
            self.total_recipe_quantity = total
            if save:
                self.save(update_fields=['total_recipe_quantity'])
            return total
        return self.total_recipe_quantity
    
    def _auto_fill_servings_from_pan(self):
        """Tente de deviner le nombre de portions si un pan est présent mais pas les servings renseignés."""
        if not self.pan:
            return

        if self.servings_min and not self.servings_max:
            self.servings_max = self.servings_min
        elif self.servings_max and not self.servings_min:
            self.servings_min = self.servings_max
        elif not self.servings_min and not self.servings_max:
            # Si aucun des deux n'est renseigné, on utilise le nombre de cavités du moule utilisé
            if self.pan.units_in_mold and self.pan_quantity:
                # cas : 1 cercle individuel utilisé 5 fois => 5 portions
                self.servings_min = self.pan.units_in_mold * self.pan_quantity
                self.servings_max = self.servings_min
            elif self.pan.units_in_mold:
                self.servings_min = self.pan.units_in_mold
                self.servings_max = self.pan.units_in_mold
            elif self.pan_quantity:
                self.servings_min = self.pan_quantity
                self.servings_max = self.pan_quantity

    def _validate_servings_range(self):
        if self.servings_min and self.servings_max and self.servings_min > self.servings_max:
            raise ValidationError("Le nombre de portions minimum ne peut pas être supérieur au maximum.")
    
    def clean(self):
        """ Vérifications métier avant sauvegarde. """
        # Validation basique
        # if not self.user and not self.guest_id: # On ne peut pas avoir aucun user ni aucun guest_id
        #     raise ValidationError("Une recette doit appartenir à un utilisateur ou à un invité (user ou guest_id obligatoire).")
        # On ne peut pas avoir les deux
        if self.user and self.guest_id:
            raise ValidationError("Une recette ne peut pas avoir à la fois un user et un guest_id.")
    
        if not self.recipe_name or len(self.recipe_name.strip()) < 3:
            raise ValidationError("Le nom de la recette doit contenir au moins 3 caractères.")
        if not self.chef_name or len(self.chef_name.strip()) < 3:
            raise ValidationError("Le nom du chef doit contenir au moins 3 caractères.")
        if not self.recipe_name:
            raise ValidationError("Le nom de la recette est obligatoire.")

        if self.description and len(self.description.strip()) < 10:
            raise ValidationError("La description doit contenir au moins 10 caractères.")
        if self.trick and len(self.trick.strip()) < 10:
            raise ValidationError("L’astuce (trick) doit contenir au moins 10 caractères.")
        if self.context_name and len(self.context_name.strip()) < 3:
            raise ValidationError("Le contexte doit contenir au moins 3 caractères.")
        if self.source and len(self.source.strip()) < 3:
            raise ValidationError("La source doit contenir au moins 3 caractères.")
        
        # Servings doivent être positifs si renseignés
        if self.servings_min is not None and self.servings_min < 1:
            raise ValidationError("Le nombre minimal de portions doit être supérieur à 0.")
        if self.servings_max is not None and self.servings_max < 1:
            raise ValidationError("Le nombre maximal de portions doit être supérieur à 0.")
        if self.servings_min and self.servings_max and self.servings_min > self.servings_max:
            raise ValidationError("Le nombre minimal de portions ne peut pas être supérieur au nombre maximal.")

        self._validate_servings_range()
        self._auto_fill_servings_from_pan()

        # Normalisation
        self.recipe_name = normalize_case(self.recipe_name)
        self.chef_name = normalize_case(self.chef_name)
        if self.context_name:
            self.context_name = normalize_case(self.context_name)
        if self.source:
            self.source = normalize_case(self.source)

        # Si un seul servings fourni, l’autre est copié automatiquement
        if self.servings_min and not self.servings_max:
            self.servings_max = self.servings_min
        if self.servings_max and not self.servings_min:
            self.servings_min = self.servings_max

        # --- Unicité nom/chef/context vide ---
        # Empêcher les doublons sur (nom, chef) quand context_name est NULL ou vide
        normalized_context = self.context_name or ""
        if normalized_context == "":
            doublon = Recipe.objects.exclude(pk=self.pk).filter(
                recipe_name__iexact=self.recipe_name, chef_name__iexact=self.chef_name,
            ).filter(models.Q(context_name__isnull=True) | models.Q(context_name="")).exists()
            if doublon:
                raise ValidationError("Il existe déjà une recette de ce nom et chef sans contexte. Ajoutez un contexte pour différencier.")

        # Si une parent_recipe est renseignée, le type doit être VARIATION
        if self.parent_recipe and self.recipe_type != "VARIATION":
            raise ValidationError("Une recette avec un parent doit être de type VARIATION.")

        # Si le type est VARIATION, il faut une parent_recipe
        if self.recipe_type == "VARIATION" and not self.parent_recipe:
            raise ValidationError("Une recette de type VARIATION doit avoir une parent_recipe.")

        # Note adaptation que si il existe un parent_recipe
        if self.adaptation_note and not self.parent_recipe:
            raise ValidationError({"adaptation_note": "Ce champ n'est permis que pour une adaptation (parent_recipe doit être défini)."})

        # Anti boucle directe
        if self.parent_recipe and self.parent_recipe == self:
            raise ValidationError("Une recette ne peut pas être sa propre version précédente.")

        # --- Boucle indirecte (cycle) ---
        def has_cyclic_parent(instance):
            current = instance.parent_recipe
            while current:
                if current == instance:
                    return True
                current = current.parent_recipe
            return False

        if has_cyclic_parent(self):
            raise ValidationError("Cycle détecté dans les versions de recette.")
    
        # Pas possible de valider contenu tant que non sauvegardée
        if not self.id:  # Si la recette n'existe pas encore en base, on ne peut pas vérifier
            return

        # Une recette doit avoir au moins (un ingrédient OU une sous-recette) ET au moins une étape 
        has_ingredients = self.recipe_ingredients.exists()
        has_subrecipes = self.main_recipes.exists()
        has_steps = self.steps.exists()
        if not (has_ingredients or has_subrecipes):
            raise ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
        # Une recette doit avoir au moins une étape
        if not has_steps:
            raise ValidationError("Une recette doit contenir au moins une étape.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.parent_recipe and not self.context_name:
            self.context_name = f"Variante de {self.parent_recipe.recipe_name}"
        super().save(*args, **kwargs)

class RecipeStep(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="steps")
    step_number = models.IntegerField(validators=[MinValueValidator(1)], null=True, blank=True)
    instruction = models.TextField(max_length=250)
    trick = models.TextField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['recipe','step_number']
        constraints = [models.UniqueConstraint(fields=["recipe", "step_number"], name="unique_step_per_recipe"),]

    def delete(self, *args, **kwargs):
        """Empêche la suppression du dernier `RecipeStep` d'une recette et réorganise les étapes après suppression."""
        total_steps = RecipeStep.objects.filter(recipe=self.recipe).count()
        if total_steps == 1:
            raise ValidationError("A recipe must have at least one step.")

        super().delete(*args, **kwargs)  # Suppression si plus d'un steps)

        # Réorganiser les `step_number` restants
        steps = RecipeStep.objects.filter(recipe=self.recipe).order_by("step_number")
        for index, step in enumerate(steps, start=1):
            step.step_number = index
            step.save()
    
    def clean(self):
        super().clean()

        # Vérifier si `recipe` est défini sans provoquer d'erreur
        recipe = getattr(self, "recipe", None)
        if recipe is None:
            return  # On stoppe la validation pour éviter toute erreur
    
        # Assigner automatiquement max(step_number) + 1 dans la recette si step_number n'est pas spécifié
        # --- 1. Si nouvelle étape (pas de pk), auto-attribution si absent ---
        if not self.pk and self.step_number is None:
            qs = RecipeStep.objects.filter(recipe=recipe)
            max_step = qs.aggregate(models.Max("step_number"))["step_number__max"]
            self.step_number = 1 if max_step is None else max_step + 1
        # --- 2. Si update, interdire step_number vide ---
        if self.pk and self.step_number is None:
            raise ValidationError("Impossible de vider le numéro d'étape sur une étape existante.")
        # --- 3. Interdire plusieurs étapes sans numéro sur une même recette ---
        if self.step_number is None:
            exists_other = RecipeStep.objects.filter(recipe=recipe, step_number__isnull=True).exclude(pk=self.pk).exists()
            if exists_other:
                raise ValidationError("Impossible d'avoir plusieurs étapes sans numéro dans une recette.")

        # Vérifier que le numéro d'étape est strictement supérieur à 0
        if self.step_number < 1:
            raise ValidationError("Step number must start at 1.")
        
        # Vérifie que l'instruction a une longueur minimale
        if self.instruction and len(self.instruction) < 5:
            raise ValidationError("L'instruction doit contenir au moins 5 caractères.")

        # Si c’est le seul step de la recette, il doit obligatoirement être step_number == 1
        if self.recipe and RecipeStep.objects.filter(recipe=self.recipe).exclude(pk=self.pk).count() == 0:
            if self.step_number != 1:
                raise ValidationError("S'il n'y a qu'une seule étape, son numéro doit être 1.")
    
        # Vérifier que le `step_number` est consécutif
        qs = RecipeStep.objects.filter(recipe=recipe).exclude(pk=self.pk)  # Exclure soi-même pour éviter le faux positif sur update
        if qs.exists():
            last_step_number = qs.aggregate(models.Max("step_number"))["step_number__max"]
            # Le nouveau doit être exactement à la suite ou égal à un existant si on fait un update
            if self.step_number > last_step_number + 1:
                raise ValidationError("Step numbers must be consecutive.")

    def save(self, *args, **kwargs):
        self.clean() 
        super().save(*args, **kwargs)

@receiver(post_delete, sender=RecipeStep)
def reorder_step_numbers(sender, instance, **kwargs):
    """ Réorganise les step_number après suppression (même en bulk_delete !) ."""
    steps = RecipeStep.objects.filter(recipe=instance.recipe).order_by("step_number")
    for idx, step in enumerate(steps, start=1):
        if step.step_number != idx:
            step.step_number = idx
            step.save()

class SubRecipe(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='main_recipes')
    sub_recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name='used_in_recipes')
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)

    def clean(self):
        """ Validation métier avant sauvegarde """
        if self.recipe == self.sub_recipe:
            raise ValidationError("Une recette ne peut pas être sa propre sous-recette.")

        # Vérifier uniquement si quantity est bien un nombre avant de comparer
        if isinstance(self.quantity, (int, float)) and self.quantity <= 0:
            raise ValidationError("La quantité doit être strictement positive.")
        
        # Empêcher la modification de `recipe` après création
        if self.pk:
            original = SubRecipe.objects.get(pk=self.pk)
            if original.recipe != self.recipe:
                raise ValidationError("Recipe cannot be changed after creation.")

    def save(self, *args, **kwargs):
        """ Applique les validations avant la sauvegarde """
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} {self.unit} de {self.sub_recipe.recipe_name} dans {self.recipe.recipe_name}"

class Ingredient(models.Model):
    ingredient_name = models.CharField(max_length=200, unique=True)
    categories = models.ManyToManyField(Category, related_name='ingredients', blank=True)
    labels = models.ManyToManyField(Label, related_name='ingredients', blank=True)

    # Utilisateur
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ingredients", blank=True, null=True)  # null=True pour migrer en douceur
    guest_id = models.CharField(max_length=64, blank=True, null=True, db_index=True) 
    visibility = models.CharField(max_length=10, choices=[('private', 'Privée'), ('public', 'Publique')], default='private')
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['ingredient_name']

    def __str__(self):
        return self.ingredient_name

    def clean(self):
        """ Vérifie que les `categories` et `labels` existent bien en base, sans les créer automatiquement. """
        if self.user and self.guest_id:
            raise ValidationError("Une recette ne peut pas avoir à la fois un user et un guest_id.")

        # Ignorer la validation des ManyToMany si l'objet n'est pas encore enregistré
        if not self.pk:
            return
        
        # Vérifie que toutes les catégories et labels associées existent en base
        existing_categories = set(Category.objects.values_list("id", flat=True))
        existing_labels = set(Label.objects.values_list("id", flat=True))

        for category in self.categories.all():
            if category.id not in existing_categories:
                raise ValidationError(f"La catégorie '{category.category_name}' n'existe pas en base.")
            # Vérifie que la catégorie est bien de type 'ingredient' ou 'both'
            if category.category_type not in ("ingredient", "both"):
                raise ValidationError(f"La catégorie '{category.category_name}' (type '{category.category_type}') n'est pas valide pour un ingrédient.")

        for label in self.labels.all():
            if label.id not in existing_labels:
                raise ValidationError(f"Le label '{label.label_name}' n'existe pas en base.")
            # Vérifie que le label est bien de type 'ingredient' ou 'both'
            if label.label_type not in ("ingredient", "both"):
                raise ValidationError(f"Le label '{label.label_name}' (type '{label.label_type}') n'est pas valide pour un ingrédient.")

        # Vérifier que le nom est correct, normalisé
        self.ingredient_name = normalize_case(self.ingredient_name)
        
        # Empêcher les noms trop courts ou entièrement numériques
        if len(self.ingredient_name) < 2:
            raise ValidationError("Le nom de l'ingrédient doit contenir au moins 2 caractères.")
        
        if self.ingredient_name.isdigit():
            raise ValidationError("Le nom de l'ingrédient ne peut pas être uniquement numérique.")

    def save(self, *args, **kwargs):
        """ Sauvegarde et validation sans duplication d'ID."""
        # Forcer la validation `clean()` AVANT `full_clean()`
        self.full_clean() 
        
        # Si l'objet est nouveau, on le sauvegarde une première fois pour obtenir un ID
        is_new = self.pk is None
        if is_new:
            super().save(*args, **kwargs)

        # Maintenant que l’objet a un ID, on peut exécuter `full_clean()`
        self.full_clean(exclude=['categories', 'labels']) # Exclure les relations ManyToMany

        # Sauvegarde finale seulement si l’objet est nouveau
        if is_new:
            return  # On évite un deuxième `save()` si l’objet est déjà en base
        
        super().save(*args, **kwargs)  # Une seule sauvegarde pour éviter `IntegrityError`

class Store(models.Model):
    store_name = models.CharField(max_length=200) #default="Non renseigné")
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    address = models.CharField(max_length=200, blank=True, null=True)

    # Utilisateur
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stores", blank=True, null=True)  # null=True pour migrer en douceur
    guest_id = models.CharField(max_length=64, blank=True, null=True, db_index=True) 
    visibility = models.CharField(max_length=10, choices=[('private', 'Privée'), ('public', 'Publique')], default='private')
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["store_name", "city", "zip_code", "address"], name="unique_store_per_location")]
        indexes = [models.Index(fields=["store_name", "city", "zip_code"])]  # Ajout d'un index pour accélérer les requêtes sur (store_name, city, zip_code)

    def __str__(self):
        return f"{self.store_name} ({self.city or 'Ville non renseignée'})"

    def clean(self):
        if self.user and self.guest_id:
            raise ValidationError("Une recette ne peut pas avoir à la fois un user et un guest_id.")

        # Vérifie que le magasin a une localisation valide
        if self.store_name and not (self.city or self.zip_code or self.address):
            raise ValidationError("Si un magasin est renseigné, vous devez indiquer une ville, un code postal ou une adresse.")
        if not self.store_name :
            raise ValidationError("field cannot be null")
        # Vérifie que le nom du magasin, de la ville et l'addresse ont une longueur minimale
        if len(self.store_name) < 2:
            raise ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")
        if self.city and len(self.city) < 2:
            raise ValidationError("Le nom de la ville doit contenir au moins 2 caractères.")
        if self.address and len(self.address) < 2:
            raise ValidationError("L'adresse doit contenir au moins 2 caractères.")

        # Normalisation des noms avant validation
        self.store_name = normalize_case(self.store_name)
        self.city = normalize_case(self.city)
        self.address = normalize_case(self.address)

        # Vérifie l’unicité en base sur (store_name, city, zip_code, address)
        if Store.objects.filter(store_name=self.store_name, city=self.city, zip_code=self.zip_code, address=self.address).exclude(id=self.id).exists():
            raise ValidationError("Ce magasin existe déjà.")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class IngredientPrice(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="prices")
    brand_name = models.CharField(max_length=200, null=True, blank=True, default=None)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="prices", null=True, blank=True)
    quantity = models.FloatField(validators=[MinValueValidator(0)])       # Quantité
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)          # Unité de mesure
    price = models.FloatField(validators=[MinValueValidator(0)])          # Prix normal
    date = models.DateField(null=True, blank=True, default=now)           # Date d'enregistrement du prix

    is_promo = models.BooleanField(default=False)  # Indique si c'est un prix promo
    promotion_end_date = models.DateField(null=True, blank=True)  # Date de fin de promo, Facultatif

    class Meta:
        constraints = [UniqueConstraint(
                fields=["ingredient", "store", "brand_name", "quantity", "unit"], name="unique_ingredient_price")]

    def __str__(self):
        """ Affichage clair du prix de l’ingrédient """
        promo_text = " (Promo)" if self.is_promo else ""
        store_name = str(self.store) if self.store else "Non renseigné"
        return f"{self.ingredient.ingredient_name} - {self.brand_name} @ {store_name} ({self.quantity}{self.unit} pour {self.price}€{promo_text})"

    def __init__(self, *args, **kwargs):
        """ Normalise l'unité de mesure immédiatement après l'instanciation. """
        super().__init__(*args, **kwargs)
        
        if self.unit:  # Vérifier que `unit` n'est pas vide
            self.unit = normalize_case(self.unit)  # Appliquer la normalisation

    def clean(self):
        """ Validation des contraintes métier avant sauvegarde """
        # Vérifier que les champs obligatoires sont remplis
        if self.price is None or self.quantity is None or self.unit is None:
            raise ValidationError("Le prix, la quantité et l'unité de mesure sont obligatoires.")
        if self.date is None:
            self.date = now().date()  # Assigner la date du jour par défaut

        # Vérifier que 'price' et 'quantity' sont bien des floats et les convertir sinon.
        if self.price is not None:
            try:
                self.price = float(self.price)
            except ValueError:
                raise ValidationError("Le prix doit être un nombre valide.")

        if self.quantity is not None:
            try:
                self.quantity = float(self.quantity)
            except (ValueError, TypeError):
                raise ValidationError("La quantité doit être un nombre valide.")

        # Vérifier que les prix et les quantités sont positifs
        if self.price is not None and self.price <= 0:
            raise ValidationError("Un ingrédient doit avoir un prix strictement supérieur à 0€.")
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError("Une quantité ne peut pas être négative ou nulle.")
        
        # Vérifie que le nom de la marque a une longueur minimale
        if self.brand_name and len(self.brand_name) < 2:
            raise ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")

        # Normaliser la marque
        if self.brand_name:
            self.brand_name = normalize_case(self.brand_name)
        
        # Vérifier que `unit` est bien dans `UNIT_CHOICES`
        valid_units = dict(UNIT_CHOICES).keys()  # Récupérer les clés valides
        if self.unit not in valid_units:
            raise ValidationError(f"L'unité '{self.unit}' n'est pas valide. Choisissez parmi {list(valid_units)}.")

        # Vérifier la cohérence des promotions
        if self.promotion_end_date and not self.is_promo:
            raise ValidationError("Une date de fin de promo nécessite que `is_promo=True`.")
        if self.promotion_end_date and self.promotion_end_date < now().date():
            raise ValidationError("La date de fin de promo ne peut pas être dans le passé.")

        # Vérifier que si `is_promo=True`, le prix promo n'est pas supérieur au dernier prix normal
        if self.is_promo:
            last_price = (
                IngredientPrice.objects.filter(ingredient=self.ingredient, store=self.store)
                .exclude(is_promo=True)  # Exclure les anciens prix promo
                .order_by("-date").first())
            if last_price and self.price > last_price.price:
                raise ValidationError(f"Le prix promo ({self.price}€) doit être inférieur au dernier prix normal ({last_price.price}€).")

        # Vérifier l'unicité du tuple (ingredient, store, brand_name, quantity, unit) : Sert à afficher un message d'erreur plus UX-friendly
        if IngredientPrice.objects.exclude(pk=self.pk).filter(ingredient=self.ingredient, store=self.store, brand_name=self.brand_name, 
                                                              quantity=self.quantity, unit=self.unit).exists():
            raise ValidationError("Un prix existe déjà pour ce tuple. Pas de doublons autorisés.")
    
    def save(self, *args, **kwargs):
        """
        Archivage de l'ancien prix **seulement si** :
          - update (pas create)
          - le prix change (pas un update sur date/is_promo/promotion_end_date uniquement)
        Respecte la logique métier décrite dans le serializer DRF :
            - Si la date modifiée est plus récente ou égale à la ligne existante, on archive l'ancienne.
            - Si la date modifiée est antérieure à l'existant, on archive la nouvelle valeur (rétroactif).
        """
        is_create = self.pk is None

        self.full_clean()  # Valide l’objet avant sauvegarde

        if not is_create:
            # L’objet existe déjà, donc update potentiel
            old = IngredientPrice.objects.get(pk=self.pk)

            # Check du tuple unique (interdiction de le modifier)
            for field in ["ingredient", "store", "brand_name", "quantity", "unit"]:
                if getattr(old, field) != getattr(self, field):
                    raise ValidationError(f"Modification du champ '{field}' interdite après création. Veuillez plutôt créer un nouvel objet")

            prix_change = (old.price != self.price)

            # Si changement de prix :
            if prix_change:
                # Si la nouvelle date est plus récente ou égale, archive l'ancien prix
                if self.date is None or old.date is None or self.date >= old.date:
                    # Archive l'ancien avant update
                    IngredientPriceHistory.objects.create(
                        ingredient=old.ingredient,
                        store=old.store,
                        brand_name=old.brand_name,
                        quantity=old.quantity,
                        unit=old.unit,
                        price=old.price,
                        is_promo=old.is_promo,
                        promotion_end_date=old.promotion_end_date,
                        date=old.date,
                    )
                else:
                    # Si la date est antérieure (update rétroactif), on archive la nouvelle donnée,
                    # mais on ne modifie pas la ligne existante
                    IngredientPriceHistory.objects.create(
                        ingredient=self.ingredient,
                        store=self.store,
                        brand_name=self.brand_name,
                        quantity=self.quantity,
                        unit=self.unit,
                        price=self.price,
                        is_promo=self.is_promo,
                        promotion_end_date=self.promotion_end_date,
                        date=self.date,
                    )
                    # On ne modifie pas la ligne existante
                    return  # stoppe le save

        super().save(*args, **kwargs)

class IngredientPriceHistory(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True)  # Laisse l’historique même si l’ingrédient est supprimé)
    ingredient_name = models.CharField(max_length=255, null=True, blank=True, default="")  # Ajout du nom pour référence
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True)  # Ajout du magasin
    brand_name = models.CharField(max_length=200, blank=True, null=True, default=None)  # Ajout de la marque
    quantity = models.FloatField(validators=[MinValueValidator(0)])  # Ajout de la quantité
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)  # Ajout de l'unité
    price = models.FloatField(validators=[MinValueValidator(0)])
    is_promo = models.BooleanField(default=False)
    promotion_end_date = models.DateField(null=True, blank=True)  # Ajout de la date de fin de promo
    date = models.DateField(null=True, blank=True, default=now)  # Date d'archivage

    class Meta:
        constraints = [UniqueConstraint(
                fields=["ingredient", "store", "brand_name", "quantity", "unit"],
                name="unique_ingredient_price_history")]
        verbose_name_plural = "ingredient prices history"

    def __str__(self):
        """ Affichage clair du prix de l’ingrédient """
        promo_text = " (Promo)" if self.is_promo else ""
        store_name = str(self.store) if self.store else "Non renseigné"
        ingredient_display = self.ingredient.ingredient_name if self.ingredient else self.ingredient_name or "Ingrédient supprimé"
        return f"{ingredient_display} - {self.brand_name} @ {store_name} ({self.quantity}{self.unit} pour {self.price}€{promo_text})"

    def __init__(self, *args, **kwargs):
        """ Normalise l'unité de mesure immédiatement après l'instanciation. """
        super().__init__(*args, **kwargs)
        
        if self.unit:  # Vérifier que `unit` n'est pas vide
            self.unit = normalize_case(self.unit)  # Appliquer la normalisation

    def clean(self):
        """ Validation des contraintes métier avant sauvegarde """
        # Vérifier que les champs obligatoires sont remplis
        if self.price is None or self.quantity is None or self.unit is None:
            raise ValidationError("Le prix, la quantité et l'unité de mesure sont obligatoires.")
        if self.date is None:
            self.date = now().date()  # Assigner la date du jour par défaut

        # Vérifier que 'price' et 'quantity' sont bien des floats
        if self.price is not None:
            try:
                self.price = float(self.price)
            except ValueError:
                raise ValidationError("Le prix doit être un nombre valide.")

        if self.quantity is not None:
            try:
                self.quantity = float(self.quantity)
            except (ValueError, TypeError):
                raise ValidationError("La quantité doit être un nombre valide.")

        # Vérifier que les prix et les quantités sont positifs
        if self.price is not None and self.price <= 0:
            raise ValidationError("Un ingrédient doit avoir un prix strictement supérieur à 0€.")
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError("Une quantité ne peut pas être négative ou nulle.")
        
        # Vérifie que le nom de la marque a une longueur minimale
        if self.brand_name and len(self.brand_name) < 2:
            raise ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")

        # Normaliser la marque
        if self.brand_name:
            self.brand_name = normalize_case(self.brand_name)

        # Vérifier que `unit` est bien dans `UNIT_CHOICES`
        valid_units = dict(UNIT_CHOICES).keys()  # Récupérer les clés valides
        if self.unit not in valid_units:
            raise ValidationError(f"L'unité '{self.unit}' n'est pas valide. Choisissez parmi {list(valid_units)}.")

        # Vérifier la cohérence des promotions
        if self.promotion_end_date and not self.is_promo:
            raise ValidationError("Une date de fin de promo nécessite que `is_promo=True`.")
        if self.promotion_end_date and self.promotion_end_date < now().date():
            raise ValidationError("La date de fin de promo ne peut pas être dans le passé.")

        # Vérifier que si `is_promo=True`, le prix promo est inférieur au dernier prix normal
        if self.is_promo:
            last_price = (
                IngredientPriceHistory.objects.filter(ingredient=self.ingredient, store=self.store)
                .exclude(is_promo=True)  # Exclure les anciens prix promo
                .order_by("-date").first())
            if last_price and self.price > last_price.price:
                raise ValidationError(f"Le prix promo ({self.price}€) doit être inférieur au dernier prix normal ({last_price.price}€).")

    def save(self, *args, **kwargs):
        """ Vérifie les contraintes métier et empêche l'enregistrement inutile de doublons. """
        self.clean()  # Appliquer les validations avant l'enregistrement

        # Remplit automatiquement `ingredient_name` avec le slug de `ingredient`.
        if self.ingredient:
            self.ingredient_name = self.ingredient.ingredient_name  # Récupère le slug

        # Vérifier s'il existe déjà un historique avec le même prix pour ce produit
        last_price = IngredientPriceHistory.objects.filter(
            ingredient=self.ingredient, store=self.store, brand_name=self.brand_name, 
            quantity=self.quantity, unit=self.unit
        ).order_by("-date").first()

        # Si le dernier prix enregistré est identique, ne pas créer de doublon
        if last_price and last_price.price == self.price and last_price.is_promo == self.is_promo:
            return  # Annule l'enregistrement

        super().save(*args, **kwargs)
        
# Gestion des promos plus avancées (promo nationale + promo magasin par ex., promo conditionnelle 2+1 gratuit)
# Ajout d'un modèle Promotion
# class Promotion(models.Model):
#     ingredient_price = models.ForeignKey(IngredientPrice, on_delete=models.CASCADE, related_name="promotions")
#     discount_price = models.FloatField(validators=[MinValueValidator(0)])  # Prix promo
#     start_date = models.DateField(default=now)  # Début de promo
#     end_date = models.DateField(null=True, blank=True)  # Fin de promo optionnelle

class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="recipe_ingredients")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="ingredient_recipes")
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)
    display_name = models.CharField(max_length=255, blank=True, null=True)  # Nom avec suffixe (ex: "Sucre 1")

    class Meta:
        ordering = ['recipe', 'ingredient']

    def __str__(self):
        return f"{self.quantity} {self.unit} de {self.ingredient.ingredient_name} pour {self.recipe.recipe_name}"

# When creating a new Recipe through the Django admin site, Django uses the ModelAdmin class to handle the creation of the Recipe and its related RecipeIngredient objects. 
# The ModelAdmin class does not use the RecipeSerializer or RecipeIngredientSerializer, so the validate_quantity method in the RecipeIngredientSerializer is not being called.
# To enforce the validation when creating a Recipe through the Django admin site, override the clean method of the RecipeIngredient model.
    def clean(self):
        """ Vérifie les règles métier avant sauvegarde. """
        # Vérifier que l'ingrédient, la quantité et l'unité sont bien renseignés
        if not self.ingredient:
            raise ValidationError("Un ingrédient est obligatoire.")
        if not self.quantity:
            raise ValidationError("Une quantité est obligatoire.")
        if not self.unit:
            raise ValidationError("Une unité de mesure est obligatoire.")

        # Normaliser le display_name
        if self.display_name:
            self.display_name = normalize_case(self.display_name)
        
        # Vérifier que la quantité est valide
        if self.quantity <= 0:
            raise ValidationError("Quantity must be a positive number.")

        # Vérifier que `unit` fait partie des choix définis
        valid_units = dict(UNIT_CHOICES).keys()
        if self.unit not in valid_units:
            raise ValidationError(f"L'unité '{self.unit}' n'est pas valide. Choisissez parmi {list(valid_units)}.")

    def save(self, *args, **kwargs):
        """ Nettoyage des données et validation avant sauvegarde. """
        self.full_clean()

        # Génère un suffixe si l’ingrédient est déjà utilisé dans la recette
        if not self.display_name:  # Seulement si `display_name` n'est pas déjà défini
            count = RecipeIngredient.objects.filter(recipe=self.recipe, ingredient=self.ingredient).count()
            suffix = f" {count + 1}" if count > 0 else ""  # Ajoute un numéro si nécessaire
            self.display_name = normalize_case(f"{self.ingredient.ingredient_name}{suffix}")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """ 
        Empêche la suppression du dernier ingrédient d'une recette *s'il n'y a pas de subrecipe*
        et réattribue les suffixes après suppression. 
        """
        # Compte le nombre d'ingrédients ET vérifie les subrecipes
        has_ingredients = self.recipe.recipe_ingredients.count()
        has_subrecipes = self.recipe.main_recipes.exists()

        # Si c'est le dernier ingrédient ET qu'il n'y a pas de subrecipe => erreur
        if has_ingredients == 1 and not has_subrecipes:
            raise ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")

        # Récupérer tous les ingrédients de la recette AVANT suppression
        recipe_ingredients = RecipeIngredient.objects.filter(
            recipe=self.recipe,
            ingredient=self.ingredient
        ).order_by('id')  # On trie pour avoir un ordre logique
    
        super().delete(*args, **kwargs)  # Suppression de l'objet actuel
        # Réattribuer les suffixes aux autres ingrédients de la même recette
        for index, ingredient in enumerate(recipe_ingredients, start=1):
            ingredient.display_name = f"{ingredient.ingredient.ingredient_name} {index}"
            ingredient.save(update_fields=['display_name'])  # Évite un save complet

class IngredientUnitReference(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE, related_name="unit_references", help_text="Ingrédient concerné")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, help_text="Unité (ex : unité, cas, cc, cup, tranche, etc.)")
    weight_in_grams = models.FloatField(help_text="Poids en grammes correspondant à 1 unité de cet ingrédient.")
    notes = models.CharField(max_length=200, blank=True, help_text="Commentaire, astuce ou source (optionnel).")
    is_hidden = models.BooleanField(default=False, help_text="Masque cette référence (soft-delete pour forker une globale)")

    # Utilisateur
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="ingredient_unit_references")
    guest_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    class Meta:
        unique_together = ('ingredient', 'unit', 'user', 'guest_id')
        verbose_name = "Référence de conversion unité ➔ poids"
        verbose_name_plural = "Références de conversion unité ➔ poids"
        ordering = ['ingredient', 'unit', 'is_hidden']
        constraints = [models.UniqueConstraint(fields=["ingredient", "unit", "user", "guest_id", "is_hidden"], 
                                               name="unique_ingredient_unit_user_guest_hidden")]

    def __str__(self):
        return f"{self.ingredient.ingredient_name} ({self.unit}) : {self.weight_in_grams} g"

    def clean(self):
        # Champs obligatoires (ingredient et unit)
        if not self.ingredient :
            raise ValidationError("L’ingrédient doit être renseigné.")
        if not self.unit:
            raise ValidationError("L’unité doit être renseigné.")

        # Unicité du couple ingrédient/unité
        filters = dict(ingredient=self.ingredient, unit=self.unit, user=self.user, guest_id=self.guest_id, is_hidden=self.is_hidden)
        if IngredientUnitReference.objects.exclude(pk=self.pk).filter(**filters).exists():
            raise ValidationError("Une référence similaire existe déjà pour cet utilisateur ou guest avec ce statut (actif/masqué).")

        # Poids doit être strictement positif
        if self.weight_in_grams is None or self.weight_in_grams <= 0:
            raise ValidationError("Le poids doit être strictement supérieur à 0.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Appelle clean()
        super().save(*args, **kwargs)

class UserRecipeVisibility(models.Model):
    """
    Permet à chaque utilisateur ou invité (guest) de masquer des recettes qui, sinon,
    resteraient accessibles à tous (ex: recettes de base de l’application).
    Une ligne par (user OU guest_id, recipe). Un des deux (user ou guest_id) doit être non-null.
    Si `visible=False`, la recette est masquée pour cet utilisateur/invité ; sinon, visible (par défaut).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="hidden_recipes")
    guest_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    visible = models.BooleanField(default=True) 
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "guest_id", "recipe"),)

    def clean(self):
        # Au moins un des deux doit être présent
        if not self.user and not self.guest_id:
            raise ValidationError("Un UserRecipeVisibility doit être lié à un user OU un guest_id.")
        if self.user and self.guest_id:
            raise ValidationError("Un UserRecipeVisibility ne peut pas avoir à la fois user et guest_id.")

        # Vérif unicité "à la main" car DB ne le fera pas si NULL présent
        qs = UserRecipeVisibility.objects.filter(recipe=self.recipe)
        if self.user:
            qs = qs.filter(user=self.user, guest_id__isnull=True)
        else:
            qs = qs.filter(user__isnull=True, guest_id=self.guest_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError("Doublon (user/guest_id/recipe) impossible.")
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

