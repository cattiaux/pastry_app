from django.contrib import admin, messages
from django import forms
from django.forms.models import BaseInlineFormSet
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
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
    readonly_fields = ['display_name'] 

class RecipeStepInlineForm(forms.ModelForm):
    """
    Formulaire ModelForm custom pour RecipeStep Inline dans l'admin.
    - Garantit que le step_number assigné dans cleaned_data est bien propagé sur l'instance avant sauvegarde.
    """
    def save(self, commit=True):
        # Force la cohérence : ce qui est dans cleaned_data devient la vraie valeur de l'instance
        step_number = self.cleaned_data.get('step_number')
        if step_number is not None:
            self.instance.step_number = step_number
        return super().save(commit=commit)

class RecipeStepInlineFormSet(BaseInlineFormSet):
    """
    Formset personnalisé pour la gestion des étapes de recette (RecipeStep) dans l'admin Django.

    - Auto-recalcule TOUS les step_number consécutifs (1...N) après création, édition ou suppression.
    - Aucun champ step_number n'est obligatoire côté admin.
    - UX fluide, plus besoin de corriger à la main, ni de gérer les doublons ou les trous dans la séquence.
    - Affiche les erreurs métier user-friendly dans l'admin (pas d'écran jaune).
    """
    def clean(self):
        # Appelle la clean de base (qui va appeler clean() sur chaque form/instance)
        super().clean()

        # 1. Retire l'erreur métier "l'unique step doit être n°1" en mode admin, seulement en création admin
        #    (souvent gênante lors des saisies multiples inline)
        errors_to_skip = ["S'il n'y a qu'une seule étape, son numéro doit être 1."]
        for form in self.forms:
            if form.errors:
                # Si la forme contient l'erreur métier ciblée, on la retire
                # (utile uniquement lors de la création, pas lors de l'update d'une recette existante)
                for error in errors_to_skip:
                    form._errors.pop('__all__', None)

        # 2. Récupère tous les forms valides (pas DELETE)
        step_forms = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)]

        # 3. Attribue à CHAQUE form un step_number consécutif en fonction de l'ordre visuel (formset)
        for i, form in enumerate(step_forms, start=1):
            form.cleaned_data['step_number'] = i

class RecipeStepInline(admin.TabularInline):
    model = RecipeStep
    extra = 1
    form = RecipeStepInlineForm
    formset = RecipeStepInlineFormSet

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "instruction":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 2, "cols": 40})
        if db_field.name == "trick":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 1, "cols": 40})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def delete_model(self, request, obj):
        """ Affiche les erreurs métier (ex: suppression du dernier step) comme message utilisateur."""
        try:
            obj.delete()
        except ValidationError as e:
            self.message_user(request, e.messages[0], level=messages.ERROR)

    def save_formset(self, request, form, formset, change):
        """ Réordonne automatiquement les step_number après modification/suppression. """
        # Appel normal
        super().save_formset(request, form, formset, change)
        # Réordonner les steps
        recipe = form.instance
        steps = recipe.steps.order_by('step_number')
        for i, step in enumerate(steps, start=1):
            if step.step_number != i:
                step.step_number = i
                step.save()

class SubRecipeInline(admin.TabularInline):
    model = SubRecipe
    fk_name = 'recipe'
    extra = 0

class RecipeCategoryInline(admin.TabularInline):
    model = RecipeCategory
    extra = 0
    autocomplete_fields = ['category']

