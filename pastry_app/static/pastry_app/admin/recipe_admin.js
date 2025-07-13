(function waitForJquery(){
    if (typeof django !== "undefined" && typeof django.jQuery === "function") {

        // On attend que le DOM admin Django soit chargé, et on utilise le jQuery intégré par Django
        (function($) {
            $(document).ready(function(){

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