import { defineComponent, h, KeepAlive, nextTick, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTaskAutoRefresh } from './task-auto-refresh';

function mountPage(refresh: () => Promise<boolean>) {
  const visible = ref(true);
  let polling!: ReturnType<typeof useTaskAutoRefresh>;
  const Page = defineComponent({
    setup() {
      polling = useTaskAutoRefresh(refresh);
      return () => h('div');
    },
  });
  const wrapper = mount(
    defineComponent({
      setup: () => () => h(KeepAlive, () => (visible.value ? h(Page) : null)),
    }),
  );
  return { wrapper, visible, polling };
}

describe('任务结果自动刷新', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('慢请求期间不叠加轮询，手动刷新复用在途请求', async () => {
    let finish!: (value: boolean) => void;
    const refresh = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve;
        }),
    );
    const { wrapper, polling } = mountPage(refresh);
    await vi.advanceTimersByTimeAsync(9000);
    void polling.syncTaskState();
    expect(refresh).toHaveBeenCalledTimes(1);
    finish(true);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);
    expect(refresh).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    finish(true);
    await flushPromises();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('缓存页面隐藏后暂停，重新打开时立即同步并恢复轮询', async () => {
    const refresh = vi
      .fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValue(true);
    const { wrapper, visible, polling } = mountPage(refresh);
    await flushPromises();
    expect(polling.isAutoRefreshing.value).toBe(false);
    visible.value = false;
    await nextTick();
    await vi.advanceTimersByTimeAsync(6000);
    expect(refresh).toHaveBeenCalledTimes(1);
    visible.value = true;
    await nextTick();
    await flushPromises();
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(polling.isAutoRefreshing.value).toBe(true);
    visible.value = false;
    await nextTick();
    await vi.advanceTimersByTimeAsync(6000);
    expect(refresh).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it('页面离开后未完成的请求不能重新启动轮询', async () => {
    let finish!: (value: boolean) => void;
    const refresh = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve;
        }),
    );
    const { wrapper, visible } = mountPage(refresh);
    visible.value = false;
    await nextTick();
    finish(true);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(6000);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
    wrapper.unmount();
  });

  it('请求期间离开再返回时，旧响应结束后重新获取当前状态', async () => {
    let finish!: (value: boolean) => void;
    const refresh = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<boolean>((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValue(false);
    const { wrapper, visible } = mountPage(refresh);
    visible.value = false;
    await nextTick();
    visible.value = true;
    await nextTick();
    finish(false);
    await flushPromises();
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
    wrapper.unmount();
  });

  it('短暂失败后继续重试，成功收到终态后停止', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const refresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(false);
    const { wrapper, polling } = mountPage(refresh);
    await flushPromises();
    expect(polling.isAutoRefreshing.value).toBe(true);
    await vi.advanceTimersByTimeAsync(3000);
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(polling.isAutoRefreshing.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    wrapper.unmount();
  });
});
