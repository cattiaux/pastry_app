/**
 * Autocomplete simple pour la barre de recherche du changelist Label.
 * - Injecte un <datalist> sur l'input #searchbar.
 * - À chaque saisie (>= 2 chars), requête GET sur /admin/.../label/suggest/?q=...
 * - Remplit le datalist avec les 10 premiers libellés retournés.
 * - Aucune dépendance externe. Fonctionne uniquement sur /admin/.../label/
 */

(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function() {
            // N'active le script que sur la page de liste des Labels (évite effets de bord).
            if (!/\/admin\/[^/]+\/label\/$/.test(window.location.pathname)) return;

            /**
             * Crée (ou récupère) un <datalist> et l'associe à l'input de recherche.
             * @param {HTMLInputElement} input - La barre de recherche admin (#searchbar).
             * @returns {HTMLDataListElement} - Le datalist prêt à être rempli.
             */
            function ensureDatalist(input) {
                let listId = 'label-suggest-list';
                let dl = document.getElementById(listId);
                if (!dl) {
                dl = document.createElement('datalist');
                dl.id = listId;
                document.body.appendChild(dl);
                }
                input.setAttribute('list', listId);
                return dl;
            }

            /**
             * Remplace toutes les options du datalist par une liste de suggestions.
             * @param {HTMLDataListElement} dl - Le datalist cible.
             * @param {string[]} items - Les libellés proposés.
             */
            function updateOptions(dl, items) {
                dl.innerHTML = '';
                items.forEach(function(name){
                const opt = document.createElement('option');
                opt.value = name;
                dl.appendChild(opt);
                });
            }

            /**
             * Appelle l'endpoint JSON des suggestions et renvoie les résultats au callback.
             * @param {string} q - Terme de recherche.
             * @param {(results: string[]) => void} cb - Callback recevant un tableau de libellés.
             */
            function fetchSuggestions(q, cb) {
                const url = 'suggest/?q=' + encodeURIComponent(q);
                fetch(url, {credentials: 'same-origin'})
                .then(r => r.ok ? r.json() : {results: []})
                .then(data => cb(Array.isArray(data.results) ? data.results : []))
                .catch(() => cb([]));
            }

            /**
             * Point d'entrée:
             * - Récupère #searchbar.
             * - Monte le datalist.
             * - Écoute input avec un debounce léger pour limiter les requêtes réseau.
             */
            function init() {
                const input = document.getElementById('searchbar'); // barre admin
                if (!input) return;
                const dl = ensureDatalist(input);
                let last = '', timer = null;

                input.addEventListener('input', function() {
                const q = this.value.trim();

                // Pas de requête si trop court ou si inchangé.
                if (q.length < 2 || q === last) return;
                last = q;

                // Petit debounce (150 ms) pour éviter de spammer l'endpoint.
                if (timer) clearTimeout(timer);
                timer = setTimeout(function(){
                    fetchSuggestions(q, function(results){ updateOptions(dl, results); });
                }, 150);
                });
            }

            // Initialise au bon moment selon l'état du DOM.
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', init);
            } else {
                init();
            }
        })(django.jQuery);


    } else {
        // Attend que django.jQuery soit dispo
        setTimeout(waitForDjangoJQuery, 100);
    }
})();