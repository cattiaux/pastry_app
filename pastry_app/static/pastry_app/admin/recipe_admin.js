(function waitForJquery(){
    if (typeof django !== "undefined" && typeof django.jQuery === "function") {

        // On attend que le DOM admin Django soit chargé, et on utilise le jQuery intégré par Django
        (function($) {
            $(document).ready(function(){


                // =======================
                // AJOUT NOTA BENE RECETTE STEPS INLINE (que lors création !)
                // =======================

                // Vérifie qu'on est bien sur la page d'ajout et PAS modification
                if (window.location.pathname.endsWith('/add/')) {
                    // Cible le bloc d'inlines steps
                    var $stepsGroup = $('#steps-group');
                    if ($stepsGroup.length) {
                        // Trouve le titre "Recipe steps"
                        var $header = $stepsGroup.find('fieldset.module > h2').first();
                        if ($header.length && $header.next('.step-warning').length === 0) {
                            // Ajoute le message juste après le titre du bloc
                            $header.after(
                                `<div class="step-warning" style="margin-bottom:8px; color:#a67400; background:#fffbe5; border:1px solid #ffe58f; padding:7px 10px; border-radius:5px;">
                                    <strong>Nota bene :</strong> Pour chaque étape, <b>renseignez explicitement le 'step_number'</b> lors de la création d'une recette dans l’admin.<br>
                                    (L’attribution automatique n’est pas possible ici via l'admin. Laisser vide peut provoquer des erreurs.)
                                </div>`
                            );
                        }
                    }
                }

                // Fonction pour afficher/masquer la ligne du champ adaptation_note selon parent_recipe
                function toggleAdaptationNote() {
                    // Récupère la valeur sélectionnée dans le champ parent_recipe (champ ForeignKey)
                    var parentRecipeSelected = $('#id_parent_recipe').val();
                    // Sélectionne la ligne (form-row) contenant le champ adaptation_note
                    var adaptationNoteRow = $('#id_adaptation_note').closest('.form-row');

                    // Si un parent est sélectionné, on affiche la ligne
                    if (parentRecipeSelected) {
                        adaptationNoteRow.show();
                    } else {
                        // Sinon, on masque la ligne et on vide le champ (évite de sauvegarder une note sans parent)
                        adaptationNoteRow.hide();
                        $('#id_adaptation_note').val('');
                    }
                }

                // On applique une première fois le toggle au chargement de la page (ex : édition)
                toggleAdaptationNote();

                // À chaque fois que l'utilisateur change la valeur de parent_recipe, on applique le toggle
                $('#id_parent_recipe').change(toggleAdaptationNote);
            });
        })(django.jQuery);

            } else {
        setTimeout(waitForJquery, 100);
    }
})();