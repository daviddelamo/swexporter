/**
 * SWADE PDF Character Exporter — Foundry VTT Module
 * ====================================================
 * Adds an "Export PDF" button to SWADE character sheets.
 * Sends actor data + portrait to an external FastAPI server
 * and triggers a PDF download.
 */

const MODULE_ID = "swade-pdf-exporter";

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
});

// ─────────────────────────────────────────────────
// Inject Export Button — Method 1: Header Buttons Hook
// ─────────────────────────────────────────────────

Hooks.on("getActorSheetHeaderButtons", (sheet, buttons) => {
  // Only add to character sheets for the SWADE system
  if (sheet.actor?.type !== "character") return;

  // Only show if the user owns the character
  if (!sheet.actor.isOwner) return;

  console.log(`${MODULE_ID} | Adding header button for ${sheet.actor.name}`);

  buttons.unshift({
    label: game.i18n.localize("SWADE_PDF.ExportPDF"),
    class: "swade-pdf-export-header",
    icon: "fas fa-file-pdf",
    onclick: () => exportCharacterPDF(sheet.actor),
  });
});

// ─────────────────────────────────────────────────
// Inject Export Button — Method 2: DOM Injection Fallback
// Works with both AppV1 (jQuery) and AppV2 (vanilla DOM)
// ─────────────────────────────────────────────────

Hooks.on("renderActorSheet", (app, html, data) => {
  // Only target character sheets
  if (app.actor?.type !== "character") return;
  if (!app.actor.isOwner) return;

  // Convert to jQuery if needed (AppV2 passes vanilla DOM element)
  const $html = html instanceof jQuery ? html : $(html);

  // Check if button already exists (avoid duplicates)
  if ($html.find(".swade-pdf-export-btn").length > 0) return;

  console.log(`${MODULE_ID} | Injecting DOM button for ${app.actor.name}`);

  // Create the export button
  const $btn = $(`<a class="swade-pdf-export-btn" title="${game.i18n.localize("SWADE_PDF.ExportPDF")}">
    <i class="fas fa-file-pdf"></i> ${game.i18n.localize("SWADE_PDF.ExportPDF")}
  </a>`);

  $btn.on("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    exportCharacterPDF(app.actor);
  });

  // Try multiple injection points for compatibility with different SWADE sheet versions
  const injectionTargets = [
    ".window-header .window-title",           // Standard Foundry header
    ".window-header .header-button",          // Near other header buttons
    ".window-header",                          // Fallback: append to header
    ".charname",                               // SWADE character name area
    "header.sheet-header",                     // Generic sheet header
  ];

  let injected = false;
  for (const selector of injectionTargets) {
    const $target = $html.closest(".app").find(selector);
    if ($target.length > 0) {
      if (selector.includes("window-title") || selector.includes("charname")) {
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
    // Last resort: try the parent window
    const $window = $html.closest(".app").find(".window-header");
    if ($window.length) {
      $window.append($btn);
      console.log(`${MODULE_ID} | Button injected at window-header (fallback)`);
    } else {
      console.warn(`${MODULE_ID} | Could not find injection point for export button`);
    }
  }
});

// ─────────────────────────────────────────────────
// PDF Export Logic
// ─────────────────────────────────────────────────

/**
 * Fetches the character portrait as a base64 data URL.
 * @param {string} imgPath - Relative image path from the actor
 * @returns {Promise<string|null>} Base64 data URL or null
 */
async function fetchPortraitBase64(imgPath) {
  if (!imgPath || imgPath === "icons/svg/mystery-man.svg") return null;

  try {
    // Build the full URL to the image
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

/**
 * Main export function: collects actor data, sends to API, downloads PDF.
 * @param {Actor} actor - The Foundry VTT actor to export
 */
async function exportCharacterPDF(actor) {
  const apiUrl = game.settings.get(MODULE_ID, "apiUrl");

  if (!apiUrl) {
    ui.notifications.error(game.i18n.localize("SWADE_PDF.ErrorConnection"));
    return;
  }

  // Show generating notification
  ui.notifications.info(
    game.i18n.localize("SWADE_PDF.Generating"),
    { permanent: false }
  );

  try {
    // 1. Serialize actor data (full JSON including items)
    const actorData = actor.toObject();
    console.log(`${MODULE_ID} | Exporting actor:`, actorData.name, `(${actorData.items?.length || 0} items)`);

    // 2. Fetch portrait as base64
    const imgBase64 = await fetchPortraitBase64(actor.img);
    console.log(`${MODULE_ID} | Portrait:`, imgBase64 ? "fetched" : "none");

    // 3. Build request payload
    const payload = {
      actor_data: actorData,
      img_base64: imgBase64,
    };

    // 4. Send to API
    console.log(`${MODULE_ID} | Sending to API: ${apiUrl}/generate-pdf`);
    const response = await fetch(`${apiUrl}/generate-pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server responded with ${response.status}: ${errorText}`);
    }

    // 5. Download the PDF
    const pdfBlob = await response.blob();
    const charName = actor.name.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_");
    const filename = `${charName}.pdf`;

    // Create download link
    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    // Show success
    ui.notifications.info(game.i18n.localize("SWADE_PDF.Success"));

  } catch (err) {
    console.error(`${MODULE_ID} | Export error:`, err);
    ui.notifications.error(
      `${game.i18n.localize("SWADE_PDF.Error")}: ${err.message}`
    );
  }
}
