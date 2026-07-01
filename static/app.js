const form = document.getElementById("extract-form");
const urlInput = document.getElementById("url-input");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const recipeEl = document.getElementById("recipe");
const titleEl = document.getElementById("recipe-title");
const yieldEl = document.getElementById("recipe-yield");
const ingredientsGroups = document.getElementById("ingredients-groups");
const measurementHints = document.getElementById("measurement-hints");
const measurementHintsBody = document.getElementById("measurement-hints-body");
const stepsList = document.getElementById("steps-list");

const STORAGE_KEY = "receptHyveln:lastRecipe";

function showStatus(message, type) {
  statusEl.hidden = false;
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function hideStatus() {
  statusEl.hidden = true;
  statusEl.className = "status";
}

function renderIngredientGroups(groups) {
  ingredientsGroups.replaceChildren(
    ...groups.map((group) => {
      const wrapper = document.createElement("div");
      wrapper.className = "ingredient-group";

      if (group.title) {
        const heading = document.createElement("h4");
        heading.className = "ingredient-group-title";
        heading.textContent = group.title;
        wrapper.appendChild(heading);
      }

      const list = document.createElement("ul");
      list.className = "ingredients-list";
      list.replaceChildren(
        ...group.ingredients.map((item) => {
          const li = document.createElement("li");
          li.textContent = item;
          return li;
        })
      );
      wrapper.appendChild(list);
      return wrapper;
    })
  );
}

function renderMeasurementHints(hints) {
  if (!hints?.length) {
    measurementHints.hidden = true;
    measurementHintsBody.replaceChildren();
    return;
  }

  measurementHintsBody.replaceChildren(
    ...hints.map((hint) => {
      const row = document.createElement("tr");
      const fromCell = document.createElement("td");
      const toCell = document.createElement("td");
      fromCell.textContent = hint.from;
      toCell.textContent = hint.to;
      row.append(fromCell, toCell);
      return row;
    })
  );
  measurementHints.hidden = false;
}

function renderRecipe(recipe) {
  titleEl.textContent = recipe.title;
  yieldEl.textContent = recipe.yield || "";
  yieldEl.hidden = !recipe.yield;

  const groups = recipe.ingredient_groups?.length
    ? recipe.ingredient_groups
    : [{ title: null, ingredients: recipe.ingredients || [] }];
  renderIngredientGroups(groups);
  renderMeasurementHints(recipe.measurement_hints);

  stepsList.replaceChildren(
    ...recipe.steps.map((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      return li;
    })
  );

  recipeEl.hidden = false;
}

function saveRecipe(recipe, url) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ recipe, url }));
  } catch {
    // sessionStorage may be unavailable
  }
}

function loadSavedRecipe() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const { recipe, url } = JSON.parse(raw);
    if (recipe && url) {
      urlInput.value = url;
      renderRecipe(recipe);
    }
  } catch {
    // ignore corrupt storage
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = urlInput.value.trim();
  if (!url) return;

  submitBtn.disabled = true;
  recipeEl.hidden = true;
  showStatus("Hämtar recept…", "loading");

  try {
    const response = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join(", ")
          : "Något gick fel.";
      throw new Error(message);
    }

    hideStatus();
    renderRecipe(data);
    saveRecipe(data, url);
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    submitBtn.disabled = false;
  }
});

loadSavedRecipe();
