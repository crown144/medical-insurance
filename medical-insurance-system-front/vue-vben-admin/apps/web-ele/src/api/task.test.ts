import { describe, expect, it, vi } from 'vitest';
const { get, save } = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn() }));
vi.mock('./request', () => ({ baseRequestClient: { get }, requestClient: {} }));
vi.mock('@vben/utils', () => ({ downloadFileFromBlob: save }));
import { downloadTaskReportApi } from './task';

describe('携带登录态下载报告', () => {
  it('通过请求客户端获取 Blob，采用服务端中文文件名', async () => {
    const blob = new Blob(['report']);
    const name = '医保报告_第3期.docx';
    get.mockResolvedValue({
      data: blob,
      headers: {
        'content-disposition': `attachment; filename*=utf-8''${encodeURIComponent(name)}`,
      },
    });
    await downloadTaskReportApi(12, 3);
    expect(get).toHaveBeenCalledWith('/tasks/12/download-report/', {
      params: { issue_number: 3 },
      responseType: 'blob',
    });
    expect(save).toHaveBeenCalledWith({ source: blob, fileName: name });
  });
  it('请求失败时不下载错误响应', async () => {
    save.mockClear();
    get.mockRejectedValue(new Error('401'));
    await expect(downloadTaskReportApi(12, 3)).rejects.toThrow('401');
    expect(save).not.toHaveBeenCalled();
  });
});
