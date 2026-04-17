/**
 * SWADE PDF Character Exporter — Foundry VTT Module
 * ====================================================
 * Adds an "Export PDF" button to SWADE character sheets.
 * Sends actor data + portrait to an external FastAPI server
 * and triggers a PDF download.
 */

const MODULE_ID = "swade-pdf-exporter";
let _debugHooksEnabled = false;
let _isGeneratingPDF = false;

// ─────────────────────────────────────────────────
// Module Initialization
// ─────────────────────────────────────────────────

Hooks.once("init", () => {
  console.log(`${MODULE_ID} | Initializing SWADE PDF Exporter`);

  // Register module settings
  game.settings.register(MODULE_ID, "apiUrl", {
    name: "SWADE_PDF.Settings.ApiUrl.Name",
    hint: "SWADE_PDF.Settings.ApiUrl.Hint",
    scope: "world",
    config: true,
    type: String,
    default: "http://localhost:3000",
  });
});

Hooks.once("ready", () => {
  console.log(`${MODULE_ID} | SWADE PDF Exporter ready`);
  const apiUrl = game.settings.get(MODULE_ID, "apiUrl");
  console.log(`${MODULE_ID} | API URL configured: ${apiUrl}`);

  // Temporarily enable hook debugging to find the right render hook
  // Run this in the console: game.modules.get("swade-pdf-exporter").debugHooks = true
  // Then open a character sheet and check the console for "HOOK FIRED" messages
});

// ─────────────────────────────────────────────────
// Inject Export Button — Method 1: Header Buttons Hooks
// Try multiple hook names for compatibility
// ─────────────────────────────────────────────────

function addHeaderButton(sheet, buttons) {
  if (sheet.actor?.type !== "character") return;
  if (!sheet.actor.isOwner) return;

  console.log(`${MODULE_ID} | Adding header button for ${sheet.actor.name} via ${sheet.constructor.name}`);

  buttons.unshift({
    label: game.i18n.localize("SWADE_PDF.ExportPDF"),
    class: "swade-pdf-export-header",
    icon: "fas fa-file-pdf",
    onclick: (ev) => exportCharacterPDF(sheet.actor, ev ? ev.currentTarget : null),
  });
}

// Standard Foundry hook
Hooks.on("getActorSheetHeaderButtons", addHeaderButton);

// SWADE-specific hooks that might fire instead
Hooks.on("getSwadeCharacterSheetHeaderButtons", addHeaderButton);
Hooks.on("getSwadeActorSheetHeaderButtons", addHeaderButton);
Hooks.on("getCharacterSheetHeaderButtons", addHeaderButton);

// ─────────────────────────────────────────────────
// Inject Export Button — Method 2: DOM Injection
// Catches ALL render hooks via a broad listener
// ─────────────────────────────────────────────────

function injectDOMButton(app, html, data) {
  // Only target character actor sheets
  if (!app.actor || app.actor.type !== "character") return;
  if (!app.actor.isOwner) return;

  // Convert to jQuery if needed (AppV2 passes vanilla DOM element)
  const $html = html instanceof jQuery ? html : $(html);

  // Get the whole application window element
  const $app = $html.closest(".app").length ? $html.closest(".app") : $html;

  // Check if button already exists (avoid duplicates)
  if ($app.find(".swade-pdf-export-btn").length > 0) return;

  console.log(`${MODULE_ID} | Injecting DOM button for ${app.actor.name} (sheet class: ${app.constructor.name})`);

  // Create the export button
  const btnLabel = game.i18n.localize("SWADE_PDF.ExportPDF");
  const $btn = $(`<a class="swade-pdf-export-btn" title="${btnLabel}">
    <i class="fas fa-file-pdf"></i> ${btnLabel}
  </a>`);

  $btn.on("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    exportCharacterPDF(app.actor, ev.currentTarget);
  });

  // Try multiple injection points
  const headerSelectors = [
    ".window-header .window-title",
    ".window-header",
  ];

  let injected = false;
  for (const selector of headerSelectors) {
    const $target = $app.find(selector);
    if ($target.length > 0) {
      if (selector.includes("window-title")) {
        $target.after($btn);
      } else {
        $target.append($btn);
      }
      injected = true;
      console.log(`${MODULE_ID} | Button injected at: ${selector}`);
      break;
    }
  }

  if (!injected) {
    console.warn(`${MODULE_ID} | Could not find injection point in sheet DOM`);
  }
}

