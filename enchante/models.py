from math import pi
from django.db import models
from django.forms import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from .constants import UNIT_CHOICES

class BaseModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.name = self.name.lower() if self.name else None
        super().save(*args, **kwargs)

class Pan(models.Model):
    PAN_TYPES = [('ROUND', 'Round'),('SQUARE', 'Square'),]
    pan_name = models.TextField(max_length=200)
    pan_type = models.CharField(max_length=200, choices=PAN_TYPES)

    class Meta:
        ordering = ['pan_name']
        # abstract = True

    def __str__(self):
        return self.pan_name

    def save(self, *args, **kwargs):
        # # if pan is abstract : enforce that the pan_type matches the model’s class name
        # expected_pan_type = self.__class__.__name__.upper().replace('PAN', '')
        # if self.pan_type != expected_pan_type:
        #     raise ValidationError(f"{self.__class__.__name__} model can only have pan_type '{expected_pan_type}'")

        self.pan_name = self.pan_name.lower() if self.pan_name else None
        super().save(*args, **kwargs)

class RoundPan(Pan):
    # pan = models.OneToOneField(Pan, on_delete=models.CASCADE, primary_key=True, related_name='roundpan')
    diameter = models.FloatField()
    height = models.FloatField()
    
    # class Meta(Pan.Meta):
    #     unique_together = ('pan_name', 'diameter', 'height')
    class Meta:
        ordering = ['pan_ptr']
        unique_together = ('pan_ptr', 'diameter', 'height')

    @property
    def volume(self):
        radius = self.diameter / 2
        return pi * radius * radius * self.height

class SquarePan(Pan):
    # pan = models.OneToOneField(Pan, on_delete=models.CASCADE, primary_key=True, related_name='squarepan')
    length = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()

    # class Meta(Pan.Meta):
    #     unique_together = ('pan_name', 'length', 'width', 'height')
    class Meta:
        ordering = ['pan_ptr']
        unique_together = ('pan_ptr', 'length', 'width', 'height')

    @property
    def volume(self):
        return self.length * self.width * self.height
    
class Recipe(models.Model):
    recipe_name = models.TextField(max_length=200)
    chef = models.CharField(max_length=200)
    ingredients = models.ManyToManyField('Ingredient', through='RecipeIngredient')
    default_volume = models.FloatField(null=True, blank=True)
    default_servings = models.IntegerField(null=True, blank=True)
    # content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    # object_id = models.PositiveIntegerField(null=True)
    # pan = GenericForeignKey('content_type', 'object_id')
    pan = models.ForeignKey(Pan, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('recipe_name', 'chef',)
        ordering = ['recipe_name', 'chef']

    def __str__(self):
        return self.recipe_name

    def save(self, *args, **kwargs):
        self.recipe_name = self.recipe_name.lower() if self.recipe_name else None
        super().save(*args, **kwargs)

class RecipeStep(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    step_number = models.IntegerField()
    instruction = models.TextField()
    trick = models.TextField(null=True)

    class Meta:
        ordering = ['recipe','step_number']

class SubRecipe(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe')
    sub_recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='subrecipe_set')
    quantity = models.FloatField(default=0)

class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.lower() if self.name else None
        super().save(*args, **kwargs)

class Label(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.lower() if self.name else None
        super().save(*args, **kwargs)

class Ingredient(models.Model):
    ingredient_name = models.TextField(max_length=200, unique=True)
    categories = models.ManyToManyField(Category, related_name='ingredients', blank=True)
    labels = models.ManyToManyField(Label, related_name='ingredients', blank=True)

    class Meta:
        ordering = ['ingredient_name']

    def __str__(self):
        return self.ingredient_name

    def clean(self):
        for category in self.categories.all():
            Category.objects.get_or_create(name=category.name)
        for label in self.labels.all():
            Label.objects.get_or_create(name=label.name)

    def save(self, *args, **kwargs):
        self.ingredient_name = self.ingredient_name.lower() if self.ingredient_name else None
        super().save(*args, **kwargs)

class IngredientPrice(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    brand = models.TextField(max_length=200, null=True)
    store_name = models.TextField(max_length=200, null=True)
    date = models.DateField()
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    unit = models.TextField(max_length=200, choices=UNIT_CHOICES)
    price = models.FloatField(validators=[MinValueValidator(0)])

    def save(self, *args, **kwargs):
        self.brand = self.brand.lower() if self.brand else None
        self.store_name = self.store_name.lower() if self.store_name else None
        super().save(*args, **kwargs)

class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField(default=0, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES, null=True, blank=True)

# When creating a new Recipe through the Django admin site, Django uses the ModelAdmin class to handle the creation of the Recipe and its related RecipeIngredient objects. The ModelAdmin class does not use the RecipeSerializer or RecipeIngredientSerializer, so the validate_quantity method in the RecipeIngredientSerializer is not being called.
# To enforce the validation when creating a Recipe through the Django admin site, override the clean method of the RecipeIngredient model.
    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be a positive number.")

    def __str__(self):
        return self.ingredient.ingredient_name

class PanServing(models.Model):
    pan = models.ForeignKey(Pan, on_delete=models.SET_NULL, null=True, blank=True)
    # content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # object_id = models.PositiveIntegerField()
    # pan_type = GenericForeignKey('content_type', 'object_id')
    volume = models.FloatField()
    servings = models.IntegerField()

