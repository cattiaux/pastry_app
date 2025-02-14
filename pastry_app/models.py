from math import pi
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.utils.timezone import now
from .constants import UNIT_CHOICES, CATEGORY_DEFINITIONS, CATEGORY_TYPE_MAP, CATEGORY_NAME_CHOICES
from django.core.exceptions import ValidationError

class BaseModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.name = self.name.lower() if self.name else None
        super().save(*args, **kwargs)

class Pan(models.Model):
    PAN_TYPES = [('ROUND', 'Round'),('SQUARE', 'Square'),('CUSTOM', 'Custom'),]
    pan_name = models.TextField(max_length=200, unique=True)
    pan_type = models.CharField(max_length=200, choices=PAN_TYPES)

    class Meta:
        ordering = ['pan_name']

    def __str__(self):
        return self.pan_name

    @property
    def volume(self):
        if hasattr(self, 'roundpan'):
            return self.roundpan.volume  # Récupère le volume de RoundPan
        elif hasattr(self, 'squarepan'):
            return self.squarepan.volume  # Récupère le volume de SquarePan
        elif hasattr(self, 'custompan'):
            return self.custompan.volume_cm3  # Récupère le volume en cm3 directement fourni pour CustomPan
        return None 

    def clean(self):
        # Vérifie que `pan_type` est bien un des choix valides
        valid_types = [ptype[0] for ptype in self.PAN_TYPES]  # Liste des types valides
        if self.pan_type not in valid_types:
            raise ValidationError(f"Invalid pan_type: {self.pan_type}. Must be one of {valid_types}")
        # Vérifier si un autre Pan a déjà ce pan_name
        if Pan.objects.filter(pan_name=self.pan_name).exclude(id=self.id).exists():
            raise ValidationError(f"Pan with name '{self.pan_name}' already exists.")
    
    def save(self, *args, **kwargs):
        self.full_clean() # Vérifie `clean()` + contraintes Django
        self.pan_name = self.pan_name.lower() if self.pan_name else None
        super().save(*args, **kwargs)

class RoundPan(Pan):
    # pan = models.OneToOneField(Pan, on_delete=models.CASCADE, primary_key=True, related_name='roundpan')
    diameter = models.FloatField(validators=[MinValueValidator(0.1)])
    height = models.FloatField(validators=[MinValueValidator(0.1)])
    
    class Meta:
        ordering = ['pan_ptr']
        unique_together = ('pan_ptr', 'diameter', 'height')

    @property
    def volume(self):
        radius = self.diameter / 2
        return pi * radius * radius * self.height

class SquarePan(Pan):
    length = models.FloatField(validators=[MinValueValidator(0.1)])
    width = models.FloatField(validators=[MinValueValidator(0.1)])
    height = models.FloatField(validators=[MinValueValidator(0.1)])

    class Meta:
        ordering = ['pan_ptr']
        unique_together = ('pan_ptr', 'length', 'width', 'height')

    @property
    def volume(self):
        return self.length * self.width * self.height
    
class CustomPan(Pan):
    UNIT_CHOICES = [('cm3', 'cm³'), ('L', 'Litres')]
    
    brand = models.CharField(max_length=100, blank=True, null=True)  # Marque du moule (ex: "Silikomart")
    volume_raw = models.FloatField(validators=[MinValueValidator(1)])  # Volume fourni par le fabricant en cm³
    unit = models.CharField(max_length=3, choices=UNIT_CHOICES, default='cm3')  # Unité (cm³ ou L)
    
    class Meta:
        ordering = ['brand', 'pan_ptr']
        unique_together = ('pan_ptr', 'brand')  # Chaque moule custom (pan + marque) est unique

    def __str__(self):
        return f"{self.brand} - {self.pan_name} ({self.volume} cm³)"

    @property
    def volume(self):
        """Retourne le volume en cm³, quelle que soit l'unité stockée."""
        if self.unit == 'L':
            return self.volume_raw * 1000  # Conversion L → cm³
        return self.volume_raw  # Déjà en cm³