// Register render hooks for multiple possible sheet class names
const renderHooks = [
  "renderActorSheet",
  "renderSwadeCharacterSheet",
  "renderSwadeActorSheet",
  "renderCharacterSheet",
];

for (const hookName of renderHooks) {
  Hooks.on(hookName, (app, html, data) => {
    console.log(`${MODULE_ID} | Hook fired: ${hookName} for ${app?.actor?.name || "unknown"}`);
    injectDOMButton(app, html, data);
  });
}

// ─────────────────────────────────────────────────
// Catch-all: Listen to ALL render hooks to find the right one
// ─────────────────────────────────────────────────

Hooks.on("renderApplication", (app, html, data) => {
  // Check if this is any kind of actor sheet
  if (app.actor && app.actor.type === "character") {
    console.log(`${MODULE_ID} | renderApplication fired for actor sheet: ${app.constructor.name}`);
    injectDOMButton(app, html, data);
  }
});

// AppV2 uses "renderApplicationV2" in some versions
Hooks.on("renderApplicationV2", (app, html, data) => {
  if (app.actor && app.actor.type === "character") {
    console.log(`${MODULE_ID} | renderApplicationV2 fired for actor sheet: ${app.constructor.name}`);
    injectDOMButton(app, html, data);
  }
});

// ─────────────────────────────────────────────────
// PDF Export Logic
// ─────────────────────────────────────────────────

async function fetchPortraitBase64(imgPath) {
  if (!imgPath || imgPath === "icons/svg/mystery-man.svg") return null;

  try {
    const imgUrl = imgPath.startsWith("http")
      ? imgPath
      : `${window.location.origin}/${imgPath}`;

    const response = await fetch(imgUrl);
    if (!response.ok) return null;

    const blob = await response.blob();

    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch (err) {
    console.warn(`${MODULE_ID} | Could not fetch portrait:`, err);
    return null;
  }
}

async function exportCharacterPDF(actor, btnElement = null) {
  if (_isGeneratingPDF) {
    ui.notifications.warn("Por favor espera, la hoja ya se está generando...");
    return;
  }

  const apiUrl = game.settings.get(MODULE_ID, "apiUrl");

  if (!apiUrl) {
    ui.notifications.error(game.i18n.localize("SWADE_PDF.ErrorConnection"));
    return;
  }

  _isGeneratingPDF = true;
  let originalContent = null;
  const $btn = btnElement ? $(btnElement) : null;

  if ($btn && $btn.length) {
    originalContent = $btn.html();
    $btn.html(`<i class="fas fa-spinner fa-spin"></i> Generando...`);
    $btn.css("pointer-events", "none");
    $btn.css("opacity", "0.7");
  }

  ui.notifications.info(game.i18n.localize("SWADE_PDF.Generating"));

  try {
    const actorData = actor.toObject();
    
    // Merge calculated stats that are not in the raw data
    if (actor.system?.stats) {
      actorData.system.stats = foundry.utils.mergeObject(actorData.system.stats || {}, actor.system.stats);
    }
    if (actor.system?.pace) {
      actorData.system.pace = foundry.utils.mergeObject(actorData.system.pace || {}, actor.system.pace);
    }
    
    console.log(`${MODULE_ID} | Exporting:`, actorData.name, `(${actorData.items?.length || 0} items)`);

    const imgBase64 = await fetchPortraitBase64(actor.img);

    const payload = {
      actor_data: actorData,
      img_base64: imgBase64,
    };

    const response = await fetch(`${apiUrl}/generate-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server ${response.status}: ${errorText}`);
    }

    const pdfBlob = await response.blob();
    const charName = actor.name.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_");
    const filename = `${charName}.pdf`;

    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    ui.notifications.info(game.i18n.localize("SWADE_PDF.Success"));

  } catch (err) {
    console.error(`${MODULE_ID} | Export error:`, err);
    ui.notifications.error(`${game.i18n.localize("SWADE_PDF.Error")}: ${err.message}`);
  } finally {
    _isGeneratingPDF = false;
    if ($btn && $btn.length && originalContent) {
      $btn.html(originalContent);
      $btn.css("pointer-events", "auto");
      $btn.css("opacity", "1");
    }
  }
}
