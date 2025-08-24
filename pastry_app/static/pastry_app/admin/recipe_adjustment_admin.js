/**
 * ==============================================================
 * JS ADMIN : RECIPE - MODE AJUSTEMENT (Pan & Portions) + Synthèse arborescente
 * ==============================================================
 * Ce fichier gère le mode d'ajustement dans l'admin Django :
 * - Tous les champs deviennent gris/inactifs sauf pan, servings_min, servings_max et la case à cocher elle-même.
 * - Désactive aussi visuellement les labels pour améliorer la lisibilité.
 * - Prend en compte le champ tags (géré par Tagify).
 * 
 *   - Attente de django.jQuery (wrapper)
 *   - CSRF pour AJAX
 *   - Endpoint dynamique
 *   - Collecte des entrées (servings, pan, contraintes)
 *   - POST d’adaptation
 *   - Rendu récursif de la synthèse
 * 
 *   - Accepte une réponse JSON arborescente:
 *      {
 *        ingredients: [...],
 *        subrecipes: [
 *          { recipe_name: "...", ingredients: [...], subrecipes: [...] },
 *          ...
 *        ]
 *      }
 *    Compatibilité: supporte aussi les variantes {tree:{...}} ou {children:[...]}.
 */


// ===========================================
// Initialisation avec attente de django.jQuery
// ===========================================
(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function($) {

            // ------------ Helpers sélecteurs robustes ------------

            function getInlinePrefix(defaultPrefix){
                // Tente de lire le prefix depuis data-inline-formset si présent
                var grp = document.getElementById(defaultPrefix + '-group');
                if (grp && grp.dataset && grp.dataset.inlineFormset) {
                try { return JSON.parse(grp.dataset.inlineFormset).options.prefix || defaultPrefix; } catch(e){}
                }
                return defaultPrefix;
            }

            function findInlineRows(prefix){
                // tabular: tr.form-row ; stacked: div.form-row
                return $('.inline-related .form-row').filter(function(){
                var id = this.id || '';
                return id.indexOf(prefix + '-') === 0;
                });
            }

            function findField($row, field){ return $row.find('[name$="-' + field + '"]'); }

            function getFieldText($row, field){
                // tabular: td.field-xxx ; stacked: .field-xxx (texte brut)
                return $row.find('td.field-' + field + ', .field-' + field).text().trim();
            }

            // -------------------------------
            // 1) Gestion "mode ajustement"
            // -------------------------------

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

            // ----------------------------------------
            // 2) Bouton "Calculer les ajustements"
            // ----------------------------------------

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

            // ----------------------------------------
            // 3) Appel API d’adaptation 
            // ----------------------------------------

            // Extrait l’ID de recette depuis l’URL admin Django (ex: /admin/pastry_app/recipe/123/change/)
            function getRecipeIdFromURL() {
                const match = window.location.pathname.match(/\/recipe\/(\d+)\/change\//);
                return match ? match[1] : null;
            }

            // CSRF (si vue non exemptée)
            function getCookie(name){
                const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
                return m ? m.pop() : '';
            }

            // Logique d’ajustement (à coder selon tes besoins)
            function ajusterQuantites() {
                // Récupère valeurs actuelles du pan/servings
                const recipeId = $('#id_recipe_id').val() || getRecipeIdFromURL();
                const pan = $('#id_pan').val();
                const servingsMin = $('#id_servings_min').val();
                // Construire le payload
                const data = {recipe_id: recipeId, target_pan_id: pan, target_servings: servingsMin};
                // URL robuste: injectée via base_site.html, sinon fallback
                const RECIPES_ADAPT_ENDPOINT = window.APP_API_RECIPES_ADAPT || '/api/recipes-adapt/';

                // Appel AJAX vers /api/recipes-adapt/
                $.ajax({
                    type: "POST",
                    url: RECIPES_ADAPT_ENDPOINT,
                    data: JSON.stringify(data),
                    contentType: "application/json",
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    xhrFields: { withCredentials: true },
                    success: function (response) {
                        // Mise à jour des quantités dans la page (inlines ingrédients)
                        updateQuantitiesFromResponse(response);
                    },
                    error: function (xhr) {alert("Erreur lors de l’ajustement : " + xhr.responseText); }
                });
            }

            // ----------------------------------------
            // 4) Màj des inlines + Synthèse arborescente
            // ----------------------------------------

            // Normalise la réponse pour accepter plat ou arbre
            function normalizeTree(resp) {
                if (!resp) return { ingredients: [], subrecipes: [] };
                if (resp.tree) return resp.tree;
                return {
                ingredients: resp.ingredients || [],
                subrecipes:  resp.subrecipes || resp.children || []
                };
            }

            const ING_PREFIX = getInlinePrefix('recipe_ingredients');

            function updateInlineRow(adapted){
                const ingredientId   = Number(adapted.ingredient);
                const displayName = String(adapted.display_name || '').trim();
                const newQuantity  = adapted.scaled_quantity;

                findInlineRows(ING_PREFIX).each(function(){
                const row = (this);
                const currentIngredientId   = Number(findField(row, 'ingredient').val());
                const currentDisplayName = getFieldText(row, 'display_name');
                if (currentIngredientId === ingredientId && currentDisplayName === displayName) {
                    const qty = findField(row, 'quantity');
                    qty.val(newQuantity);
                    qty.css('background-color', '#e5ffe5').animate({ backgroundColor: '#fff' }, 1000);
                }
                });
            }

            // Met à jour une ligne inline pour un ingrédient, logique d’origine conservée

            // function updateInlineRow(adapted) {
            //     const ingredientId = adapted.ingredient;
            //     const displayName  = (adapted.display_name || '').trim();
            //     const newQuantity  = adapted.scaled_quantity;

            //     $('tr.form-row[id^="recipe_ingredients-"]').each(function () {
            //     const $row = $(this);
            //     const $ingredientSelect = $row.find('select[name$="-ingredient"]');
            //     const currentIngredientId = parseInt($ingredientSelect.val());
            //     const currentDisplayName  = $row.find('td.field-display_name p').text().trim();

            //     if (currentIngredientId === ingredientId && currentDisplayName === displayName) {
            //         const $qty = $row.find('input[name$="-quantity"]');
            //         $qty.val(newQuantity);
            //         $qty.css('background-color', '#e5ffe5').animate({ backgroundColor: '#fff' }, 1000);
            //     }
            //     });
            // }

            // Parcours récursif: met à jour inlines pour tous les niveaux
            function walkAndUpdate(node) {
                (node.ingredients || []).forEach(updateInlineRow);
                (node.subrecipes || []).forEach(function (sr) { walkAndUpdate(sr); });
            }

            // Rendu HTML arborescent dans le fieldset de synthèse (non intrusif)
            function renderSynthesis(root) {
                var $fs = $('.field-recipe_subrecipes_synthesis').closest('fieldset'); // fieldset déjà présent côté admin :contentReference[oaicite:2]{index=2}
                if ($fs.length === 0) return;

                var $box = $('#synthesis-tree');
                if ($box.length === 0) {
                $box = $('<div id="synthesis-tree" class="module aligned" style="margin-top:8px;"></div>');
                $fs.append($box);
                }
                $box.html(buildTreeHTML(root));
            }

            function esc(s){ 
                return String(s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); 
            }

            function buildTreeHTML(node) {
                const html = '<ul>';

                (node.ingredients || []).forEach(function(i){
                    const name = esc(i.display_name || i.name || '');
                    const qty  = (i.scaled_quantity != null ? i.scaled_quantity : i.quantity);
                    const unit = esc(i.unit || '');
                    html += '<li>' + name + (qty != null ? ' — ' + qty : '') + (unit ? ' ' + unit : '') + '</li>';
                });

                (node.subrecipes || []).forEach(function(sr){
                    const title = esc(sr.recipe_name || sr.name || ('Sous-recette ' + (sr.id || sr.recipe_id || '')));
                    html += '<li><strong>' + title + '</strong>' + buildTreeHTML(sr) + '</li>';
                });

                html += '</ul>';
                return html;
            }

            // Entrée unique appelée après succès API
            function updateQuantitiesFromResponse(response) {
                const root = normalizeTree(response);
                // Compat plat: si aucune structure et pas d’ingrédients, on ne fait rien
                if (!root.ingredients && !root.subrecipes) return;

                walkAndUpdate(root);     // met à jour toutes les lignes inline
                renderSynthesis(root);   // affiche la synthèse hiérarchique

                // feedback visuel comme avant
                $('.messages').append('<div class="success">Quantités ajustées !</div>'); 
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