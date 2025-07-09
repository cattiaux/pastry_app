(function waitForJquery(){
    if (typeof django !== "undefined" && typeof django.jQuery === "function") {

        (function($) {
            $(document).ready(function() {
                // Sélecteurs des champs dans le formulaire admin
                let $categoryType = $('#id_category_type');     // Le select du type de catégorie (ingredient, recipe, both)
                let $parentCategory = $('#id_parent_category');     // Le select du parent
                let allOptions = $parentCategory.find('option').clone();    // On garde une copie de toutes les options originales

                // Fonction qui filtre la liste des parents selon le type sélectionné
                function filterParentCategoryOptions() {
                    let type = $categoryType.val(); // Récupère la valeur courante du select type
                    $parentCategory.empty();        // Vide la liste déroulante
                    $parentCategory.append('<option value="">---------</option>');  // Ajoute l'option vide (pour aucun parent)
                    allOptions.each(function() {
                        let opt = $(this);
                        // On suppose que le texte est 'NomCatégorie [TYPE]', exemple : 'Fruits [ingredient]'
                        let optType = opt.text().split('[').pop().split(']')[0]; // Extrait le type entre crochets
                        if (!opt.val()) return; // Ignore l'option vide
                        // Logique de filtrage selon la règle métier :
                        // - "ingredient" ou "recipe" : parent = même type ou both
                        // - "both" : parent = both uniquement
                        if (
                            // Both peut être parent de tout
                            (type === "ingredient" && (optType === "ingredient" || optType === "both")) ||
                            (type === "recipe"    && (optType === "recipe"    || optType === "both")) ||
                            (type === "both"      && (optType === "both"))
                        ) {
                            $parentCategory.append(opt.clone()); // Ajoute l'option autorisée à la liste
                        }
                    });
                }
                
                // Quand l'utilisateur change le type, on recalcule les parents possibles
                $categoryType.change(function() {
                    filterParentCategoryOptions();
                });

                // On applique au chargement initial (ex: en modification)
                filterParentCategoryOptions();
            });
        })(django.jQuery);

    } else {
        setTimeout(waitForJquery, 100);
    }
})();
