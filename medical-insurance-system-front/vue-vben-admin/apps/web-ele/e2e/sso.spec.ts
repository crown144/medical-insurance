import type { Page } from '@playwright/test';
import { expect, test } from '@playwright/test';

const origin = 'http://127.0.0.1:5998';
const token = 'isolated-browser-test-token';

// 模拟门户与业务 API；真实 Django 令牌和 Word 生成由后端测试覆盖。
async function mockApis(page: Page, rejectTicket = false) {
  const requests: { path: string; authorization?: string; body: any }[] = [];
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const authorization = request.headers().authorization;
    requests.push({
      path: url.pathname,
      authorization,
      body: request.postDataJSON(),
    });
    let body: any;
    if (url.pathname === '/api/portal/sso/config') {
      const callback = `${origin}/#${url.searchParams.get('callback') || '/task/execution'}`;
      body = {
        code: 0,
        result: {
          enabled: true,
          authorizeUrl: `${origin}/cas/login?callback=${encodeURIComponent(callback)}`,
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
      headers: { Location: `${origin}/#/oauth/login?${params}` },
    });
  });
  return requests;
}

test('直接打开应用 → CAS → 医保任务页 → 下载报告 → 刷新保留登录态', async ({
  page,
}) => {
  const requests = await mockApis(page);
  await page.goto('/#/task/manage/execution');
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
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
  await page.goto('/#/oauth/login?code=single-use-code');
  await expect(page.getByText('门户联调任务', { exact: true })).toBeVisible();
  expect(requests.find((r) => r.path === '/api/sso/login')?.body).toEqual({
    code: 'single-use-code',
  });
});

test('无效 ticket 显示错误并停止，不进入业务页或循环登录', async ({ page }) => {
  const requests = await mockApis(page, true);
  await page.goto('/#/oauth/login?ticket=expired&appid=test-app');
  await expect(
    page.getByText('门户登录凭据无效或已过期', { exact: true }),
  ).toBeVisible();
  expect(requests.filter((r) => r.path === '/api/tasks/')).toHaveLength(0);
});
