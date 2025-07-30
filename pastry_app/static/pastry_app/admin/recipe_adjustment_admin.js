/**
 * ==============================================================
 * JS ADMIN : RECIPE - MODE AJUSTEMENT (Pan & Portions)
 * ==============================================================
 * Ce fichier gère le mode d'ajustement dans l'admin Django :
 * - Tous les champs deviennent gris/inactifs sauf pan, servings_min, servings_max et la case à cocher elle-même.
 * - Désactive aussi visuellement les labels pour améliorer la lisibilité.
 * - Prend en compte le champ tags (géré par Tagify).
 */


// ===========================================
// Initialisation avec attente de django.jQuery
// ===========================================
(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function($) {

            /**
            * Désactive tous les champs du formulaire sauf exceptions.
            * Grise aussi les labels correspondants.
            * @param {boolean} isAdjustMode - true si mode ajustement actif
            */
            function setFieldsState(isAdjustMode) {
                // Champs à NE PAS désactiver
                const except = [
                    '#id_pan', 
                    '#id_servings_min', 
                    '#id_servings_max', 
                    '#id_mode_ajustement'
                ];

                // 1. Désactiver tous les champs input/select/textarea sauf exceptions
                $('form :input').each(function() {
                    const $field = $(this);
                    const fieldId = $field.attr('id');
                    if (except.includes('#' + fieldId)) return;

                    // Désactive le champ (peu importe son type)
                    $field.prop('disabled', isAdjustMode);

                    // Gère la désactivation de Tagify (champ tags)
                    if (fieldId === "id_tags" && window.Tagify) {
                        // Si Tagify est utilisé sur ce champ
                        const tagifyInstance = $field.data('tagify');
                        if (tagifyInstance) {
                            tagifyInstance.setReadonly(isAdjustMode);
                        }
                    }
                });

                // 2. Griser/Activer les labels correspondants
                $('form label').each(function() {
                    const $label = $(this);
                    const forId = $label.attr('for');
                    if (forId && except.includes('#' + forId)) {
                        $label.css('opacity', '1');
                    } else {
                        $label.css('opacity', isAdjustMode ? '0.4' : '1');
                    }
                });
            }

            // Initialise la logique du mode ajustement (écouteur sur la checkbox)
            function toggleAdjustmentMode() {
                const $adjustmentCheckbox = $('#id_mode_ajustement');
                if ($adjustmentCheckbox.length === 0) return; // Pas de champ mode_ajustement

                // Quand on coche/décoche la case, on (dé)active les champs
                $adjustmentCheckbox.on('change', function() {
                    setFieldsState($(this).is(':checked'));
                });

                // Initialisation à l'ouverture
                setFieldsState($adjustmentCheckbox.is(':checked'));
            }           

            // Ajoute dynamiquement le bouton après les boutons d'envoi classiques
            function addAdjustButton() {
                const $row = $('.submit-row');
                if ($('#adjust-quantities-btn').length === 0) { // éviter double ajout
                    const $btn = $('<button/>', {
                        id: 'adjust-quantities-btn',
                        type: 'button',
                        class: 'default',
                        text: 'Calculer les ajustements',
                        style: 'margin-left:10px;',
                    });
                    $row.append($btn);

                    // Handler sur le clic du bouton
                    $btn.on('click', function(e) {
                        e.preventDefault();
                        // logique JS d’ajustement des quantités
                        ajusterQuantites();
                    });
                }
            }

            // Logique d’ajustement (à coder selon tes besoins)
            function ajusterQuantites() {
                // Récupère valeurs actuelles du pan/servings
                const recipeId = $('#id_recipe_id').val() || getRecipeIdFromURL();
                const pan = $('#id_pan').val();
                const servingsMin = $('#id_servings_min').val();
                const servingsMax = $('#id_servings_max').val();

                // Construire le payload
                const data = {
                    recipe_id: recipeId,
                    target_pan_id: pan,
                    target_servings: servingsMin,  // À adapter selon la logique réelle
                };

                // Appel AJAX vers /api/recipes-adapt/
                $.ajax({
                    type: "POST",
                    url: "/api/recipes-adapt/",
                    data: JSON.stringify(data),
                    contentType: "application/json",
                    success: function (response) {
                        // Mise à jour des quantités dans la page (inlines ingrédients)
                        updateQuantitiesFromResponse(response);
                    },
                    error: function (xhr) {
                        alert("Erreur lors de l’ajustement : " + xhr.responseText);
                    }
                });
            }

            // Extrait l’ID de recette depuis l’URL admin Django (ex: /admin/pastry_app/recipe/123/change/)
            function getRecipeIdFromURL() {
                const match = window.location.pathname.match(/\/recipe\/(\d+)\/change\//);
                return match ? match[1] : null;
            }

            // Mise à jour des quantités affichées dans les inlines et la synthèse de l’admin Django
            /**
             * Met à jour dynamiquement les champs quantités dans l’admin Django
             * en fonction des données retournées par l’API d’ajustement.
             *
             * @param {Object} response - La réponse JSON de l’API d’ajustement (doit contenir "ingredients")
             */
            function updateQuantitiesFromResponse(response) {
                if (!response.ingredients) {
                    console.warn("Réponse API inattendue : pas de clé 'ingredients'");
                    return;
                }

                response.ingredients.forEach(function(adapted) {
                    var ingredientId = adapted.ingredient;
                    var displayName = (adapted.display_name || "").trim();
                    var newQuantity = adapted.scaled_quantity;

                    // Parcours chaque ligne du formset des ingrédients
                    $('tr.form-row[id^="recipe_ingredients-"]').each(function() {
                        var $row = $(this);
                        // ID ingrédient de la ligne
                        var $ingredientSelect = $row.find('select[name$="-ingredient"]');
                        var currentIngredientId = parseInt($ingredientSelect.val());

                        // Display name de la ligne (texte)
                        var currentDisplayName = $row.find('td.field-display_name p').text().trim();

                        // Correspondance double : id + display_name
                        if (currentIngredientId === ingredientId && currentDisplayName === displayName) {
                            // Champ quantité à mettre à jour
                            var $qtyInput = $row.find('input[name$="-quantity"]');
                            $qtyInput.val(newQuantity);
                            $qtyInput.css('background-color', '#e5ffe5').animate({backgroundColor: "#fff"}, 1000);
                        }
                    });
                });

                // feedback visuel
                $(".messages").append('<div class="success">Quantités ajustées !</div>');

            }
    
            // =====================================
            // Initialisation globale au chargement
            // =====================================
            $(document).ready(function () {

                toggleAdjustmentMode();

                addAdjustButton();

            });

        })(django.jQuery);

    } else {
        // Attend que django.jQuery soit dispo
        setTimeout(waitForDjangoJQuery, 100);
    }
})();