class Category(models.Model):
    """
    ⚠️ IMPORTANT ⚠️
    - Actuellement, nous utilisons SQLite, qui ne supporte pas `on_delete=PROTECT`.
    - La suppression est donc gérée dans l’API (voir `CategoryViewSet.destroy()`).
    - Une fois en production, nous prévoyons de migrer vers PostgreSQL.
    - Après migration, vérifier que `on_delete=PROTECT` fonctionne et mettre à jour `destroy()`.

    - Actuellement, `category_name` N'A PAS `unique=True` pour éviter les conflits en développement.
    - Une fois en production avec PostgreSQL, AJOUTER `unique=True` sur `category_name`.
    """

    CATEGORY_CHOICES = [
        ('ingredient', 'Ingrédient'),
        ('recipe', 'Recette'),
        ('both', 'Les deux'),
    ]
    # Note : 
    # `unique=True` dans le field 'category_name' empêche les doublons en base, mais bloque l'API avant même qu'elle ne puisse gérer l'erreur.
    # Pour l'unicité avec pytest, enlève `unique=True` et gère l'unicité dans `serializers.py`.
    category_name = models.CharField(max_length=200) #unique=True à activer en production
    category_type = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='both')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name

    # def clean(self):
    #     """ Validation avant sauvegarde (nettoyage et règles métier)."""
    #     self.category_name = " ".join(self.category_name.lower().strip().split()) # Lower + supprime espaces inutiles

    #     # Vérifier la longueur minimale
    #     if len(self.category_name) < 2:
    #         raise ValidationError("Le nom de la catégorie doit contenir au moins 2 caractères.")

    #     # Empêcher les noms uniquement numériques
    #     if self.category_name.isdigit():
    #         raise ValidationError("Le nom de la catégorie ne peut pas être uniquement numérique.")
        
    #     super().clean()  # Permet à Django d'exécuter d'autres validations éventuelles

    def save(self, *args, **kwargs):
        """ 
        Validation avant sauvegarde : nettoyage, validation et attribution du type automatique.
        """
        self.category_name = " ".join(self.category_name.lower().strip().split()) # Lower + supprime espaces inutiles

        # Vérifier si `category_name` est valide (dans la liste des choix autorisés)
        if self.category_name not in CATEGORY_TYPE_MAP:
            raise ValidationError(f"'{self.category_name}' n'est pas une catégorie valide.")

        # Assigner automatiquement `category_type`
        self.category_type = CATEGORY_TYPE_MAP[self.category_name]

        super().save(*args, **kwargs)

