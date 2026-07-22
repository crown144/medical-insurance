<script lang="ts" setup>
import { computed, ref } from 'vue';

import { CopyOutlined, ExpandOutlined, ShrinkOutlined } from '@ant-design/icons-vue';
import { Button, Space, message } from 'ant-design-vue';

const props = defineProps<{
  modelValue: string;
  readonly?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const isFullscreen = ref(false);

const editorValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

async function handleCopy() {
  await navigator.clipboard.writeText(props.modelValue || '');
  message.success('SQL已复制');
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value;
}
</script>

<template>
  <div
    :class="[
      'rounded-lg border border-slate-200 bg-white',
      isFullscreen ? 'fixed inset-4 z-[1001] shadow-2xl' : '',
    ]"
  >
    <div class="flex items-center justify-between border-b border-slate-200 px-3 py-2">
      <div class="text-sm font-medium text-slate-700">SQL内容</div>
      <Space>
        <Button size="small" @click="handleCopy">
          <CopyOutlined />
          复制SQL
        </Button>
        <Button size="small" @click="toggleFullscreen">
          <template #icon>
            <ExpandOutlined v-if="!isFullscreen" />
            <ShrinkOutlined v-else />
          </template>
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </Button>
      </Space>
    </div>
    <textarea
      v-model="editorValue"
      :readonly="readonly"
      :class="[
        'block w-full resize-none rounded-b-lg border-0 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-100 outline-none',
        readonly ? 'cursor-default' : '',
      ]"
      :style="{ minHeight: isFullscreen ? 'calc(100vh - 120px)' : '320px', whiteSpace: 'pre-wrap' }"
      spellcheck="false"
      wrap="soft"
    />
  </div>
</template>