class RecipeLabelInline(admin.TabularInline):
    model = RecipeLabel
    extra = 0
    autocomplete_fields = ['label']

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    inlines = [RecipeCategoryInline, RecipeLabelInline, RecipeIngredientInline, RecipeStepInline, SubRecipeInline]
    list_display = ('recipe_name', 'id', 'chef_name', 'context_name', 'parent_recipe', 'tags', 'visibility', 'is_default')
    list_filter = ('recipe_type', 'categories', 'labels', 'visibility')    
    readonly_fields = ['recipe_subrecipes_synthesis']

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css','pastry_app/admin/recipe_admin.css')}
        js = ('pastry_app/admin/recipe_admin.js',)
    
    fieldsets = (
        ('Synthèse', {
            'fields': ('recipe_subrecipes_synthesis',),
            'classes': ('hide-label',),
            'description': "Vue synthétique ingrédients et étapes (recette + sous-recettes)."
        }),
        ('Caractéristiques principales de la recette', {
            'fields': ('recipe_type', 'recipe_name', 'chef_name', 'parent_recipe', 'adaptation_note',
                       'servings_min', 'servings_max', 'pan', 'pan_quantity')
        }),
        ('Contenu', {
            'fields': ('description', 'trick', 'image', 'tags')
        }),
        ('Source de la recette', {
            'fields': ('context_name', 'source')
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    def recipe_subrecipes_synthesis(self, obj):
        html = "<div class='recipe-columns-container'>"

        # Main recipe (always first column)
        html += """
        <div class='recipe-card'>
        <h3 class='main-title'>Main recipe</h3>
        <b>Ingredients:</b>
        <ul>
        """
        for ri in obj.recipe_ingredients.all():
            html += f"<li>{ri.quantity} {ri.unit} of <b>{ri.ingredient}</b></li>"
        html += "</ul><b>Steps:</b><ol>"
        for step in obj.steps.all().order_by('step_number'):
            html += f"<li>{step.instruction}</li>"
        html += "</ol></div>"

        # Subrecipes (one column per subrecipe)
        for sub in obj.main_recipes.all():
            html += f"""
            <div class='recipe-card'>
                <h4 class='sub-title'>Sub-recipe: {sub.sub_recipe.recipe_name}</h4>
                <b>Ingredients:</b>
                <ul>
            """
            for ri in sub.sub_recipe.recipe_ingredients.all():
                html += f"<li>{ri.quantity} {ri.unit} of <b>{ri.ingredient}</b></li>"
            html += "</ul><b>Steps:</b><ol>"
            for step in sub.sub_recipe.steps.all().order_by('step_number'):
                html += f"<li>{step.instruction}</li>"
            html += "</ol></div>"

        html += "</div>"  # end of flex container

        return mark_safe(html)
    recipe_subrecipes_synthesis.short_description = ""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Ajuste la taille (hauteur/largeur) des champs texte 'description' et 'trick', 
        pour avoir des champs moins envahissants et un rendu plus agréable.
        """
        if db_field.name == "description":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 2, "cols": 60})
        if db_field.name == "trick":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 1, "cols": 60})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        """
        Valide les contraintes “au moins un ingrédient/sous-recette” après sauvegarde.
        Évite l’écran jaune admin et affiche une erreur claire à l’utilisateur.
        Nécessaire car l’admin ne gère pas ces règles lors de la création.
        """
        super().save_related(request, form, formsets, change)
        recipe = form.instance

        try :
            # On vérifie la présence d'au moins un ingrédient ou une sous-recette
            has_ingredients = recipe.recipe_ingredients.exists()
            has_subrecipes = recipe.main_recipes.exists()
            has_steps = recipe.steps.exists()
            if not (has_ingredients or has_subrecipes):
                raise ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            if not has_steps:
                raise ValidationError("Une recette doit contenir au moins une étape.")
        except ValidationError as e:
            # Cas création (recette pas encore en BDD avant cette transaction)
            if recipe._state.adding:
                recipe.delete()
                self.message_user(request, str(e), level=messages.ERROR)
                # Ne pas raise: force le redirect à la liste
            else:
                # Cas édition, on ne supprime pas !
                raise

class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'ingredient_name', 'id')
    readonly_fields = ['display_name'] 

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'  # Sets column name in admin site

    def ingredient_name(self, obj):
        return obj.ingredient.ingredient_name
    ingredient_name.short_description = 'Ingredient Name'  # Sets column name in admin site

@admin.register(RecipeStep)
class RecipeStepAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'id', 'step_number')

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def get_form(self, request, obj=None, **kwargs):
        """ Rend le champ step_number obligatoire en modification, mais facultatif en création. """
        form = super().get_form(request, obj, **kwargs)
        original_init = form.__init__
        def custom_init(form_self, *a, **kw):
            original_init(form_self, *a, **kw)
            if obj:  # update
                form_self.fields["step_number"].required = True
            else:
                form_self.fields["step_number"].required = False
        form.__init__ = custom_init
        return form

    def delete_view(self, request, object_id, extra_context=None):
        """
        Empêche la suppression du dernier step, affiche une erreur UX-friendly,
        et évite l'écran jaune.
        """
        obj = self.get_object(request, object_id)
        if obj:
            total_steps = RecipeStep.objects.filter(recipe=obj.recipe).count()
            if total_steps == 1:
                self.message_user(request, "❌ Une recette doit avoir au moins une étape.", level=messages.ERROR)
                return redirect(request.META.get('HTTP_REFERER', '/admin/pastry_app/recipestep/'))
        return super().delete_view(request, object_id, extra_context)

    def get_actions(self, request):
        """ Déscactive l'action de suppression en masse pour éviter l'écran jaune d'erreur. """
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

@admin.register(SubRecipe)
class SubRecipeAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'subrecipe_name', 'id')

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def subrecipe_name(self, obj):
        return obj.sub_recipe.recipe_name
    subrecipe_name.short_description = 'Subrecipe Name'
