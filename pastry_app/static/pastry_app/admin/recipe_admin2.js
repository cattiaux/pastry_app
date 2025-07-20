(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function($) {

            // ==============================
            // JS ADMIN : RECIPE - UX & UI
            // ==============================

            // 1. Affiche/masque le champ adaptation_note selon le contexte (tu peux garder ta logique !)
            function toggleAdaptationNote() {
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

            $(document).ready(function () {

                // 1. Adaptation note display/hide
                toggleAdaptationNote();

                // 2. Ajout des messages d'info sous les bons blocs inline
                waitForInlines(function() {

                    /**
                     * Ajoute un bandeau d'information sous un bloc inline admin (step, ingredient, subrecipe).
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
            });

        })(django.jQuery);

    } else {
        // Attend que django.jQuery soit dispo
        setTimeout(waitForDjangoJQuery, 100);
    }
})();