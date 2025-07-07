(function waitForJquery(){
    if (typeof django !== "undefined" && typeof django.jQuery === "function") {

        (function($) {
            $(document).ready(function() {

                console.log("jQuery dans pan_admin.js fonctionne (delayed) !");

                // Affiche/masque les champs du formulaire selon la valeur de pan_type
                function updatePanFields() {
                    var panType = $('#id_pan_type').val(); // Récupère la valeur du champ type de moule

                    // On cache d'abord tous les champs de dimensions et volume
                    $('#id_diameter').closest('.form-row').hide();
                    $('#id_height').closest('.form-row').hide();
                    $('#id_length').closest('.form-row').hide();
                    $('#id_width').closest('.form-row').hide();
                    $('#id_rect_height').closest('.form-row').hide();
                    $('#id_volume_raw').closest('.form-row').hide();
                    $('#id_is_total_volume').closest('.form-row').hide();
                    $('#id_unit').closest('.form-row').hide();
                    $('#id_units_in_mold').closest('.form-row').hide(); // Par défaut, units_in_mold caché (sauf pour custom)

                    // Afficher les champs selon le type sélectionné
                    if (panType === 'ROUND') {
                        $('#id_diameter').closest('.form-row').show();
                        $('#id_height').closest('.form-row').show();
                        $('#id_units_in_mold').val(1); // units_in_mold est forcé à 1 pour ROUND
                    } else if (panType === 'RECTANGLE') {
                        $('#id_length').closest('.form-row').show();
                        $('#id_width').closest('.form-row').show();
                        $('#id_rect_height').closest('.form-row').show();
                        $('#id_units_in_mold').val(1); // units_in_mold est forcé à 1 pour RECTANGLE
                    } else if (panType === 'CUSTOM') {
                        $('#id_volume_raw').closest('.form-row').show();
                        $('#id_is_total_volume').closest('.form-row').show();
                        $('#id_unit').closest('.form-row').show();
                        $('#id_units_in_mold').closest('.form-row').show(); // Editable pour CUSTOM
                    }
                    updateIsTotalVolume(); // On met aussi à jour la case volume total
                }

                // Gère l'état (coché/désactivé) de la case is_total_volume selon units_in_mold et pan_type
                function updateIsTotalVolume() {
                    var units = parseInt($('#id_units_in_mold').val());
                    var panType = $('#id_pan_type').val();
                    if (units === 1 || panType !== 'CUSTOM') {
                        $('#id_is_total_volume').prop('checked', true);
                        $('#id_is_total_volume').attr('disabled', 'disabled');
                    } else {
                        $('#id_is_total_volume').removeAttr('disabled'); // Editable seulement si CUSTOM et >1
                    }
                }

                // Rafraîchir lors du changement de pan_type ou units_in_mold
                $('#id_pan_type').change(function() {
                    updatePanFields();
                });

                // Quand on change le nombre d'unités, on met à jour la case à cocher volume total
                $('#id_units_in_mold').change(function() {
                    updateIsTotalVolume();
                });

                // Initialisation à l'ouverture
                updatePanFields();
            });
        })(django.jQuery);

    } else {
        setTimeout(waitForJquery, 100);
    }
})();
