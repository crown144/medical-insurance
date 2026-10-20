import type { BrowserContext, Page } from '@playwright/test';
import { expect, test } from '@playwright/test';

const appBaseURL = `${(process.env.PLAYWRIGHT_SSO_BASE_URL || 'http://127.0.0.1:5998').replace(/\/+$/, '')}/`;
const origin = new URL(appBaseURL).origin;
const appUrl = (path = '') => `${appBaseURL}${path ? `#${path}` : ''}`;
const token = 'isolated-browser-test-token';

// 模拟门户与业务 API；真实 Django 令牌和 Word 生成由后端测试覆盖。
async function mockApis(page: BrowserContext | Page, rejectTicket = false) {
  const requests: { path: string; gatewayPath: string; authorization?: string; body: any }[] = [];
  await page.route(/\/(?:api|yibao-api)\//, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const gatewayPath = url.pathname;
    url.pathname = url.pathname.replace(/^\/yibao-api(?=\/)/, '/api');
    const authorization = request.headers().authorization;
    requests.push({
      path: url.pathname,
      gatewayPath,
      authorization,
      body: request.postDataJSON(),
    });
    let body: any;
    if (url.pathname === '/api/portal/sso/config') {
      const callback = appUrl(
        url.searchParams.get('callback') || '/task/execution',
      );
      body = {
        code: 0,
        result: {
          enabled: true,
          authorizeUrl: `${origin}/cas/login?callback=${encodeURIComponent(callback)}`,
          logoutUrl: `${origin}/cas/logout`,
          portalHomeUrl: `${origin}/portal-home`,
        },
      };
    } else if (url.pathname === '/api/sso/login') {
      if (rejectTicket)
        return route.fulfill({
          status: 401,
          json: { message: '门户登录凭据无效或已过期' },
        });
      body = { code: 0, result: { accessToken: token } };
    } else if (authorization !== `Bearer ${token}`) {
      return route.fulfill({ status: 401, json: { message: '缺少医保令牌' } });
    } else if (url.pathname === '/api/user/info') {
      body = {
        code: 0,
        result: {
          userId: '1',
          username: 'portal_test',
          realName: '门户联调',
          roles: ['normal'],
        },
      };
    } else if (url.pathname === '/api/auth/codes') {
      body = { code: 0, result: [] };
    } else if (url.pathname.endsWith('/download-report/')) {
      return route.fulfill({
        status: 200,
        headers: {
          'Content-Type':
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent('医保联调报告.docx')}`,
        },
        body: 'browser-test-report',
      });
    } else if (url.pathname === '/api/tasks/') {
      body = {
        count: 1,
        results: [
          {
            id: 1,
            name: '门户联调任务',
            status: 'completed',
            hospitalization_ids: [],
            selectedSchemas: ['超限定用药'],
            created_at: '2026-10-09T00:00:00Z',
          },
        ],
      };
    } else {
      body = { code: 0, result: [] };
    }
    await route.fulfill({ json: body });
  });
  await page.route('**/cas/login?**', (route) => {
    const callback =
      new URL(route.request().url()).searchParams.get('callback') || '';
    const params = new URLSearchParams({
      ticket: 'ST-browser-test',
      appid: 'test-app',
      callback,
    });
    return route.fulfill({
      status: 302,
      headers: { Location: appUrl(`/oauth/login?${params}`) },
    });
  });
  await page.route('**/cas/logout', (route) =>
    route.fulfill({ status: 200, body: 'CAS logout complete' }),
  );
  await page.route('**/portal-home', (route) =>
    route.fulfill({ status: 200, body: 'Portal home' }),
  );
  return requests;
}

test('门户卡片新窗口打开无参数的注册地址 → 自动 CAS 登录 → 医保任务页', async ({
  context,
  page,
}) => {
  const requests = await mockApis(context);
  const portalHome = 'http://portal.example.test/home';
  await context.route(portalHome, (route) =>
    route.fulfill({
      contentType: 'text/html; charset=utf-8',
      body: `<a href="${appUrl()}" target="_blank" rel="noopener" aria-label="医保控费">医保控费</a>`,
    }),
  );
  await page.goto(portalHome);
  const card = page.getByRole('link', { name: '医保控费' });
  await expect(card).toHaveAttribute('href', appBaseURL);
  const casRequestPromise = context.waitForEvent('request', (request) => {
    const url = new URL(request.url());
    return url.origin === origin && url.pathname === '/cas/login';
  });
  const [appPage] = await Promise.all([
    page.waitForEvent('popup'),
    card.click(),
  ]);
  const casRequest = await casRequestPromise;
  const callback = new URL(casRequest.url()).searchParams.get('callback');
  expect(callback?.startsWith(`${appBaseURL}#`)).toBe(true);
  await expect(
    appPage.getByText('门户联调任务', { exact: true }),
  ).toBeVisible();
  await expect(appPage).toHaveURL(appUrl('/task/manage/execution'));
  await expect(page).toHaveURL(portalHome);
  await expect(card).toBeVisible();
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every((r) => r.gatewayPath.startsWith('/yibao-api/'))).toBe(true);
  expect(requests.find((r) => r.path === '/api/sso/login')?.body).toEqual({
    ticket: 'ST-browser-test',
    appid: 'test-app',
  });
});

test('直接打开应用 → CAS → 医保任务页 → 下载报告 → 刷新保留登录态', async ({
  page,
}) => {
  const requests = await mockApis(page);
  await page.goto(appUrl('/task/manage/execution'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(appUrl('/task/manage/execution'));
  expect(requests.find((r) => r.path === '/api/sso/login')?.body).toEqual({
    ticket: 'ST-browser-test',
    appid: 'test-app',
  });
  await page.getByRole('button', { name: '下载报告' }).click();
  const prompt = page.getByRole('dialog');
  await prompt.getByRole('textbox').fill('3');
  const downloaded = page.waitForEvent('download');
  await prompt.getByRole('button', { name: '确定' }).click();
  expect((await downloaded).suggestedFilename()).toBe('医保联调报告.docx');
  await page.reload();
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.filter((r) => r.path === '/api/sso/login')).toHaveLength(1);
  for (const request of requests.filter((r) =>
    [
      '/api/tasks/',
      '/api/tasks/1/download-report/',
      '/api/user/info',
      '/api/auth/codes',
    ].includes(r.path),
  )) {
    expect(request.authorization).toBe(`Bearer ${token}`);
  }
});

test('后端 302 交换码也能建立医保登录态', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto(appUrl('/oauth/login?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.find((r) => r.path === '/api/sso/login')?.body).toEqual({
    code: 'single-use-code',
  });
});

test('兼容集成分支 SSO 地址并在交换前移除登录凭据', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto(appUrl('/auth/sso?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.find((r) => r.path === '/api/sso/login')?.body).toEqual({
    code: 'single-use-code',
  });
  expect(page.url()).not.toContain('single-use-code');
});

test('退出时先清除医保会话再跳转配置的 CAS 地址', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto(appUrl('/oauth/login?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await expect(page).toHaveURL(`${origin}/cas/logout`);
  expect(
    requests.find((r) => r.path === '/api/auth/logout')?.authorization,
  ).toBe(`Bearer ${token}`);
  const loginRequests = requests.filter(
    (r) => r.path === '/api/sso/login',
  ).length;
  await page.goto(appUrl('/task/manage/execution'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.filter((r) => r.path === '/api/sso/login')).toHaveLength(
    loginRequests + 1,
  );
});

test('门户退出回调清理当前会话并拒绝外站回跳', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto(appUrl('/oauth/login?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  await page.goto(
    appUrl('/auth/sso-logout?callback=https%3A%2F%2Fevil.example%2F'),
  );
  await expect(page).toHaveURL(appUrl('/auth/login'));
  const loginRequests = requests.filter(
    (r) => r.path === '/api/sso/login',
  ).length;
  await page.goto(appUrl('/task/manage/execution'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.filter((r) => r.path === '/api/sso/login')).toHaveLength(
    loginRequests + 1,
  );
});

test('门户退出回调支持配置的门户首页', async ({ page }) => {
  await mockApis(page);
  await page.goto(appUrl('/oauth/login?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  await page.goto(
    appUrl(
      `/auth/sso-logout?callback=${encodeURIComponent(`${origin}/portal-home`)}`,
    ),
  );
  await expect(page).toHaveURL(`${origin}/portal-home`);
});

test('未配置门户时本地退出仍然可用', async ({ page }) => {
  await mockApis(page);
  await page.goto(appUrl('/oauth/login?code=single-use-code'));
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  await page.route(/\/(?:api|yibao-api)\/portal\/sso\/config\?/, (route) =>
    route.fulfill({
      json: { code: 0, result: { enabled: false, authorizeUrl: '' } },
    }),
  );
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await expect(page).toHaveURL(appUrl('/auth/login'));
  await page.goto(appUrl('/task/manage/execution'));
  await expect(page).toHaveURL(/#\/auth\/login\?redirect=/);
});

test('无效 ticket 显示错误并停止，不进入业务页或循环登录', async ({ page }) => {
  const requests = await mockApis(page, true);
  await page.goto(appUrl('/oauth/login?ticket=expired&appid=test-app'));
  await expect(
    page.getByText('门户登录凭据无效或已过期', { exact: true }),
  ).toBeVisible();
  expect(requests.filter((r) => r.path === '/api/tasks/')).toHaveLength(0);
  expect(page.url()).not.toContain('ticket=');
});
