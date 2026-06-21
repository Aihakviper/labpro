import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const baseUrl = "http://127.0.0.1:8000";
const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const outputDirectory = path.resolve(".local", "acceptance");
const password = "DemoPassword123!";

await fs.mkdir(outputDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
});

const results = [];

async function login(page, email) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.locator("#login-button").click();
  await page.locator("#app-view:not(.d-none)").waitFor();
  await page.locator("#page-title").waitFor();
}

async function openRoute(page, route, heading) {
  await page.locator(`[data-route="${route}"]`).click();
  await page.waitForURL(`**/#${route}`);
  await page.locator("#page-content").getByRole(
    "heading",
    { name: heading, exact: true },
  ).waitFor();
}

async function runRole(name, email, checks) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.url().startsWith(`${baseUrl}/api/`) && response.status() >= 500) {
      errors.push(`api ${response.status()}: ${response.url()}`);
    }
  });

  try {
    await login(page, email);
    await checks(page);
    await page.screenshot({
      path: path.join(outputDirectory, `${name}.png`),
      fullPage: true,
    });
    assert.deepEqual(errors, [], `${name} browser errors:\n${errors.join("\n")}`);
    results.push(`${name}: PASS`);
  } finally {
    await context.close();
  }
}

await runRole("admin", "admin@librarianpro.ng", async (page) => {
  await page.getByRole("heading", { name: "Library overview" }).waitFor();
  await openRoute(page, "users", "Users & roles");
  await page.getByRole("button", { name: "Create user" }).click();
  await page.locator("#form-modal.show").waitFor();
  await page.getByRole("button", { name: "Cancel" }).click();
  await openRoute(page, "reports", "Reports & analytics");
  await page.getByRole("button", { name: "Inventory" }).click();
  await page.getByText("Total copies", { exact: true }).waitFor();
});

await runRole("librarian", "librarian@librarianpro.ng", async (page) => {
  await page.getByRole("heading", { name: "Library overview" }).waitFor();
  await openRoute(page, "books", "Book catalog");
  await page.getByRole("button", { name: "Add book" }).click();
  await page.locator("#form-modal.show").waitFor();
  await page.getByRole("button", { name: "Cancel" }).click();
  await openRoute(page, "members", "Members");
  await page.getByText("Fatima Bello", { exact: true }).waitFor();
  await openRoute(page, "loans", "Loans");
  await page.getByRole("button", { name: "Issue book" }).click();
  await page.locator("#form-modal.show").waitFor();
  await page.getByRole("button", { name: "Cancel" }).click();
});

await runRole("member", "fatima.member@librarianpro.ng", async (page) => {
  await page.getByRole("heading", { name: "Welcome, Fatima" }).waitFor();
  await openRoute(page, "books", "Book catalog");
  await page.getByText("Things Fall Apart", { exact: true }).waitFor();
  await openRoute(page, "reservations", "Reservations");
  await page.getByText("waiting", { exact: true }).waitFor();
  await openRoute(page, "fines", "Fines");
  await page.getByText("Fine records", { exact: true }).waitFor();
  await openRoute(page, "notifications", "Notifications");
  await page.getByText("Book issued successfully", { exact: true }).waitFor();
});

await browser.close();
console.log(results.join("\n"));
