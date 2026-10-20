import { flushPromises, shallowMount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { getTask, getResults, messageError } = vi.hoisted(() => ({
  getTask: vi.fn(),
  getResults: vi.fn(),
  messageError: vi.fn(),
}));
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { taskId: '12' } }),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('@vben/stores', () => ({
  useUserStore: () => ({ userInfo: { roles: [] } }),
}));
vi.mock('element-plus', () => ({
  ElMessage: { error: messageError, success: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}));
vi.mock('../../api/request', () => ({ baseRequestClient: { get: getTask } }));
vi.mock('../../api/result', () => ({
  getTaskResultListApi: getResults,
  downloadTaskResultCasesApi: vi.fn(),
}));
vi.mock('../../api/task', () => ({ executeTaskApi: vi.fn() }));

import SpecificTaskResult from './SpecificTaskResult.vue';

const result = (id: number) => ({
  data: {
    count: id,
    results: [
      { id, hospitalization_id: `case-${id}`, violation_item: '收费项目' },
    ],
  },
});

function mountResult() {
  return shallowMount(SpecificTaskResult, {
    global: {
      stubs: Object.fromEntries(
        [
          'ElForm',
          'ElFormItem',
          'ElInput',
          'ElDatePicker',
          'ElButton',
          'ElIcon',
          'ElTag',
          'ElCollapse',
          'ElCollapseItem',
          'ElTable',
          'ElTableColumn',
          'ElPagination',
          'ElCol',
          'ElRow',
          'ElTooltip',
        ].map((name) => [name, true]),
      ),
      directives: { loading: () => {} },
    },
  });
}

describe('任务结果分页与自动刷新', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    getTask.mockResolvedValue({ data: { name: 'task', status: 'completed' } });
    getResults.mockResolvedValue(result(1));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('先前分页的慢响应不会覆盖用户最新选择的分页结果', async () => {
    const wrapper = mountResult();
    await flushPromises();
    let resolveOld!: (value: ReturnType<typeof result>) => void;
    getResults.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    );
    (wrapper.vm as any).handlePageChange(2);
    getResults.mockResolvedValueOnce(result(3));
    (wrapper.vm as any).handlePageChange(3);
    await flushPromises();
    resolveOld(result(2));
    await flushPromises();
    expect((wrapper.vm as any).tableData[0].id).toBe(3);
    expect((wrapper.vm as any).total).toBe(3);
    wrapper.unmount();
  });

  it('更改每页条数后请求第一页而非跳到第 20 页', async () => {
    const wrapper = mountResult();
    await flushPromises();
    const pagination = wrapper.findComponent({ name: 'ElPagination' });
    pagination.vm.$emit('size-change', 20);
    await flushPromises();
    expect(getResults).toHaveBeenLastCalledWith(
      expect.objectContaining({
        task_id: '12',
        page: 1,
        page_size: 20,
      }),
    );
    wrapper.unmount();
  });

  it('首次任务状态请求失败后仍轮询，直到成功同步终态', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    getTask.mockRejectedValueOnce(new Error('offline'));
    const wrapper = mountResult();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);
    expect(getTask).toHaveBeenCalledTimes(2);
    expect((wrapper.vm as any).taskStatus).toBe('completed');
    expect(vi.getTimerCount()).toBe(0);
    wrapper.unmount();
  });
});
