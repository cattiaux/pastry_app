/**
 * Admin "Full" editor for Recipe.
 * - Récupère /api/recipes/{id}/full (contrat: { tree, flat_* ... }).
 * - Rend une colonne par nœud: racine + sous-recettes récursives.
 * - Édition locale des ingrédients/étapes. Sauvegarde → POST /full-apply/.
 *
 * Dépendances: django.jQuery présent (admin), mais on utilise DOM natif.
 * Sécurité: CSRF via cookie, credentials:same-origin.
 *
 * Sections:
 *   1) Bootstrap (attente de django.jQuery)
 *   2) Helpers utilitaires (DOM, escape, cookie)
 *   3) Rendu (colonne, nœud, arbre)
 *   4) Actions (ajout ligne, suppression)
 *   5) Sauvegarde (collecte → payload → POST)
 *   6) Init (fetch /full, montage, handlers)
 */

(function waitForDjangoJQuery(){
    if(typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

        (function($) {
            function $(sel, ctx){ return (ctx||document).querySelector(sel) }
            function $all(sel, ctx){ return Array.from((ctx||document).querySelectorAll(sel)) }

            function getCookie(name){
                const m = document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)');
                return m ? m.pop() : '';
            }

            function renderIngredient(li, item, rootId){
                li.className = "fe-item";
                li.dataset.riId = item.ri_id || "";
                li.dataset.sourceRecipeId = item.source_recipe_id || rootId || "";
                li.innerHTML = `
                <input class="fe-ing-id" type="hidden" value="${item.ingredient_id||''}">
                <input class="fe-ing-name" type="text" placeholder="Nom affiché" value="${item.display_name||''}">
                <input class="fe-ing-qty" type="number" step="any" placeholder="Qté" value="${item.quantity||''}">
                <input class="fe-ing-unit" type="text" placeholder="Unité" value="${item.unit||''}">
                <button type="button" class="fe-del">✕</button>
                `;
                li.querySelector(".fe-del").onclick = () => li.remove();
            }

            function renderStep(li, s, rootId){
                li.className = "fe-item";
                li.dataset.stepId = s.step_id || "";
                li.dataset.sourceRecipeId = s.source_recipe_id || rootId || "";
                li.innerHTML = `
                <input class="fe-step-order" type="number" step="1" value="${s.order||s.step_number||0}">
                <input class="fe-step-text" type="text" placeholder="Instruction" value="${s.text||s.instruction||''}">
                <button type="button" class="fe-del">✕</button>
                `;
                li.querySelector(".fe-del").onclick = () => li.remove();
            }

            async function init(){
                const root = document.querySelector("#full-editor"); if(!root) return;
                const rootId  = parseInt(root.dataset.rootId || "0", 10) || null;
                const fullUrl = root.dataset.fullUrl;
                const applyUrl = root.dataset.applyUrl;

                // Page Add => pas d'ID, donc pas d'URLs -> on n'initialise pas l'éditeur
                if (!fullUrl || !applyUrl) { // page Add
                    const s = document.querySelector("#fe-status");
                    if (s) s.textContent = "Éditeur inactif en création. Enregistrez d’abord.";
                    return;
                }

                const res = await fetch(fullUrl, {credentials: "same-origin"});
                const data = await res.json();

                const ingUL = document.querySelector("#fe-ingredients");
                (data.flat_ingredients||[]).forEach(it => {
                    const li = document.createElement("li");
                    renderIngredient(li, it, rootId); ingUL.appendChild(li);
                });

                const stepsOL = document.querySelector("#fe-steps");
                (data.flat_steps||[]).forEach(st => {
                    const li = document.createElement("li");
                    renderStep(li, st, rootId); stepsOL.appendChild(li);
                });

                document.querySelector("#fe-add-ingredient").onclick = () => {
                    const li = document.createElement("li");
                    renderIngredient(li, {quantity:"", unit:"", display_name:""}, rootId); ingUL.appendChild(li);
                };
                document.querySelector("#fe-add-step").onclick = () => {
                    const li = document.createElement("li");
                    renderStep(li, {order: ($all(".fe-step-order").length+1), text:""}, rootId); stepsOL.appendChild(li);
                };

                document.querySelector("#fe-save").onclick = async () => {
                    const payload = {
                        flat_ingredients: [...document.querySelectorAll("#fe-ingredients .fe-item")].map(li => ({
                            ri_id: li.dataset.riId || null,
                            source_recipe_id: parseInt(li.dataset.sourceRecipeId || "0", 10) || null,
                            ingredient_id: parseInt(li.querySelector(".fe-ing-id").value || "0", 10) || null,
                            display_name: li.querySelector(".fe-ing-name").value || null,
                            quantity: parseFloat(li.querySelector(".fe-ing-qty").value || "0"),
                            unit: li.querySelector(".fe-ing-unit").value || "",
                        })),
                        flat_steps: $all("#fe-steps .fe-item").map(li => ({
                            step_id: li.dataset.stepId || null,
                            source_recipe_id: parseInt(li.dataset.sourceRecipeId || "0", 10) || null,
                            order: parseInt(li.querySelector(".fe-step-order").value || "0", 10),
                            text: li.querySelector(".fe-step-text").value || "",
                        })),
                    };
                    const csrftoken = getCookie("csrftoken");
                    const r = await fetch(applyUrl, {
                        method: "POST",
                        headers: {"Content-Type":"application/json", "X-CSRFToken": csrftoken},
                        body: JSON.stringify(payload),
                        credentials: "same-origin"
                    });
                    const out = await r.json().catch(() => ({}));
                    document.querySelector("#fe-status").textContent = r.ok ? "Enregistré" : ("Erreur: " + (out.error||r.status));
                };
            }

        document.addEventListener("DOMContentLoaded", init);

        })(django.jQuery);

    } else {
        // Attend que django.jQuery soit dispo
        setTimeout(waitForDjangoJQuery, 100);
    }
})();
