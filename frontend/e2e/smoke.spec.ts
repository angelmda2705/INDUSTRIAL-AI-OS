import { expect, test } from "@playwright/test";

const EMAIL = process.env.E2E_EMAIL ?? "ana@ejemplo.test";
const PASSWORD = process.env.E2E_PASSWORD ?? "";
const SCREENSHOT_DIR = process.env.E2E_SCREENSHOT_DIR ?? "test-results";

test.skip(!PASSWORD, "Set E2E_EMAIL and E2E_PASSWORD for an existing organization administrator.");

test("login → demo data → findings workflow → import wizard → report → logout", async ({ page }) => {
  // Protected pages redirect to login without a session
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);

  // Wrong password shows a generic, actionable error
  await page.getByLabel("Correo electrónico").fill(EMAIL);
  await page.getByLabel("Contraseña").fill("incorrecta-123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Correo o contraseña incorrectos" })).toBeVisible();

  await page.getByLabel("Contraseña").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Panel ejecutivo" })).toBeVisible();

  // Empty state offers clearly-labelled demo data
  const loadDemo = page.getByRole("button", { name: "Cargar datos de demostración" });
  if (await loadDemo.isVisible()) {
    await loadDemo.click();
  }
  await expect(page.getByText("Indicadores clave")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("datos de demostración").first()).toBeVisible();
  await expect(page.getByText("Problemas prioritarios")).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/dashboard.png`, fullPage: true });

  // Findings: open one and move it through the workflow
  await page.getByRole("link", { name: "Hallazgos" }).first().click();
  await expect(page.getByRole("heading", { name: "Hallazgos" })).toBeVisible();
  await page.locator("table a").first().click();
  await expect(page.getByText("Evidencia")).toBeVisible();
  // Pick any allowed transition that does not require a closing note (state depends on earlier runs).
  const statusSelect = page.getByLabel("Cambiar estado");
  const choices = await statusSelect.locator("option").evaluateAll((opts) =>
    opts.map((o) => (o as HTMLOptionElement).value).filter((v) => v && v !== "resolved" && v !== "dismissed"),
  );
  await statusSelect.selectOption(choices[0]);
  await page.getByLabel("Comentario").fill("Revisión asignada en prueba E2E");
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Revisión asignada en prueba E2E").first()).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/finding.png`, fullPage: true });

  // Import wizard with a small production file (one invalid row)
  const suffix = Date.now();
  const csv = [
    "Fecha,Línea,Piezas buenas,Scrap,Cantidad planeada",
    "01/03/2025,L1,90,5,100",
    "02/03/2025,L1,95,2,100",
    "03/03/2025,L2,abc,1,100",
  ].join("\n");
  await page.goto("/imports/new");
  await page.getByTestId("file-input").setInputFiles({ name: `produccion_${suffix}.csv`, mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Cargar y analizar columnas" }).click();
  await expect(page.getByText("Vista previa")).toBeVisible();
  await page.getByRole("radio", { name: /Registros de producción/ }).click();
  await expect(page.getByLabel(/Centro de trabajo/)).toHaveValue("Línea");
  await page.getByLabel("Nombre del conjunto").fill(`E2E producción ${suffix}`);
  await page.getByRole("button", { name: "Validar todos los renglones" }).click();
  await expect(page.getByText("Resultado de la validación")).toBeVisible();
  await expect(page.getByText("Se esperaba un número")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar importación" }).click();
  await expect(page.getByText(/Importación confirmada: 2 renglones/)).toBeVisible({ timeout: 60_000 });

  // Report generation and download
  await page.goto("/reports");
  await page.getByLabel("Excel").check();
  await page.getByRole("button", { name: "Generar" }).click();
  const link = page.getByRole("link", { name: "Descargar" }).first();
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  const res = await page.request.get(href!);
  expect(res.status()).toBe(200);
  expect((await res.body()).subarray(0, 2).toString()).toBe("PK");

  // Logout ends the session
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
