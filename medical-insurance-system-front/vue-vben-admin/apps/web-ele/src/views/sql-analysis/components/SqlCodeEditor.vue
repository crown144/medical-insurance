<script lang="ts" setup>
import { computed, ref } from 'vue';

import { ElMessage } from 'element-plus';

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
  ElMessage.success('SQL已复制');
}
</script>

<template>
  <div :class="['sql-editor', { fullscreen: isFullscreen }]">
    <div class="sql-editor__toolbar">
      <span class="sql-editor__title">SQL内容</span>
      <div class="sql-editor__actions">
        <el-button plain size="small" @click="handleCopy">复制SQL</el-button>
        <el-button plain size="small" @click="isFullscreen = !isFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </el-button>
      </div>
    </div>
    <textarea
      v-model="editorValue"
      :readonly="readonly"
      class="sql-editor__textarea"
      spellcheck="false"
      wrap="soft"
    />
  </div>
</template>

<style scoped>
.sql-editor {
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.sql-editor.fullscreen {
  position: fixed;
  inset: 16px;
  z-index: 3000;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.28);
}

.sql-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #f8fafc;
}

.sql-editor__title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.sql-editor__actions {
  display: flex;
  gap: 8px;
}

.sql-editor__textarea {
  width: 100%;
  min-height: 320px;
  resize: vertical;
  border: 0;
  outline: none;
  padding: 16px;
  background: #020617;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.7;
  font-family: Consolas, Monaco, monospace;
  white-space: pre-wrap;
}

.fullscreen .sql-editor__textarea {
  min-height: calc(100vh - 110px);
}
</style>

