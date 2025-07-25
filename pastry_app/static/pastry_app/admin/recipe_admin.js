/**
 * ==============================================================
 * JS ADMIN : RECIPE - UX & UI ENHANCEMENTS
 * ==============================================================
 * Ce fichier gère plusieurs améliorations UX pour l'admin Django :
 * 1. Affichage conditionnel du champ "adaptation_note" selon le type de recette et la présence d'une parent_recipe.
 * 2. Affichage conditionnel du champ "pan quantity" uniquement si un "pan" est sélectionné. 
 * 3. Affichage de messages d'alerte/information sous les blocs inlines "étapes", "ingrédients", "sous-recettes".
 * 4. Hide synthesis fieldset and its title on "add recipe" only
 * 5. Utilisation de Tagify pour le rendu visuel du champ tags
 */


// ===========================================
// Initialisation avec attente de django.jQuery
// ===========================================
(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function($) {

            // ========================================
            // 1. Affichage/Masquage de adaptation_note
            // ========================================

            // Affiche/masque le champ adaptation_note selon le contexte (tu peux garder ta logique !)
            function toggleAdaptationNoteField() {
                var typeField = $('#id_recipe_type');
                var adaptationField = $('#id_adaptation_note').closest('.form-row');
                var parentRecipeField = $('#id_parent_recipe');

                function updateField() {
                    if (typeField.val() === 'VARIATION' && parentRecipeField.val()) {
                        adaptationField.show();
                    } else {
                        adaptationField.hide();
                        $('#id_adaptation_note').val('');
                    }
                }

                typeField.on('change', updateField);
                parentRecipeField.on('change', updateField);
                updateField();
            }

            // ===============================================
            // 2. Affichage conditionnel du champ pan_quantity
            // ===============================================
            function togglePanQuantityField() {
                var panField = $('#id_pan');
                var panQuantityRow = $('.form-row.field-pan_quantity');

                function updateField() {
                    if (panField.val()) {
                        panQuantityRow.show();
                    } else {
                        panQuantityRow.hide();
                        $('#id_pan_quantity').val(1);  // Réinitialise la quantité à 1 si le pan est désélectionné
                    }
                }

                panField.on('change', updateField);
                updateField();
            }

            // =======================================================
            // 3. Affichage des messages d'info sous les blocs inlines
            // =======================================================

            // Utilitaire pour attendre que les blocs inline existent
            function waitForInlines(callback) {
                if (
                    $('#steps-group').length &&
                    $('#recipe_ingredients-group').length &&
                    $('#main_recipes-group').length
                ) {
                    callback();
                } else {
                    setTimeout(function() {
                        waitForInlines(callback);
                    }, 100);
                }
            }

            /**
             * Ajoute un bandeau d'information sous un bloc inline admin.
             * @param {string} selector - Sélecteur CSS du bloc inline
             * @param {string} message - Texte à afficher.
             */
            function addInlineInfo(selector, message) {
                var $inlineGroup = $(selector);
                // Vérifie si le message est déjà présent pour éviter les doublons
                if ($inlineGroup.length > 0 && $inlineGroup.find('.admin-inline-info').length === 0) {
                    var $infoDiv = $('<div class="admin-inline-info"></div>');
                    $infoDiv.css({
                        "padding": "7px 12px",
                        "margin": "8px 0 14px 0",
                        "border-radius": "4px",
                        "font-size": "13px",
                    });
                    $infoDiv.html("&#9888; " + message);
                    // Ajoute le message juste après le titre du bloc inline
                    $inlineGroup.find('h2').first().after($infoDiv);
                }
            }

            // -------------------------------------------------------------------
            // 4. Hide synthesis fieldset and its title on "add recipe" only
            // -------------------------------------------------------------------
            function hideSynthesisOnCreate() {
                if ($('body').hasClass('add-form')) {
                    // Hide the whole fieldset (title + synthesis block)
                    $('.field-recipe_subrecipes_synthesis').closest('fieldset').hide();
                }
                // Sinon, fallback : vérifie le titre h1 (si tu n’as pas la classe add-form)
                else if ($('#content h1').text().trim().toLowerCase().startsWith('add recipe')) {
                    $('.field-recipe_subrecipes_synthesis').closest('fieldset').hide();
                }
            }

            // -------------------------------------------------------------------
            // 5. Utilisation de Tagify pour le rendu visuel du champ tags
            // -------------------------------------------------------------------
            function setupTagifyOnTagsField() {
                var tagsInput = document.querySelector('#id_tags');
                if (!tagsInput) return;

                // Si déjà initialisé, on ne refait pas
                if (tagsInput.classList.contains('tagify-initialized')) return;

                // Initialisation Tagify
                new Tagify(tagsInput, {
                    delimiters: ",",
                    whitelist: [], // Optionnel : possibilité de fournir une liste de tags suggérés
                    dropdown: {
                        enabled: 0,  // 0 = pas de suggestions par défaut, 1 = suggestions dès le premier caractère
                        maxItems: 10,  // max suggestions affichées
                    }
                });
                tagsInput.classList.add('tagify-initialized');
            }

            // =====================================
            // 4. Initialisation globale au chargement
            // =====================================
            $(document).ready(function () {

                // 1. Adaptation note display/hide
                toggleAdaptationNoteField();

                // 2. Pan quantity display/hide
                togglePanQuantityField();

                // 3. Hide synthesis fieldset on recipe creation
                hideSynthesisOnCreate();

                // 4. Ajout des messages d'info sous les bons blocs inline
                waitForInlines(function() {
                    // Steps
                    addInlineInfo(
                        '#steps-group',
                        "Ajoutez <strong>au moins une étape</strong> à votre recette (obligatoire)."
                    );
                    // Ingredients
                    addInlineInfo(
                        '#recipe_ingredients-group',
                        "Ajoutez <strong>au moins un ingrédient (ou une sous-recette)</strong> à votre recette."
                    );
                    // Subrecipes
                    addInlineInfo(
                        '#main_recipes-group',
                        "Ajoutez <strong>au moins une sous-recette (ou un ingrédient)</strong> à votre recette."
                    );
                });

                // 5. Initialisation de Tagify sur le champ tags
                setupTagifyOnTagsField();
            });

        })(django.jQuery);

    } else {
        // Attend que django.jQuery soit dispo
        setTimeout(waitForDjangoJQuery, 100);
    }
})();