class Label(models.Model):
    LABEL_CHOICES = [
        ('ingredient', 'Ingrédient'),
        ('recipe', 'Recette'),
        ('both', 'Les deux'),
    ]
    label_name = models.CharField(max_length=200, unique=True)
    label_type = models.CharField(max_length=10, choices=LABEL_CHOICES, default='both')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label_name

    def clean(self):
        """ Validation avant sauvegarde."""
        self.label_name = " ".join(self.label_name.lower().strip().split())

        # Vérifier la longueur minimale
        if len(self.label_name) < 2:
            raise ValidationError("Le nom du label doit contenir au moins 2 caractères.")

        # Empêcher les noms uniquement numériques
        if self.label_name.isdigit():
            raise ValidationError("Le nom du label ne peut pas être uniquement numérique.")

    def save(self, *args, **kwargs):
        self.label_name = self.label_name.lower() if self.label_name else ""
        self.full_clean()
        super().save(*args, **kwargs)

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT était une tentative de forcer Django à empêcher la suppression en base
class IngredientCategory(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT était une tentative de forcer Django à empêcher la suppression en base
class RecipeCategory(models.Model):
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

class Recipe(models.Model):
    recipe_name = models.TextField(max_length=200)
    chef = models.CharField(max_length=200, default="Anonyme")
    ingredients = models.ManyToManyField('Ingredient', through='RecipeIngredient')
    categories = models.ManyToManyField(Category, related_name="recipes") 
    default_volume = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])
    default_servings = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    avg_density = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])
    pan = models.ForeignKey(Pan, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('recipe_name', 'chef',)
        ordering = ['recipe_name', 'chef']

    def __str__(self):
        return self.recipe_name
    
    # def clean(self):
    #     """Vérifie qu'au moins `default_servings` ou `pan` est renseigné."""
    #     if not self.default_servings and not self.pan:
    #         raise ValidationError("Vous devez renseigner au moins `default_servings` ou `pan`.")

    def calculate_avg_density(self):
        """
        Calcule la densité moyenne d'une recette (g/cm³).
        """
        total_weight = sum(ri.quantity for ri in self.recipeingredient_set.all())  # Poids total
        return total_weight / self.default_volume if self.default_volume and self.default_volume > 0 else None

    def save(self, *args, **kwargs):
        """Vérifie les contraintes et met à jour `avg_density` avant la sauvegarde."""
        # self.clean()  # Vérifie que `default_servings` ou `pan` est rempli
        self.recipe_name = self.recipe_name.lower() if self.recipe_name else None
        self.chef = self.chef.lower() if self.chef else None
        if self.default_volume and self.default_volume > 0:
            self.avg_density = self.calculate_avg_density()
        super().save(*args, **kwargs)

class RecipeStep(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    step_number = models.IntegerField()
    instruction = models.TextField()
    trick = models.TextField(null=True)

    class Meta:
        ordering = ['recipe','step_number']

    def save(self, *args, **kwargs):
        if RecipeStep.objects.filter(recipe=self.recipe, step_number=self.step_number).exists():
            raise ValidationError(f'Step number {self.step_number} already exists in the recipe.')
        super().save(*args, **kwargs)

class SubRecipe(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe')
    sub_recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='subrecipe_set')
    quantity = models.FloatField(default=0, validators=[MinValueValidator(0.1)])

class Ingredient(models.Model):
    ingredient_name = models.CharField(max_length=200, unique=True)
    categories = models.ManyToManyField(Category, related_name='ingredients', blank=True)
    labels = models.ManyToManyField(Label, related_name='ingredients', blank=True)

    class Meta:
        ordering = ['ingredient_name']

    def __str__(self):
        return self.ingredient_name

    def _validate_m2m_relations(self):
        """ Vérifie que les `categories` et `labels` existent bien en base."""
        
        if not self.pk:  # Vérification avant d’accéder aux ManyToManyField
            return
        
        for category in self.categories.all():
            if not Category.objects.filter(id=category.id).exists():
                raise ValidationError(f"La catégorie '{category.name}' n'existe pas en base.")

        for label in self.labels.all():
            if not Label.objects.filter(id=label.id).exists():
                raise ValidationError(f"Le label '{label.name}' n'existe pas en base.")

    def clean(self):
        existing_categories = {cat.category_name for cat in Category.objects.all()}
        existing_labels = {lbl.label_name for lbl in Label.objects.all()}

        for category in self.categories.all():
            if category.category_name not in existing_categories:
                Category.objects.create(category_name=category.category_name)

        for label in self.labels.all():
            if label.label_name not in existing_labels:
                Label.objects.create(label_name=label.label_name)

    def save(self, *args, **kwargs):
        """ Sauvegarde et validation sans duplication d'ID."""
        
        # Normalisation du nom de l'ingrédient
        self.ingredient_name = self.ingredient_name.lower() if self.ingredient_name else None
        
        # Si l'objet est nouveau, on le sauvegarde une première fois pour obtenir un ID
        is_new = self.pk is None
        if is_new:
            super().save(*args, **kwargs)

        # Maintenant que l’objet a un ID, on peut exécuter `full_clean()`
        self.full_clean(exclude=['categories', 'labels'])  

        # Sauvegarde finale seulement si l’objet est nouveau
        if is_new:
            return  # On évite un deuxième `save()` si l’objet est déjà en base
        
        super().save(*args, **kwargs)  # Une seule sauvegarde pour éviter `IntegrityError`
        # Vérification des `ManyToManyField`
        self._validate_m2m_relations()

class IngredientPrice(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    brand = models.TextField(max_length=200, null=True)
    store_name = models.TextField(max_length=200, null=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    date = models.DateField(null=True, blank=True, default=now)
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.TextField(max_length=200, choices=UNIT_CHOICES)
    price = models.FloatField(validators=[MinValueValidator(0)])

    def clean(self):
        """ Vérifie que city ou zip_code est rempli si store_name est renseigné """
        if self.store_name and not (self.city or self.zip_code):
            raise ValidationError("Si un magasin est renseigné, vous devez indiquer une ville ou un code postal.")

    def save(self, *args, **kwargs):
        self.brand = self.brand.lower() if self.brand else None
        self.store_name = self.store_name.lower() if self.store_name else None
        super().save(*args, **kwargs)

class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField(default=0, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES, null=True, blank=True)

# When creating a new Recipe through the Django admin site, Django uses the ModelAdmin class to handle the creation of the Recipe and its related RecipeIngredient objects. 
# The ModelAdmin class does not use the RecipeSerializer or RecipeIngredientSerializer, so the validate_quantity method in the RecipeIngredientSerializer is not being called.
# To enforce the validation when creating a Recipe through the Django admin site, override the clean method of the RecipeIngredient model.
    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be a positive number.")

    def __str__(self):
        return self.ingredient.ingredient_name

class PanServing(models.Model):
    pan = models.ForeignKey(Pan, on_delete=models.CASCADE)
    servings_min = models.IntegerField(validators=[MinValueValidator(1)])  # Nombre minimum de portions
    servings_max = models.IntegerField(validators=[MinValueValidator(1)])  # Nombre maximum de portions
    # recipe_type = models.CharField(max_length=50, choices=RECIPE_TYPES, null=True, blank=True)

    class Meta:
        ordering = ['servings_min']
        # unique_together = ('pan', 'recipe_type')  # Unicité par pan + type de recette

    def __str__(self):
        return f"{self.pan.pan_name} - {self.pan.volume} cm³ - {self.servings_min}-{self.servings_max} servings ({self.recipe_type})"
    
