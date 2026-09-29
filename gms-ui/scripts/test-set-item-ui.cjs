const assert = require('node:assert/strict');
const path = require('node:path');
const sharp = require('sharp');
const { chromium } = require('playwright');

const baseUrl = process.env.SET_ITEM_UI_URL || 'http://127.0.0.1:5176';
const catalogRoot = path.resolve(__dirname, '../../gms-server/src/main/resources/equipment-catalog');
const catalog = require(path.join(catalogRoot, 'catalog.json'));
const equipment = (id) => {
  const entry = catalog.items.find((candidate) => candidate.id === id);
  return { ...entry, description: entry.desc, iconAvailable: entry.icon };
};
const item = equipment(1002000);
const slots = [[equipment(1002001)], [equipment(1040000)]];
const definition = { id: 20000, jobIndex: -1, name: '测试套装', completeCount: 2, builtIn: false,
  enabled: true, slots, defaultSlots: slots, slotsCustomized: false,
  tiers: [{ requiredCount: 1, stats: { HP: 100, PDD: 30 }, defaultStats: { HP: 100, PDD: 30 }, customized: false }] };

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.SET_ITEM_BROWSER || 'chrome' });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      let saved;
      let created;
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.addInitScript(() => localStorage.setItem('token', 'set-item-test-only'));
      await page.route('http://localhost:8686/**', async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/assets/')) {
          const id = Number(path.basename(url.pathname, '.png'));
          const entry = equipment(id);
          const body = await sharp(path.join(catalogRoot, 'atlases', `${entry.category}.png`))
            .extract({ left: entry.x, top: entry.y, width: catalog.cellSize, height: catalog.cellSize })
            .png().toBuffer();
          await route.fulfill({ contentType: 'image/png', body });
          return;
        }
        let data = {};
        if (url.pathname === '/account/v1/info') data = { name: '测试管理员', nick: '测试管理员', webadmin: true };
        else if (url.pathname.endsWith('/equipment/catalog')) data = { records: [item], pageNo: Number(url.searchParams.get('pageNo') || 1), pageSize: 30, total: 60, categories: [], weaponTypes: [] };
        else if (url.pathname === '/setItem/v1/catalog') data = [definition];
        else if (route.request().method() === 'PUT') { saved = route.request().postDataJSON().data; data = 0; }
        else if (url.pathname === '/setItem/v1/custom' && route.request().method() === 'POST') {
          created = route.request().postDataJSON().data; data = 20001;
        }
        else if (url.pathname.includes('/menu')) data = [];
        await route.fulfill({ json: { code: 20000, data, message: 'OK' } });
      });
      await page.goto(`${baseUrl}/#/game/setItem`);
      try {
        await page.getByRole('button', { name: '编辑套装', exact: true }).click({ timeout: 10000 });
      } catch (error) {
        await page.screenshot({ path: '/tmp/set-item-ui-failure.png', fullPage: true });
        console.error({ url: page.url(), body: await page.locator('body').innerText(), errors });
        throw error;
      }
      const modal = page.locator('.arco-modal:visible').first();
      const hpForm = modal.locator('.arco-form-item').filter({ hasText: '最大HP' }).first();
      await hpForm.locator('label').filter({ hasText: '百分比' }).click();
      await hpForm.getByRole('spinbutton').fill('20');
      await modal.getByRole('button', { name: '添加装备', exact: true }).first().click();
      const search = page.locator('.arco-modal').filter({ has: page.getByText('选择装备', { exact: true }) });
      await search.getByPlaceholder('输入装备名称或物品ID').fill('航空帽');
      await search.getByRole('button', { name: '搜索', exact: true }).click();
      await search.getByText(item.name, { exact: true }).waitFor();
      await search.locator('.equipment-icon').first().hover();
      await page.locator('.equipment-tooltip').waitFor({ state: 'visible' });
      await page.screenshot({ path: `/tmp/set-item-search-${viewport.width}.png`, fullPage: true, animations: 'disabled' });
      const preview = await page.locator('.equipment-tooltip').boundingBox();
      assert.ok(preview.x >= 0 && preview.x + preview.width <= viewport.width + 1,
        'equipment preview overflows viewport');
      await page.mouse.move(0, 0);
      await page.locator('.equipment-tooltip').waitFor({ state: 'hidden' });
      await search.locator('.arco-pagination-item').filter({ hasText: /^2$/ }).click();
      await search.getByRole('button', { name: '选择', exact: true }).click();
      await search.waitFor({ state: 'hidden' });
      await modal.getByText(item.name, { exact: true }).waitFor();
      await page.waitForFunction(() => [...document.querySelectorAll('.arco-modal img')]
        .every((image) => image.complete && image.naturalWidth > 0));
      await page.screenshot({ path: `/tmp/set-item-editor-${viewport.width}.png`, fullPage: true });
      const overflow = await modal.evaluate((el) => el.scrollWidth > el.clientWidth + 1);
      assert.equal(overflow, false, 'modal horizontally overflows');
      await modal.getByRole('button', { name: '保存', exact: true }).click();
      await modal.waitFor({ state: 'hidden' });
      assert.equal(saved.tiers['1'].HPPct, 20);
      assert.equal('HP' in saved.tiers['1'], false);
      assert.deepEqual(saved.slots, [[1002001, 1002000], [1040000]]);
      await page.getByRole('button', { name: '新增套装', exact: true }).click();
      const create = page.locator('.arco-modal').filter({ has: page.getByText('新增自定义套装', { exact: true }) });
      await create.locator('.arco-form-item').filter({ hasText: '套装名称' }).getByRole('textbox').fill('新建测试套装');
      await create.locator('.stat-row label').filter({ hasText: '百分比' }).click();
      await create.locator('.stat-row').getByRole('spinbutton').fill('20');
      await create.getByRole('button', { name: '添加装备', exact: true }).click();
      await search.getByPlaceholder('输入装备名称或物品ID').fill('1002000');
      await search.getByRole('button', { name: '搜索', exact: true }).click();
      await search.getByText(item.name, { exact: true }).waitFor();
      await search.getByRole('button', { name: '选择', exact: true }).click();
      await search.waitFor({ state: 'hidden' });
      await create.getByRole('button', { name: '添加槽位', exact: true }).click();
      await create.getByRole('button', { name: '新增套装', exact: true }).click();
      await page.getByText('每个槽位至少选择一件装备', { exact: true }).waitFor();
      assert.equal(created, undefined, 'empty slot must not reach the API');
      await create.locator('.slot-row').last().locator('.slot-header button').click();
      await page.screenshot({ path: `/tmp/set-item-create-${viewport.width}.png`, fullPage: true });
      assert.equal(await create.evaluate((el) => el.scrollWidth > el.clientWidth + 1), false);
      await create.getByRole('button', { name: '新增套装', exact: true }).click();
      await create.waitFor({ state: 'hidden' });
      assert.deepEqual(created.slots, [[1002000]]);
      assert.equal(created.tiers['1'].PADPct, 20);
      assert.deepEqual(errors, []);
      console.log(`set-item UI ${viewport.width}: edit/create, fixed/percent, equipment preview/search/paging, slot validation/removal, save and overflow checks passed`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
