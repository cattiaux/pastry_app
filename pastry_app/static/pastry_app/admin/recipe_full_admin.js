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
  if (typeof window.django !== "undefined" && typeof django.jQuery !== "undefined") {

    (function(_$jq){ // on n'utilise pas jQuery ici mais on attend sa présence (admin ready)

      window.addEventListener('error', e => console.error('[full] window error:', e.error || e.message));
      window.addEventListener('unhandledrejection', e => console.error('[full] unhandled:', e.reason));

      "use strict";

      // -----------------------------
      // 2) Helpers utilitaires
      // -----------------------------
      const qs  = (sel, ctx) => (ctx||document).querySelector(sel);
      const qsa = (sel, ctx) => Array.from((ctx||document).querySelectorAll(sel));
      const esc = s => String(s ?? "").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
      const getCookie = (name) => {
        const m = document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)');
        return m ? m.pop() : "";
      };

      // Crée un bouton simple
      function makeBtn(text, className, onClick){
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = text;
        if (className) b.className = className;
        b.addEventListener("click", onClick);
        return b;
      }

      // Ligne ingrédient editable
      function makeIngredientRow(item, sourceRecipeId){
        // if (!item) console.warn('[full] makeIngredientRow item=undefined');
        const li = document.createElement("li");
        li.className = "fe-item fe-ing-item";
        li.dataset.riId = item.ri_id || "";
        li.dataset.sourceRecipeId = String(item.source_recipe_id || sourceRecipeId || "");
        li.innerHTML = `
          <input class="fe-ing-id" type="hidden" value="${item.ingredient_id||''}">
          <input class="fe-ing-name" type="text" placeholder="Nom affiché" value="${esc(item.display_name||'')}">
          <input class="fe-ing-qty" type="number" step="any" placeholder="Qté" value="${item.quantity ?? ''}">
          <input class="fe-ing-unit" type="text" placeholder="Unité" value="${esc(item.unit||'')}">
          <button type="button" class="fe-del" title="Supprimer">✕</button>
        `;
        qs(".fe-del", li).onclick = () => li.remove();
        return li;
      }

      // Ligne étape editable
      function makeStepRow(s, sourceRecipeId){
        // if (!s) console.warn('[full] makeStepRow s=undefined');
        const li = document.createElement("li");
        li.className = "fe-item fe-step-item";
        li.dataset.stepId = s.step_id || "";
        li.dataset.sourceRecipeId = String(s.source_recipe_id || sourceRecipeId || "");
        li.innerHTML = `
          <input class="fe-step-order" type="number" step="1" value="${parseInt(s.order ?? s.step_number ?? 0,10)}">
          <input class="fe-step-text" type="text" placeholder="Instruction" value="${esc(s.text || s.instruction || '')}">
          <button type="button" class="fe-del" title="Supprimer">✕</button>
        `;
        qs(".fe-del", li).onclick = () => li.remove();
        return li;
      }

      // -----------------------------
      // 3) Rendu (colonne, nœud, arbre)
      // -----------------------------

      // Rend une colonne pour un nœud de l'arbre
      function buildColumn(node){
        // console.log('[full] buildColumn', node?.recipe_id);
        const wrap = document.createElement("div");
        wrap.className = "fe-col";
        wrap.dataset.recipeId = String(node.recipe_id);

        const title = esc(node.recipe_name || `Recipe #${node.recipe_id}`);
        // Toolbar locale (ajout ingrédient/étape pour CE nœud)
        wrap.innerHTML = `
          <h3 style="margin-top:0">${title}</h3>
          <div class="fe-col-toolbar" style="margin-bottom:.5rem"></div>
          <b>Ingrédients</b>
          <ul class="fe-ings"></ul>
          <b>Étapes</b>
          <ol class="fe-steps"></ol>
        `;

        const colTb = qs(".fe-col-toolbar", wrap);
        const ul    = qs(".fe-ings", wrap);
        const ol    = qs(".fe-steps", wrap);

        // remplit les listes
        (node.ingredients || []).forEach(i => ul.appendChild(makeIngredientRow(i, node.recipe_id)));
        (node.steps || []).forEach(s => ol.appendChild(makeStepRow(s, node.recipe_id)));

        // boutons "ajouter" propres à ce nœud
        colTb.appendChild(makeBtn("Ajouter ingrédient", "fe-add fe-add-ingredient", () => {
          ul.appendChild(makeIngredientRow({quantity:"", unit:"", display_name:""}, node.recipe_id));
        }));
        colTb.appendChild(makeBtn("Ajouter étape", "fe-add fe-add-step", () => {
          const next = qsa(".fe-step-item", wrap).length + 1;
          ol.appendChild(makeStepRow({order: next, text:""}, node.recipe_id));
        }));

        return wrap;
      }

      // Rend récursivement l'arbre (racine puis sous-recettes)
      function renderTree(rootEl, tree){
        rootEl.innerHTML = "";
        function visit(node){
            // console.log('[full] visit node',
            // 'id=', node?.recipe_id,
            // 'ings=', (node?.ingredients||[]).length,
            // 'steps=', (node?.steps||[]).length,
            // 'subs=', (node?.subrecipes||[]).length
            // );
            rootEl.appendChild(buildColumn(node));
            (node.subrecipes || []).forEach(visit);
        }
        visit(tree);
      }

      // -----------------------------
      // 4) Actions (global toolbar)
      // -----------------------------
      function attachGlobalToolbar(rootEl, rootId){
        const globalBar = qs(".fe-toolbar", rootEl);
        if (!globalBar) return;

        // Ajout global = sur la colonne racine uniquement
        const rootCol = qs(`.fe-col[data-recipe-id="${rootId}"]`, rootEl) || qs(".fe-col", rootEl);
        if (!rootCol) return;

        const rootUl = qs(".fe-ings", rootCol);
        const rootOl = qs(".fe-steps", rootCol);

        const addIngBtn  = qs("#fe-add-ingredient", rootEl);
        const addStepBtn = qs("#fe-add-step", rootEl);

        if (addIngBtn)  addIngBtn.onclick  = () => rootUl.appendChild(makeIngredientRow({quantity:"", unit:"", display_name:""}, rootId));
        if (addStepBtn) addStepBtn.onclick = () => {
          const next = qsa(".fe-step-item", rootCol).length + 1;
          rootOl.appendChild(makeStepRow({order: next, text:""}, rootId));
        };
      }

      // -----------------------------
      // 5) Sauvegarde
      // -----------------------------
      function collectPayload(rootEl){
        // Parcourt toutes les colonnes et lignes pour produire les "flats"
        const ingRows  = qsa(".fe-ing-item", rootEl);
        const stepRows = qsa(".fe-step-item", rootEl);

        const flat_ingredients = ingRows.map(li => ({
          ri_id: li.dataset.riId || null,
          source_recipe_id: parseInt(li.dataset.sourceRecipeId || "0", 10) || null,
          ingredient_id: parseInt(qs(".fe-ing-id", li)?.value || "0", 10) || null,
          display_name: qs(".fe-ing-name", li)?.value || null,
          quantity: parseFloat(qs(".fe-ing-qty", li)?.value || "0"),
          unit: qs(".fe-ing-unit", li)?.value || "",
        }));

        const flat_steps = stepRows.map(li => ({
          step_id: li.dataset.stepId || null,
          source_recipe_id: parseInt(li.dataset.sourceRecipeId || "0", 10) || null,
          order: parseInt(qs(".fe-step-order", li)?.value || "0", 10),
          text: qs(".fe-step-text", li)?.value || "",
        }));
        
        // console.log('[full] collectPayload',
        // 'ings=', flat_ingredients.length,
        // 'steps=', flat_steps.length
        // );
        return { flat_ingredients, flat_steps };
      }

      async function saveAll(rootEl, applyUrl){
        const payload = collectPayload(rootEl);
        const csrftoken = getCookie("csrftoken");
        const res = await fetch(applyUrl, {
          method: "POST",
          headers: {"Content-Type":"application/json", "X-CSRFToken": csrftoken},
          body: JSON.stringify(payload),
          credentials: "same-origin",
        });
        // console.log('[full] save HTTP', res.status);
        let data = {};
        try { data = await res.json(); } catch(_){}
        return { ok: res.ok, data, status: res.status };
      }

      // -----------------------------
      // 6) Init
      // -----------------------------
      async function init(){
        // console.info('[full] init start');
        const mount = qs("#full-editor"); if (!mount) return;
        // if (!mount) { console.warn('[full] no mount'); return; }
        // console.log('[full] dataset:', mount.dataset);

        const rootId  = parseInt(mount.dataset.rootId || "0", 10) || null;
        const fullUrl = mount.dataset.fullUrl;
        const applyUrl= mount.dataset.applyUrl;

        // Page Add → pas d'init
        if (!fullUrl || !applyUrl || !rootId){
          const s = qs("#fe-status", mount);
          if (s) s.textContent = "Éditeur inactif en création. Enregistrez d’abord.";
          return;
        }

        // Récupère l'arbre canonique
        let data;
        try {
            // console.log('[full] GET', fullUrl);
            const resp = await fetch(fullUrl, { credentials: "same-origin", headers: { "X-Admin-Context": "1" }, });   // signale le contexte admin
            // console.log('[full] HTTP status', resp.status);
            // const clone = resp.clone();
            // try { data = await resp.json(); }
            // catch (e) {
            // const raw = await clone.text();
            // console.warn('[full] non-JSON body sample:', raw.slice(0,200));
            // throw e;
            // }
            // console.log('[full] keys:', Object.keys(data||{}));
            // console.log('[full] counts:', 
            // 'flat_ingredients=', (data.flat_ingredients||[]).length,
            // 'flat_steps=', (data.flat_steps||[]).length,
            // 'tree?', !!data.tree
            // );

            data = await resp.json();
        } catch (e) {
          console.warn("[full] fetch error", e);
          const s = qs("#fe-status", mount);
          if (s) s.textContent = "Erreur de chargement.";
          return;
        }

        const tree = data && data.tree ? data.tree : {};
        const cols = qs(".fe-columns", mount) || mount;

        // console.time('[full] renderTree');

        // try { renderTree(cols, tree); }
        // catch (e) { console.error('[full] renderTree error:', e); cols.innerHTML = '<em>Erreur de rendu.</em>'; }
        // console.timeEnd('[full] renderTree');

        // Rendu de l'arbre (colonnes)
        renderTree(cols, tree);

        // Toolbar globale (root only)
        attachGlobalToolbar(mount, rootId);

        // Save
        const saveBtn = qs("#fe-save", mount);
        const statusEl= qs("#fe-status", mount);
        if (saveBtn){
          saveBtn.onclick = async () => {
            if (statusEl) statusEl.textContent = "Sauvegarde…";
            const out = await saveAll(mount, applyUrl);
            if (statusEl) statusEl.textContent = out.ok ? "Enregistré" : ("Erreur: " + (out.data?.error || out.status));
          };
        }
      }

    //   document.addEventListener("DOMContentLoaded", init);
      if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
      } else {
      init(); // DOM déjà prêt → lance tout de suite
      }

    })(django.jQuery);

  } else {
    // Attend que django.jQuery soit dispo (admin)
    setTimeout(waitForDjangoJQuery, 100);
  }
})();
