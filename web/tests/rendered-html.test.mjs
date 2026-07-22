import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the HustleNest business workspace", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>HustleNest · Business workspace<\/title>/i);
  assert.match(html, /Today at a glance/);
  assert.match(html, /Start with what needs attention/);
  assert.match(html, /Needs your attention/);
  assert.match(html, /data-testid="quick-add-order"/);
  assert.match(html, /data-testid="quick-add-record"/);
  assert.match(html, /data-testid="global-search"/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("keeps the prototype metadata and dependencies product-specific", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /function OrderComposer/);
  assert.match(page, /data-testid="quick-add-order"/);
  assert.match(page, /function HustleNestWorkspace/);
  assert.match(page, /Mark unpaid/);
  assert.match(page, /Cancel order and restore inventory/);
  assert.match(page, /api\/orders\/\$\{selected.id\}\/invoice/);
  assert.match(layout, /HustleNest · Business workspace/);
  assert.match(layout, /HustleNest\.ico/);
  assert.match(packageJson, /"lucide-react"/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.doesNotMatch(page, /_sites-preview|SkeletonPreview|codex-preview/);

  await access(new URL("../public/HustleNest.ico", import.meta.url));
  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
});

test("includes connected business, home, and reporting workspace modules", async () => {
  const [navigation, customers, interaction, products, materials, inventoryAdjustment, vendors, finance, reports, history, geography, home, goals, documents, documentPanel, settings, backups, imports, appearance, cloudSync, trash, quickAdd, globalSearch, shared] = await Promise.all([
    readFile(new URL("../app/components/app-navigation.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/customers-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/interaction-panel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/products-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/materials-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/inventory-adjustment-panel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/vendors-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/finance-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/reports-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/history-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/geography-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/home-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/goal-panel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/documents-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/document-panel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/settings-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/backup-settings-card.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/import-settings-card.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/appearance-settings-card.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/cloud-sync-settings-card.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/trash-workspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/quick-add-panel.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/global-search.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/hustlenest.ts", import.meta.url), "utf8"),
  ]);

  assert.match(navigation, /aria-current/);
  assert.match(customers, /Create order for/);
  assert.match(customers, /onEdit/);
  assert.match(customers, /Recent orders/);
  assert.match(customers, /Interaction history/);
  assert.match(customers, /Relationship cadence/);
  assert.match(interaction, /Save interaction/);
  assert.match(interaction, /api\/customers\/\$\{customer.id\}\/interactions/);
  assert.match(products, /Start order with/);
  assert.match(products, /Inventory available/);
  assert.match(products, /Stock outlook/);
  assert.match(products, /Total unit cost/);
  assert.match(products, /Materials used/);
  assert.match(products, /Add photo/);
  assert.match(products, /api\/products\/\$\{selected.id\}\/photo/);
  assert.match(products, /8 MB or smaller/);
  assert.match(products, /Pencil/);
  assert.match(materials, /Recent inventory activity/);
  assert.match(materials, /Needs attention/);
  assert.match(materials, /Edit material/);
  assert.match(materials, /Adjust stock/);
  assert.match(materials, /Used by products/);
  assert.match(inventoryAdjustment, /Add delivered stock/);
  assert.match(inventoryAdjustment, /Counted quantity on hand/);
  assert.match(inventoryAdjustment, /api\/materials\/\$\{material.id\}\/adjust/);
  assert.match(vendors, /Supplied materials/);
  assert.match(vendors, /Reorder exposure/);
  assert.match(vendors, /Edit vendor/);
  assert.match(finance, /Monthly recurring/);
  assert.match(finance, /Open linked material/);
  assert.match(finance, /Year-to-date/);
  assert.match(finance, /Losses/);
  assert.match(finance, /Operational context/);
  assert.match(finance, /Open linked order/);
  assert.match(finance, /Edit expense/);
  assert.match(finance, /Edit recurring/);
  assert.match(finance, /Edit loss/);
  assert.match(reports, /Revenue and gross profit/);
  assert.match(reports, /Top customers/);
  assert.match(reports, /Reporting period/);
  assert.match(history, /Activity history/);
  assert.match(history, /Export CSV/);
  assert.match(history, /api\/history/);
  assert.match(history, /Open order/);
  assert.match(geography, /Sales geography/);
  assert.match(geography, /Order activity by state/);
  assert.match(geography, /api\/geography/);
  assert.match(geography, /onOpenOrder/);
  assert.match(home, /Needs your attention/);
  assert.match(home, /Business goals/);
  assert.match(home, /Manage goals/);
  assert.match(home, /Keep moving/);
  assert.match(goals, /Goals & checkpoints/);
  assert.match(goals, /Calculate progress automatically/);
  assert.match(goals, /Save checkpoint/);
  assert.match(goals, /api\/goals/);
  assert.match(documents, /Linked business record/);
  assert.match(documents, /Copy file location/);
  assert.match(documents, /Missing locally/);
  assert.match(documents, /Upload document/);
  assert.match(documents, /api\/documents\/\$\{item.id\}\/download/);
  assert.match(documentPanel, /Managed by HustleNest/);
  assert.match(documentPanel, /20 MB maximum/);
  assert.match(documentPanel, /Also delete the managed file/);
  assert.match(documentPanel, /api\/documents/);
  assert.match(settings, /CloudSyncSettingsCard/);
  assert.match(settings, /Orders and inventory/);
  assert.match(settings, /Browser editing is enabled/);
  assert.match(settings, /Selected work browser/);
  assert.match(settings, /Invoice payment methods/);
  assert.match(settings, /Saved destinations stay masked/);
  assert.match(settings, /Add payment method/);
  assert.match(settings, /other_action/);
  assert.match(settings, /Revision protected/);
  assert.match(backups, /Backups & recovery/);
  assert.match(backups, /Back up now/);
  assert.match(backups, /RESTORE/);
  assert.match(backups, /api\/backups/);
  assert.match(imports, /Import data/);
  assert.match(imports, /Update matching records and preserve unmapped data/);
  assert.match(imports, /api\/imports\/preview/);
  assert.match(imports, /api\/imports\/execute/);
  assert.match(appearance, /Appearance & dashboard/);
  assert.match(appearance, /Dashboard layout/);
  assert.match(appearance, /Move \$\{section\.label\} up/);
  assert.match(appearance, /api\/settings\/logo/);
  assert.match(cloudSync, /Saved values never return to the browser/);
  assert.match(cloudSync, /PULL CLOUD DATA/);
  assert.match(cloudSync, /api\/sync-settings\/upload/);
  assert.match(trash, /Recently deleted/);
  assert.match(trash, /EMPTY TRASH/);
  assert.match(trash, /api\/trash/);
  assert.match(trash, /Restore/);
  assert.match(quickAdd, /Quick add/);
  assert.match(quickAdd, /Save \$\{type\}/);
  assert.match(quickAdd, /api\/quick-add/);
  assert.match(quickAdd, /api\/records/);
  assert.match(quickAdd, /Save changes/);
  assert.match(quickAdd, /Extra unit costs/);
  assert.match(quickAdd, /Product status/);
  assert.match(quickAdd, /Automatically record when due/);
  assert.match(globalSearch, /Find or do anything/);
  assert.match(globalSearch, /Command/);
  assert.match(globalSearch, /ArrowDown/);
  assert.match(globalSearch, /Ctrl K/);
  assert.match(globalSearch, /Recurring/);
  assert.match(shared, /FinanceWorkspaceData/);
  assert.match(shared, /ReportsWorkspaceData/);
  assert.match(shared, /HomeWorkspaceData/);
  assert.match(shared, /HistoryWorkspaceData/);
  assert.match(shared, /GeographyWorkspaceData/);
  assert.match(shared, /GoalsWorkspaceData/);
  assert.match(shared, /DocumentsWorkspaceData/);
  assert.match(shared, /SettingsWorkspaceData/);
  assert.match(shared, /TrashWorkspaceData/);
  assert.match(shared, /BackupWorkspaceData/);
  assert.match(shared, /ImportPreviewData/);
  assert.match(shared, /ImportResultData/);
  assert.match(shared, /dashboard_sections/);
  assert.match(shared, /CloudSyncWorkspaceData/);
  assert.match(shared, /MaterialDetail/);
  assert.match(shared, /cost_components/);
  assert.match(shared, /days_until_stockout/);
  assert.match(shared, /photo_available/);
  assert.match(shared, /key: string/);
  assert.match(shared, /getBridgeData/);
});
