from math import pi
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.timezone import now
from .constants import UNIT_CHOICES, CATEGORY_TYPE_MAP, LABEL_TYPE_MAP
from django.core.exceptions import ValidationError
from pastry_app.tests.utils import normalize_case

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
    - Actuellement, `category_name` N'A PAS `unique=True` pour éviter les conflits en développement.
    - Une fois en production, AJOUTER `unique=True` sur `category_name`.
    """
    CATEGORY_CHOICES = [
        ('ingredient', 'Ingrédient'),
        ('recipe', 'Recette'),
        ('both', 'Les deux'),
    ]
    # Note : `unique=True` dans le field 'category_name' empêche les doublons en base, mais bloque l'API avant même qu'elle ne puisse gérer l'erreur.
    # Pour l'unicité avec pytest, enlève `unique=True` et gère l'unicité dans `serializers.py`.
    category_name = models.CharField(max_length=200) #unique=True à activer en production
    category_type = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='both')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name

    def save(self, *args, **kwargs):
        """ 
        Validation avant sauvegarde : nettoyage, validation et attribution du type automatique.
        """
        self.category_name = normalize_case(self.category_name) # Lower + supprime espaces inutiles

        # Vérifier si `category_name` est valide (dans la liste des choix autorisés)
        if self.category_name not in CATEGORY_TYPE_MAP:
            raise ValidationError(f"'{self.category_name}' n'est pas une catégorie valide.")

        # Assigner automatiquement `category_type`
        self.category_type = CATEGORY_TYPE_MAP[self.category_name]

        super().save(*args, **kwargs)

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
    label_name = models.CharField(max_length=200, unique=True) #unique=True à activer en production
    label_type = models.CharField(max_length=10, choices=LABEL_CHOICES, default='both')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label_name

    def save(self, *args, **kwargs):
        """ 
        Validation avant sauvegarde : nettoyage, validation et attribution du type automatique.
        """
        self.label_name = normalize_case(self.label_name) # Lower + supprime espaces inutiles

        # Vérifier si `label_name` est valide (dans la liste des choix autorisés)
        if self.label_name not in LABEL_TYPE_MAP:
            raise ValidationError(f"'{self.label_name}' n'est pas une catégorie valide.")

        # Assigner automatiquement `label_type`
        self.label_type = LABEL_TYPE_MAP[self.label_name]

        super().save(*args, **kwargs)

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT oblige Django à empêcher la suppression en base
class IngredientCategory(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT oblige Django à empêcher la suppression en base
class RecipeCategory(models.Model):
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT oblige Django à empêcher la suppression en base
class IngredientLabel(models.Model):
    ingredient = models.ForeignKey("Ingredient", on_delete=models.CASCADE)
    label = models.ForeignKey("Label", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

####### AVEC AUTRE QUE SQLITE : POSTRESQL ou MYSQL ###############
# Utiliser une table intermédiaire avec on_delete=PROTECT oblige Django à empêcher la suppression en base
class RecipeLabel(models.Model):
    recipe = models.ForeignKey("Recipe", on_delete=models.CASCADE)
    label = models.ForeignKey("Label", on_delete=models.PROTECT)  # Empêche la suppression d'une catégorie utilisée

class Recipe(models.Model):
    recipe_name = models.TextField(max_length=200)
    chef = models.CharField(max_length=200, default="Anonyme")
    ingredients = models.ManyToManyField('Ingredient', through='RecipeIngredient', related_name="recipes")
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
    """
    ⚠️ IMPORTANT ⚠️
    - Actuellement, `ingredient_name` N'A PAS `unique=True` pour éviter les conflits en développement.
    - Une fois en production, AJOUTER `unique=True` sur `ingredient_name`.
    """
    # Note : `unique=True` dans le field 'label_name' empêche les doublons en base, mais bloque l'API avant même qu'elle ne puisse gérer l'erreur.
    # Pour l'unicité avec pytest, enlève `unique=True` et gère l'unicité dans `serializers.py`.
    ingredient_name = models.CharField(max_length=200) #unique=True à activer en production
    categories = models.ManyToManyField(Category, related_name='ingredients', blank=True)
    labels = models.ManyToManyField(Label, related_name='ingredients', blank=True)

    class Meta:
        ordering = ['ingredient_name']

    def __str__(self):
        return self.ingredient_name

    def clean(self):
        """ Vérifie que les `categories` et `labels` existent bien en base, sans les créer automatiquement. """
        # Ignorer la validation des ManyToMany si l'objet n'est pas encore enregistré
        if not self.pk:
            return
        
        existing_categories = set(Category.objects.values_list("id", flat=True))
        existing_labels = set(Label.objects.values_list("id", flat=True))

        for category in self.categories.all():
            if category.id not in existing_categories:
                raise ValidationError(f"La catégorie '{category.category_name}' n'existe pas en base.")

        for label in self.labels.all():
            if label.id not in existing_labels:
                raise ValidationError(f"Le label '{label.label_name}' n'existe pas en base.")

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
        self.clean() 
        
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
    store_name = models.CharField(max_length=200, null=False, blank=False) #default="Non renseigné")
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = ("store_name", "city", "zip_code")  # Empêcher les doublons
        indexes = [models.Index(fields=["store_name", "city", "zip_code"])]  # Ajout d'un index pour accélérer les requêtes sur (store_name, city, zip_code)

    def __str__(self):
        return f"{self.store_name} ({self.city or 'Ville non renseignée'})"

    def clean(self):
        # Vérifie que le magasin a une localisation valide
        if self.store_name and not (self.city or self.zip_code):
            raise ValidationError("Si un magasin est renseigné, vous devez indiquer une ville ou un code postal.")
        if not self.store_name :
            raise ValidationError("field cannot be null")
        # Vérifie que le nom du magasin et de la ville ont une longueur minimale
        if len(self.store_name) < 2:
            raise ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")
        if self.city and len(self.city) < 2:
            raise ValidationError("Le nom de la ville doit contenir au moins 2 caractères.")

        # Normalisation des noms avant validation
        self.store_name = normalize_case(self.store_name)
        self.city = normalize_case(self.city)

        # Vérifie qu'on ne peut pas créer deux magasins identiques (unique_together)
        if Store.objects.filter(store_name=self.store_name, city=self.city, zip_code=self.zip_code).exclude(id=self.id).exists():
            raise ValidationError("Ce magasin existe déjà.")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class IngredientPrice(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="prices")
    brand_name = models.TextField(max_length=200, null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="prices", null=True, blank=True)

    quantity = models.FloatField(validators=[MinValueValidator(0)])       # Quantité
    unit = models.TextField(max_length=50, choices=UNIT_CHOICES)          # Unité de mesure
    price = models.FloatField(validators=[MinValueValidator(0)])          # Prix normal
    date = models.DateField(null=True, blank=True, default="2025-01-01")  # Date d'enregistrement du prix

    is_promo = models.BooleanField(default=False)  # Indique si c'est un prix promo
    promotion_end_date = models.DateField(null=True, blank=True)  # Date de fin de promo, Facultatif

    def __str__(self):
        """ Affichage clair du prix de l’ingrédient """
        promo_text = " (Promo)" if self.is_promo else ""
        store_name = self.store.store_name if self.store else "Non renseigné"
        return f"{self.ingredient.ingredient_name} - {self.brand_name} @ {store_name} ({self.quantity}{self.unit} pour {self.price}€{promo_text})"

    def clean(self):
        """ Validation des contraintes métier avant sauvegarde """
        # Vérifier que les champs obligatoires sont remplis
        if self.price is None or self.quantity is None or self.unit is None:
            raise ValidationError("Le prix, la quantité et l'unité de mesure sont obligatoires.")
        if self.date is None:
            self.date = now().date()  # Assigner la date du jour par défaut

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
            raise ValidationError("Si une date de fin de promo est renseignée, `is_promo` doit être activé.")
        if self.promotion_end_date and self.promotion_end_date < now().date():
            raise ValidationError("La date de fin de promo ne peut pas être dans le passé.")

        # Vérifier que si `is_promo=True`, le prix promo est inférieur au dernier prix normal
        if self.is_promo:
            last_price = (
                IngredientPrice.objects.filter(ingredient=self.ingredient, store=self.store)
                .exclude(is_promo=True)  # Exclure les anciens prix promo
                .order_by("-date").first())
            if last_price and self.price >= last_price.price:
                raise ValidationError(f"Le prix promo ({self.price}€) doit être inférieur au dernier prix normal ({last_price.price}€).")

    def save(self, *args, **kwargs):
        """ Archive l'ancien prix dans `IngredientPriceHistory` avant modification. """
        self.clean()  # Valide l’objet avant sauvegarde

        if self.pk:
            old_instance = IngredientPrice.objects.get(pk=self.pk)

            # Vérifier si on modifie bien le même tuple (ingredient, store, brand_name, quantity, unit)
            if (
                old_instance.ingredient == self.ingredient and
                old_instance.store == self.store and
                old_instance.brand_name == self.brand_name and
                old_instance.quantity == self.quantity and
                old_instance.unit == self.unit
            ):
                # Vérifier si le prix ou l'état promo a changé (mais PAS promotion_end_date seule)
                if old_instance.price != self.price or old_instance.is_promo != self.is_promo:
                    # Archiver l'ancien prix avec les anciennes valeurs
                    IngredientPriceHistory.objects.create(
                        ingredient_price=self,
                        ingredient=self.ingredient,
                        store=self.store,
                        brand_name=self.brand_name,
                        quantity=self.quantity,
                        unit=self.unit,
                        price=old_instance.price,  # Prix précédent
                        is_promo=old_instance.is_promo,
                        promotion_end_date=old_instance.promotion_end_date,  # On garde l'ancienne date de fin promo
                        date=old_instance.date  # Date de l'ancien prix
                    )

                    # Met à jour la date du prix actif pour marquer la nouvelle modification
                    self.date = now().date()

        super().save(*args, **kwargs)

