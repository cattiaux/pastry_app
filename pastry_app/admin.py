from django.contrib import admin, messages
from django import forms
from django.forms.models import BaseInlineFormSet
from django.shortcuts import redirect
from .models import *


class StoreCityListFilter(admin.SimpleListFilter):
    """
    Class pour filter par city dans l'admin de Django.
    """
    title = 'Ville du magasin'
    parameter_name = 'store_city'

    def lookups(self, request, model_admin):
        # Liste des villes présentes dans les stores liés à IngredientPrice
        cities = set(Store.objects.exclude(city__isnull=True).exclude(city__exact="").values_list('city', flat=True))
        return [(city, city) for city in cities]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(store__city=self.value())
        return queryset

class StoreNameListFilter(admin.SimpleListFilter):
    """
    Class pour filter par nom de magasin dans l'admin de Django.
    """
    title = 'Nom du magasin'
    parameter_name = 'store_store_name'

    def lookups(self, request, model_admin):
        # Liste des store_name présentes dans les stores liés à IngredientPrice
        store_names = set(Store.objects.exclude(store_name__isnull=True).exclude(store_name__exact="").values_list('store_name', flat=True))
        return [(store_name, store_name) for store_name in store_names]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(store__store_name=self.value())
        return queryset

class CategoryAdminForm(forms.ModelForm):
    """ formulaire personnalisé pour Category"""
    class Meta:
        model = Category
        fields = "__all__"

class IngredientAdminForm(forms.ModelForm):
    """
    Formulaire admin personnalisé pour Ingredient.

    Affiche une erreur claire sur le champ 'ingredient_name' si le nom existe déjà,
    au lieu d'une page d'erreur générale. Améliore l'UX admin pour la contrainte unique.
    """
    class Meta:
        model = Ingredient
        fields = '__all__'

    def clean_ingredient_name(self):
        # On normalise comme en prod
        value = self.cleaned_data["ingredient_name"].strip().lower()
        if Ingredient.objects.exclude(pk=self.instance.pk).filter(ingredient_name__iexact=value).exists():
            raise ValidationError("Un ingrédient avec ce nom existe déjà.")
        return value

@admin.register(IngredientPrice)
class IngredientPriceAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("brand_name", "is_promo", StoreCityListFilter, StoreNameListFilter)
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")
    autocomplete_fields = ['ingredient', 'store']

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

@admin.register(IngredientPriceHistory)
class IngredientPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient_name", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("brand_name", "is_promo", StoreCityListFilter, StoreNameListFilter)
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        """ Empêche l'ajout manuel d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """ Empêche la modification d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """ Empêche la suppression d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ("category_name", "category_type", "parent_category")
    search_fields = ('category_name',)
    list_filter = ('category_type',)

    class Media:
        js = ('pastry_app/admin/category_admin.js',)
        css = {'all': ('pastry_app/admin/required_fields.css',)}

    # Surcharge de la vue de suppression pour contrôler les messages et empêcher le double message succès/erreur
    def delete_view(self, request, object_id, extra_context=None):
        """
        Cette méthode est surchargée pour :
        - Empêcher la suppression d'une catégorie si elle possède des sous-catégories ou est utilisée,
        - Afficher un message d'erreur (et uniquement celui-ci),
        - Rediriger vers la liste sans afficher le message de succès natif du Django admin,
        - Éviter l'affichage simultané d'un message de succès (inexact) et d'un message d'erreur métier.
        """
        obj = self.get_object(request, object_id)
        # Cas de blocage par enfants ou utilisation
        if obj:
            if obj.recipecategory_set.exists() or obj.ingredientcategory_set.exists():
                messages.error(request, "Impossible de supprimer cette catégorie : elle est utilisée par une recette ou un ingrédient.")
                return redirect('..')
            subcategories = obj.subcategories.all()
            if subcategories.exists():
                sub_names = ', '.join([sc.category_name for sc in subcategories])
                messages.error(
                    request,
                    f"Impossible de supprimer cette catégorie : elle possède des sous-catégories ({sub_names})."
                )
                return redirect('..')
        return super().delete_view(request, object_id, extra_context)

    # Action admin : suppression parent + enfants
    def delete_with_children(self, request, queryset):
        for obj in queryset:
            subcategories = obj.subcategories.all()
            count = subcategories.count()
            subcategories.delete()
            obj.delete()
            messages.success(request, f"Catégorie '{obj.category_name}' et ses {count} sous-catégories supprimées.")

    delete_with_children.short_description = "Supprimer catégorie + sous-catégories"
    actions = [delete_with_children]

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('label_name', 'label_type')
    search_fields = ('label_name',)

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

    def delete_model(self, request, obj):
        # Refuse la suppression si le label est utilisé
        if obj.recipelabel_set.exists() or obj.ingredientlabel_set.exists():
            messages.error(request, "Impossible de supprimer ce label : il est utilisé par une recette ou un ingrédient.")
            return
        super().delete_model(request, obj)

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'id', 'city', 'zip_code', 'address', 'visibility', 'is_default')
    search_fields = ('store_name', 'city')
    list_filter = ('city', 'visibility')

    fieldsets = (
        ('Caractéristiques du magasin', {
            'fields': ('store_name', 'city', 'zip_code', 'address')
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

@admin.register(Pan)
class PanAdmin(admin.ModelAdmin):
    list_display = ('pan_name', 'id', 'pan_brand', 'pan_type', 'units_in_mold', 'visibility', 'is_default')

    fieldsets = (
        ('Caractéristiques du moule', {
            'fields': (
                'pan_name', 'pan_type', 'pan_brand', 
                'diameter', 'height', 
                'length', 'width', 'rect_height', 
                'volume_raw', 'is_total_volume', 'unit'
            )
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    class Media:
        js = ('pastry_app/admin/pan_admin.js',)
        css = {'all': ('pastry_app/admin/required_fields.css',)}

# Pour l’affichage des catégories et labels sous forme de string
def categories_display(obj):
    return ", ".join([c.category_name for c in obj.categories.all()])
categories_display.short_description = "Catégories"

def labels_display(obj):
    return ", ".join([l.label_name for l in obj.labels.all()])
labels_display.short_description = "Labels"

def prices_count(obj):
    return obj.prices.count()
prices_count.short_description = "Nb Prix"

class IngredientPriceInline(admin.TabularInline):
    model = IngredientPrice
    extra = 0  # number of extra forms to display
    min_num = 0
    show_change_link = True  # pour avoir un lien direct vers la fiche prix si besoin

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    form = IngredientAdminForm
    inlines = [IngredientPriceInline]
    list_display = ('ingredient_name', 'id', categories_display, labels_display, 'visibility', 'is_default', prices_count)
    search_fields = ('ingredient_name',)
    list_filter = ('categories','labels', 'visibility')

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

    # Pour mieux ordonner les champs et regrouper les sections
    fieldsets = (
        ('Informations principales', {
            'fields': ('ingredient_name', 'categories', 'labels')
        }),
        ('Gestion', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id')
        }),
    )

    # Pour afficher les catégories/labels sous forme de widget horizontal
    filter_horizontal = ('categories', 'labels')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Permet de filtrer dynamiquement les catégories affichées dans le widget admin.
        Ici, on restreint la sélection aux catégories de type 'ingredient' ou 'both'.
        """
        if db_field.name == "categories":
            kwargs["queryset"] = Category.objects.filter(category_type__in=["ingredient", "both"])
        return super().formfield_for_manytomany(db_field, request, **kwargs)

