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
const builtIn = { ...definition, id: 10000, builtIn: true, jobIndex: 0 };
const secondJob = { ...builtIn, id: 10001, jobIndex: 1,
  tiers: [{ ...definition.tiers[0], stats: { HP: 100, PDD: 90 }, customized: true }] };
const runtimeDefinitions = require('../../gms-server/src/main/resources/set-item/catalog.json')
  .map((series) => ({ ...series, builtIn: true, enabled: true, completeCount: series.slots.length,
    slotsCustomized: false, slots: series.slots.map((slot) => slot.map(equipment)),
    defaultSlots: series.slots.map((slot) => slot.map(equipment)),
    tiers: series.tiers.map((tier) => ({ ...tier, defaultStats: tier.stats, customized: false })) }));

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.SET_ITEM_BROWSER || 'chrome' });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      let saved;
      let savedSeries;
      let created;
      let showRuntimeCatalog = false;
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
        else if (url.pathname === '/setItem/v1/catalog') data = showRuntimeCatalog
          ? runtimeDefinitions : [definition, builtIn, secondJob];
        else if (url.pathname.startsWith('/setItem/v1/series/') && route.request().method() === 'PUT') {
          savedSeries = route.request().postDataJSON().data; data = 0;
        }
        else if (route.request().method() === 'PUT') { saved = route.request().postDataJSON().data; data = 0; }
        else if (url.pathname === '/setItem/v1/custom' && route.request().method() === 'POST') {
          created = route.request().postDataJSON().data; data = 20001;
        }
        else if (url.pathname.includes('/menu')) data = [];
        await route.fulfill({ json: { code: 20000, data, message: 'OK' } });
      });
      await page.goto(`${baseUrl}/#/game/setItem`);
      await page.getByRole('button', { name: '统一加成', exact: true }).first().waitFor();
      assert.equal(await page.getByRole('button', { name: '统一加成', exact: true }).count(), 2,
        'same-name built-in jobs must be grouped; custom sets must remain independent');
      await page.getByText('加成不一致', { exact: true }).waitFor();
      if (viewport.width < 576) await page.locator('.layout.mobile').waitFor();
      await page.screenshot({ path: `/tmp/set-item-series-${viewport.width}.png`, fullPage: true, animations: 'disabled' });
      await page.getByRole('button', { name: '统一加成', exact: true }).nth(1).click();
      const seriesModal = page.locator('.arco-modal:visible').last();
      await seriesModal.getByText('本次保存会统一覆盖本系列 2 套的全部档位加成。', { exact: true }).waitFor();
      assert.equal(await seriesModal.locator('.slot-row').count(), 0);
      await seriesModal.locator('.arco-form-item').filter({ hasText: '物理防御力' }).getByRole('spinbutton').fill('45');
      await seriesModal.getByRole('button', { name: '保存', exact: true }).click();
      await seriesModal.waitFor({ state: 'hidden' });
      assert.equal(savedSeries.tiers['1'].PDD, 45);
      assert.equal('slots' in savedSeries, false, 'series update must never copy representative slots');
      await page.getByRole('button', { name: '详情', exact: true }).first().click();
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
      showRuntimeCatalog = true;
      await page.reload();
      await page.getByRole('button', { name: '统一加成', exact: true }).first().waitFor();
      const filter = page.getByPlaceholder('搜索套装名称或ID');
      await filter.fill('黑门');
      await page.getByRole('button', { name: '统一加成', exact: true }).click();
      const blackGate = page.locator('.arco-modal:visible').last();
      await blackGate.getByText('5 件效果', { exact: true }).click();
      await blackGate.locator('.arco-tabs-tab-active').filter({ hasText: '5 件效果' }).waitFor();
      assert.equal(await blackGate.locator('.arco-form-item:visible').filter({ hasText: '最大HP' })
        .getByRole('spinbutton').inputValue(), '2');
      assert.equal(await blackGate.locator('.arco-form-item:visible').filter({ hasText: '最大MP' })
        .getByRole('spinbutton').inputValue(), '2');
      assert.equal(await blackGate.getByText('待确认', { exact: true }).count(), 0);
      assert.equal(await blackGate.evaluate((el) => el.scrollWidth > el.clientWidth + 1), false);
      await blackGate.evaluate(async (el) => Promise.all(el.getAnimations({ subtree: true })
        .filter((animation) => animation.effect.getTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => {}))));
      await page.screenshot({ path: `/tmp/set-item-black-gate-${viewport.width}.png`, fullPage: true });
      await blackGate.getByRole('button', { name: '取消', exact: true }).click();
      await blackGate.waitFor({ state: 'hidden' });
      await filter.fill('冒险岛寻宝');
      await page.getByRole('button', { name: '详情', exact: true }).click();
      await page.getByRole('button', { name: '编辑套装', exact: true }).click();
      const treasure = page.locator('.arco-modal:visible').first();
      await treasure.locator('.slot-row').first().waitFor();
      assert.equal(await treasure.locator('.slot-row').count(), 12);
      await treasure.getByRole('button', { name: '添加槽位', exact: true }).click();
      assert.equal(await treasure.locator('.slot-row').count(), 13);
      await treasure.locator('.slot-row').last().locator('.slot-header button').click();
      await treasure.getByText('6 件效果', { exact: true }).click();
      await treasure.locator('.arco-tabs-tab-active').filter({ hasText: '6 件效果' }).waitFor();
      assert.equal(await treasure.locator('.arco-form-item:visible').filter({ has: page.getByText('伤害(%)', { exact: true }) })
        .getByRole('spinbutton').inputValue(), '9');
      assert.equal(await treasure.evaluate((el) => el.scrollWidth > el.clientWidth + 1), false);
      await treasure.locator('.arco-form-item:visible').filter({ has: page.getByText('伤害(%)', { exact: true }) })
        .scrollIntoViewIfNeeded();
      await treasure.evaluate(async (el) => Promise.all(el.getAnimations({ subtree: true })
        .filter((animation) => animation.effect.getTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => {}))));
      await page.screenshot({ path: `/tmp/set-item-treasure-${viewport.width}.png`, fullPage: true });
      await treasure.getByRole('button', { name: '保存', exact: true }).click();
      await treasure.waitFor({ state: 'hidden' });
      assert.equal(saved.slots.length, 12);
      assert.equal(saved.slots.flat().includes(1012524), true);
      assert.equal(saved.tiers['12'].BossDamage, 30);
      assert.equal(saved.tiers['6'].Damage, 9);
      assert.deepEqual(errors, []);
      console.log(`set-item UI ${viewport.width}: edit/create, runtime catalog, Black Gate HP/MP, Treasure damage/12 slots, save and overflow checks passed`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
