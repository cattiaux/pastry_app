from django.contrib import admin
from .models import Recipe, RecipeStep, RoundPan, SquarePan, SubRecipe, Pan, Ingredient, IngredientPrice, RecipeIngredient, Category, Label

class IngredientPriceAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'id')

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
    list_display = ('recipe_name', 'id', 'chef')
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
    list_display = ('pan_name', 'id')

class RoundPanAdmin(admin.ModelAdmin):
    list_display = ('pan_name', 'id')

class SquarePanAdmin(admin.ModelAdmin):
    list_display = ('pan_name', 'id')

admin.site.register(Recipe, RecipeAdmin)
admin.site.register(RecipeStep, RecipeStepAdmin)
admin.site.register(SubRecipe, SubRecipeAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(IngredientPrice, IngredientPriceAdmin)
admin.site.register(RecipeIngredient, RecipeIngredientAdmin)
admin.site.register(Pan, PanAdmin)
admin.site.register(RoundPan, RoundPanAdmin)
admin.site.register(SquarePan, SquarePanAdmin)
admin.site.register(Category)
admin.site.register(Label)
