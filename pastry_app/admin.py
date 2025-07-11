from django.contrib import admin, messages
from django import forms
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

@admin.register(IngredientPrice)
class IngredientPriceAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("brand_name", "is_promo", StoreCityListFilter, StoreNameListFilter)
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

@admin.register(IngredientPriceHistory)
class IngredientPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
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

class IngredientPriceInline(admin.StackedInline):
    model = IngredientPrice
    extra = 1  # number of extra forms to display

class IngredientAdmin(admin.ModelAdmin):
    inlines = [IngredientPriceInline]
    list_display = ('ingredient_name', 'id')

    # To see only the categories for the selected ingredient in the django admin site
    # def formfield_for_manytomany(self, db_field, request, **kwargs):
    #     if db_field.name == "categories":
    #         if 'change' in request.path:
    #             ingredient_id = request.path.split('/')[-3]
    #             ingredient = Ingredient.objects.get(id=ingredient_id)
    #             kwargs["queryset"] = Category.objects.filter(ingredients=ingredient)
    #     return super().formfield_for_manytomany(db_field, request, **kwargs)

class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1

class RecipeStepInline(admin.TabularInline):
    model = RecipeStep
    extra = 1

class SubRecipeInline(admin.TabularInline):
    model = SubRecipe
    fk_name = 'recipe'
    extra = 1

class RecipeAdmin(admin.ModelAdmin):
    inlines = [RecipeIngredientInline, RecipeStepInline, SubRecipeInline]
    list_display = ('recipe_name', 'id', 'chef_name')
    exclude = ('content_type', 'object_id',)

class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'ingredient_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'  # Sets column name in admin site

    def ingredient_name(self, obj):
        return obj.ingredient.ingredient_name
    ingredient_name.short_description = 'Ingredient Name'  # Sets column name in admin site

class RecipeStepAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

class SubRecipeAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'subrecipe_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def subrecipe_name(self, obj):
        return obj.sub_recipe.recipe_name
    subrecipe_name.short_description = 'Subrecipe Name'


admin.site.register(Recipe, RecipeAdmin)
admin.site.register(Ingredient, IngredientAdmin)

