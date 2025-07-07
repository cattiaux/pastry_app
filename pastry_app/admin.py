from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from .models import *

# @admin.register(IngredientPrice)
class IngredientPriceAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("store", "brand_name", "is_promo")
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")

class IngredientPriceInline(admin.StackedInline):
    model = IngredientPrice
    extra = 1  # number of extra forms to display

# @admin.register(IngredientPriceHistory)
# class IngredientPriceHistoryAdmin(admin.ModelAdmin):
#     list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
#     list_filter = ("store", "brand_name", "is_promo")
#     search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")
    
#     def has_add_permission(self, request):
#         """ Empêche l'ajout manuel d'entrées historiques sauf pour les super-utilisateurs. """
#         return request.user.is_superuser

#     def has_change_permission(self, request, obj=None):
#         """ Empêche la modification d'entrées historiques sauf pour les super-utilisateurs. """
#         return request.user.is_superuser

#     def has_delete_permission(self, request, obj=None):
#         """ Empêche la suppression d'entrées historiques sauf pour les super-utilisateurs. """
#         return request.user.is_superuser

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

class PanAdmin(admin.ModelAdmin):
    list_display = ('pan_name', 'id', 'pan_brand', 'pan_type', 'units_in_mold', 'visibility', 'is_default')

    class Media:
        js = ('pastry_app/admin/pan_admin.js',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "category_type", "parent_category")
    search_fields = ('category_name',)

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

class LabelAdmin(admin.ModelAdmin):
    list_display = ('label_name', 'label_type')
    search_fields = ('label_name',)

    def delete_model(self, request, obj):
        # Refuse la suppression si le label est utilisé
        if obj.recipelabel_set.exists() or obj.ingredientlabel_set.exists():
            messages.error(request, "Impossible de supprimer ce label : il est utilisé par une recette ou un ingrédient.")
            return
        super().delete_model(request, obj)

admin.site.register(Recipe, RecipeAdmin)
# admin.site.register(RecipeStep, RecipeStepAdmin)
# admin.site.register(SubRecipe, SubRecipeAdmin)
admin.site.register(Ingredient, IngredientAdmin)
# admin.site.register(IngredientPrice, IngredientPriceAdmin)
# admin.site.register(IngredientPriceHistory, IngredientPriceHistoryAdmin)
# admin.site.register(RecipeIngredient, RecipeIngredientAdmin)
admin.site.register(Pan, PanAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Label, LabelAdmin)
