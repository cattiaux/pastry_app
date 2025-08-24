/**
 * Autocomplete simple pour la barre de recherche de n'importe quel changelist admin.
 * - Injecte un <datalist> sur l'input #searchbar.
 * - À chaque saisie (>= 2 chars), requête GET sur /admin/.../<model>/suggest/?q=...
 * - Remplit le datalist avec les 10 premiers libellés retournés.
 */

(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function() {

            /**
             * Crée (ou récupère) un <datalist> et l'associe à l'input de recherche.
             * @param {HTMLInputElement} input - La barre de recherche admin (#searchbar).
             * @returns {HTMLDataListElement} - Le datalist prêt à être rempli.
             */
            function ensureDatalist(input) {
                let listId = 'admin-search-suggest';
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
             * Retourne l’URL de l’endpoint de suggestion.
             * Priorité: data-suggest injecté par le template (calculé via reverse()).
             * Fallback: URL relative "suggest/" basée sur la page courante.
             */
            function apiSuggest() {
                // Priorité au data-suggest injecté par le template, sinon fallback relatif
                const n = document.getElementById('admin-api');
                return (n && n.dataset && n.dataset.suggest) ? n.dataset.suggest : new URL('suggest/', location.href).toString();
            }
            const SUGGEST_URL = apiSuggest();

            /**
             * Appelle l’endpoint JSON des suggestions et transmet les résultats.
             * @param {string} q Terme de recherche.
             * @param {(results: string[]) => void} cb Callback recevant la liste de libellés.
             */
            function fetchSuggestions(q, cb) {
                if (!SUGGEST_URL) { console.warn('[suggest JS] empty suggest URL'); return cb([]); }

                // IMPORTANT: fournir une base à new URL() si on reçoit un chemin absolu "/…"
                const u = new URL(SUGGEST_URL, window.location.href);
                u.searchParams.set('q', q);
                fetch(u.toString(), {credentials: 'same-origin', headers: { 'Accept': 'application/json'} })
                    .then(r => (!r.ok ? Promise.reject() : r))
                    .then(r => (r.headers.get('content-type') || '').includes('application/json') ? r.json() : Promise.reject())
                    .then(data => cb(Array.isArray(data.results) ? data.results : []))
                    .catch(() => cb([]))
            }

            /**
             * Point d'entrée:
             * - Récupère #searchbar.
             * - Monte le datalist.
             * - Écoute input avec un debounce léger pour limiter les requêtes réseau.
             */
            function init() {
                // Ne s'active que si on est sur une page admin list (présence #searchbar)
                const input = document.getElementById('searchbar') || document.querySelector('input[name="q"]'); // barre admin
                if (!input) return;  // pas de search_fields → rien à faire

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


