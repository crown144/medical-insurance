import { onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue';

/** Refresh only while the result page is visible, waiting for each request. */
export function useTaskAutoRefresh(
  refresh: () => Promise<boolean>,
  delay = 3000,
) {
  const isAutoRefreshing = ref(false);
  let active = false;
  let generation = 0;
  let inFlight: Promise<void> | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function clearTimer() {
    clearTimeout(timer);
    timer = undefined;
  }

  async function runRefresh() {
    const startedGeneration = generation;
    let shouldContinue = true;
    try {
      shouldContinue = await refresh();
    } catch (error) {
      // A temporary network failure must not permanently stop polling.
      console.error('同步任务状态失败', error);
    } finally {
      inFlight = undefined;
      if (active && generation !== startedGeneration) {
        // A cached page was reopened while its previous request was pending.
        void syncTaskState();
      } else if (active && shouldContinue) {
        isAutoRefreshing.value = true;
        timer = setTimeout(() => void syncTaskState(), delay);
      } else {
        isAutoRefreshing.value = false;
      }
    }
  }

  function syncTaskState(): Promise<void> {
    if (!active) return Promise.resolve();
    if (inFlight) return inFlight;
    clearTimer();
    inFlight = runRefresh();
    return inFlight;
  }

  function activate() {
    if (active) return;
    active = true;
    generation += 1;
    isAutoRefreshing.value = true;
    void syncTaskState();
  }

  function deactivate() {
    active = false;
    clearTimer();
    isAutoRefreshing.value = false;
  }

  onMounted(activate);
  onActivated(activate);
  onDeactivated(deactivate);
  onUnmounted(deactivate);

  return { isAutoRefreshing, syncTaskState };
}
