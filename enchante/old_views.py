from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.forms import inlineformset_factory
from .models import Ingredient, Recipe, RecipeIngredient, Pan
from .forms import IngredientForm, RecipeForm, RecipeIngredientForm, PanForm

def home(request):
    return render(request, 'home.html')

# Ingredient views

# Create
def ingredient_new(request):
    if request.method == "POST":
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save()
            return HttpResponseRedirect('/ingredients')  # Redirect to the ingredient list after successful creation
    else:
        form = IngredientForm()
    return render(request, 'ingredient_new.html', {'form': form})

# Retrieve
def ingredient_list(request):
    ingredients = Ingredient.objects.all()
    return render(request, 'ingredients.html', {'ingredients': ingredients})

def ingredient_detail(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk)
    return render(request, 'ingredient_detail.html', {'ingredient': ingredient})

# Update
def ingredient_edit(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk)
    if request.method == "POST":
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            ingredient = form.save()
            return HttpResponseRedirect('/ingredients')  # Redirect to the ingredient list after successful update
    else:
        form = IngredientForm(instance=ingredient)
    return render(request, 'ingredient_edit.html', {'form': form})

# Delete
def ingredient_delete(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk)
    ingredient.delete()
    return HttpResponseRedirect('/ingredients')  # Redirect to the ingredient list after successful deletion. replace '/ingredients' with the actual URL where your list view is located.

# Recipe views

# Retrieve
def recipe_list(request):
    recipes = Recipe.objects.all()
    return render(request, 'recipes.html', {'recipes': recipes})

def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    return render(request, 'recipe_detail.html', {'recipe': recipe})

# Create
def recipe_new(request):
# 1 - demander les data de recipes
# 2 - demander les ingrédients

    RecipeIngredientFormSet = inlineformset_factory(Recipe, RecipeIngredient, form=RecipeIngredientForm, extra=3)
    if request.method == "POST":
        form = RecipeForm(request.POST)
        formset = RecipeIngredientFormSet(request.POST, prefix='ingredients')
        if form.is_valid() and formset.is_valid():
            recipe = form.save()
            formset.instance = recipe
            formset.save()
            return HttpResponseRedirect('/recipes')
    else:
        form = RecipeForm()
        formset = RecipeIngredientFormSet(prefix='ingredients')
    return render(request, 'recipe_new.html', {'form': form, 'formset': formset})

# Update
def recipe_edit(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == "POST":
        form = RecipeForm(request.POST, instance=recipe)
        if form.is_valid():
            recipe = form.save()
            return HttpResponseRedirect('/recipes') # replace '/recipes' with the actual URL where your list view is located.
    else:
        form = RecipeForm(instance=recipe)
    return render(request, 'recipe_edit.html', {'form': form})

# Delete
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    recipe.delete()
    return HttpResponseRedirect('/recipes') # replace '/recipes' with the actual URL where your list view is located.

# Pan views

# Retrieve
def pan_list(request):
    pans = Pan.objects.all()
    return render(request, 'pans.html', {'pans': pans})

def pan_detail(request, pk):
    pan = get_object_or_404(Pan, pk=pk)
    return render(request, 'pan_detail.html', {'pan': pan})

# Create
def pan_new(request):
    if request.method == "POST":
        form = PanForm(request.POST)
        if form.is_valid():
            pan = form.save()
            return HttpResponseRedirect('/pans') # replace '/recipes' with the actual URL where your list view is located.
    else:
        form = PanForm()
    return render(request, 'pan_new.html', {'form': form})

# Update
def pan_edit(request, pk):
    pan = get_object_or_404(Pan, pk=pk)
    if request.method == "POST":
        form = PanForm(request.POST, instance=pan)
        if form.is_valid():
            pan = form.save()
            return HttpResponseRedirect('/pans') # replace '/recipes' with the actual URL where your list view is located.
    else:
        form = PanForm(instance=pan)
    return render(request, 'pan_edit.html', {'form': form})

# Delete
def pan_delete(request, pk):
    pan = get_object_or_404(Pan, pk=pk)
    pan.delete()
    return HttpResponseRedirect('/pans') # replace '/recipes' with the actual URL where your list view is located.