class IngredientPriceHistory(models.Model):
    ingredient_price = models.ForeignKey(IngredientPrice, on_delete=models.CASCADE, related_name="history")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)  # Ajout de la FK Ingredient
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True)  # Ajout du magasin
    brand_name = models.CharField(max_length=255, blank=True, null=True)  # Ajout de la marque
    quantity = models.FloatField()  # Ajout de la quantité
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)  # Ajout de l'unité
    price = models.FloatField(validators=[MinValueValidator(0)])
    is_promo = models.BooleanField(default=False)
    promotion_end_date = models.DateField(null=True, blank=True)  # Ajout de la date de fin de promo
    date = models.DateField(default=now)  # Date d'archivage

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ingredient_price", "date"], name="unique_ingredientpricehistory")]

    def clean(self):
        """ Vérifie la cohérence des données avant sauvegarde. """
        # Le prix doit être supérieur à 0
        if self.price <= 0:
            raise ValidationError("Le prix doit être supérieur à 0.")
        # Empêcher l'enregistrement de prix futurs
        if self.date > now().date():
            raise ValidationError("La date ne peut pas être dans le futur.")
        # Vérifier qu'un enregistrement identique n'existe pas déjà
        # if IngredientPriceHistory.objects.filter(ingredient_price=self.ingredient_price, date=self.date, price=self.price).exists():
        #     raise ValidationError("Cet enregistrement de prix existe déjà.")

    def save(self, *args, **kwargs):
        """ Empêche les doublons et n'enregistre que si le prix change. """
        self.clean()  #Appliquer les validations avant l'enregistrement

        # Récupérer le dernier prix enregistré
        last_price = IngredientPriceHistory.objects.filter(ingredient_price=self.ingredient_price).order_by("-date").first()

        # Si le prix n’a pas changé, ne pas enregistrer inutilement
        if last_price and last_price.price == self.price:
            return  

        super().save(*args, **kwargs)
        
# Gestion des promos plus avancées (promo nationale + promo magasin par ex., promo conditionnelle 2+1 gratuit)
# Ajout d'un modèle Promotion
# class Promotion(models.Model):
#     ingredient_price = models.ForeignKey(IngredientPrice, on_delete=models.CASCADE, related_name="promotions")
#     discount_price = models.FloatField(validators=[MinValueValidator(0)])  # Prix promo
#     start_date = models.DateField(default=now)  # Début de promo
#     end_date = models.DateField(null=True, blank=True)  # Fin de promo optionnelle

class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
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
    

