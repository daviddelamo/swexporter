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
    name: game.i18n?.localize("SWADE_PDF.Settings.ApiUrl.Name") ?? "API URL",
    hint: game.i18n?.localize("SWADE_PDF.Settings.ApiUrl.Hint") ?? "URL of the PDF generation server",
    scope: "world",
    config: true,
    type: String,
    default: "http://localhost:5050",
  });
});

Hooks.once("ready", () => {
  console.log(`${MODULE_ID} | SWADE PDF Exporter ready`);
});

// ─────────────────────────────────────────────────
// Inject Export Button into Character Sheets
// ─────────────────────────────────────────────────

Hooks.on("getActorSheetHeaderButtons", (sheet, buttons) => {
  // Only add to character sheets for the SWADE system
  if (sheet.actor?.type !== "character") return;

  // Only show if the user owns the character
  if (!sheet.actor.isOwner) return;

  buttons.unshift({
    label: game.i18n.localize("SWADE_PDF.ExportPDF"),
    class: "swade-pdf-export-header",
    icon: "fas fa-file-pdf",
    onclick: () => exportCharacterPDF(sheet.actor),
  });
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
  if (!imgPath) return null;

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
  const notifId = ui.notifications.info(
    game.i18n.localize("SWADE_PDF.Generating"),
    { permanent: true }
  );

  try {
    // 1. Serialize actor data (full JSON including items)
    const actorData = actor.toObject();

    // 2. Fetch portrait as base64
    const imgBase64 = await fetchPortraitBase64(actor.img);

    // 3. Build request payload
    const payload = {
      actor_data: actorData,
      img_base64: imgBase64,
    };

    // 4. Send to API
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

    // Dismiss generating notification and show success
    ui.notifications.remove(notifId);
    ui.notifications.info(game.i18n.localize("SWADE_PDF.Success"));

  } catch (err) {
    console.error(`${MODULE_ID} | Export error:`, err);
    ui.notifications.remove(notifId);
    ui.notifications.error(
      `${game.i18n.localize("SWADE_PDF.Error")}: ${err.message}`
    );
  }
}