class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0

class RecipeStepInline(admin.TabularInline):
    model = RecipeStep
    extra = 0

class SubRecipeInline(admin.TabularInline):
    model = SubRecipe
    fk_name = 'recipe'
    extra = 0

class RecipeAdmin(admin.ModelAdmin):
    inlines = [RecipeIngredientInline, RecipeStepInline, SubRecipeInline]
    list_display = ('recipe_name', 'id', 'chef_name', 'context_name', 'parent_recipe', 'tags', 'visibility', 'is_default')
    list_filter = ('recipe_type',)
    exclude = ('content_type', 'object_id',)

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/recipe_admin.js',)

    fieldsets = (
        ('Caractéristiques principales de la recette', {
            'fields': ('recipe_type', 'recipe_name', 'chef_name', 'parent_recipe', 'servings_min', 'servings_max', 'pan_quantity')
        }),
        ('Contenu', {
            'fields': ('description', 'trick', 'image', 'adaptation_note', 'tags')
        }),
        ('Source de la recette', {
            'fields': ('context_name', 'source')
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        recipe = form.instance
        # On vérifie la présence d'au moins un ingrédient ou une sous-recette
        has_ingredients = recipe.recipe_ingredients.exists()
        has_subrecipes = recipe.main_recipes.exists()
        has_steps = recipe.steps.exists()
        if not (has_ingredients or has_subrecipes):
            self.message_user(
                request, "❌ Une recette doit contenir au moins un ingrédient ou une sous-recette.", level="error")
            # Supprimer la recette créée pour éviter la base incohérente
            recipe.delete()
            return
        if not (has_steps or has_subrecipes):
            self.message_user(
                request, "❌ Une recette doit contenir au moins une étape ou une sous-recette.", level="error")
            recipe.delete()
            return

class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'ingredient_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'  # Sets column name in admin site

    def ingredient_name(self, obj):
        return obj.ingredient.ingredient_name
    ingredient_name.short_description = 'Ingredient Name'  # Sets column name in admin site

@admin.register(RecipeStep)
class RecipeStepAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'id', 'step_number')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

# @admin.register(SubRecipe)
class SubRecipeAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'subrecipe_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def subrecipe_name(self, obj):
        return obj.sub_recipe.recipe_name
    subrecipe_name.short_description = 'Subrecipe Name'


admin.site.register(Recipe, RecipeAdmin)

