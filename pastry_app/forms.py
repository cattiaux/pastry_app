from django import forms
from .models import Recipe, Pan, Ingredient, RecipeIngredient

class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['recipe_name']

class PanForm(forms.ModelForm):
    class Meta:
        model = Pan
        fields = ['pan_type', 'dimension1', 'dimension2', 'height']

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['ingredient_name', 'family_name']

class RecipeIngredientForm(forms.ModelForm):
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.all())
    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity']
