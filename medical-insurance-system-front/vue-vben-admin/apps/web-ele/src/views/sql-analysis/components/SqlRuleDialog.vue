<script lang="ts" setup>
import type { SqlRule } from '#/api/sqlAnalysis';

import { computed, reactive, watch } from 'vue';

import SqlCodeEditor from './SqlCodeEditor.vue';

type Mode = 'create' | 'edit' | 'view';

const props = defineProps<{
  mode: Mode;
  modelValue: boolean;
  rule: null | SqlRule;
  saving?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  submit: [payload: {
    ruleName: string;
    ruleType: string;
    description: string;
    sqlContent: string;
    remark: string;
  }];
}>();

const form = reactive({
  ruleName: '',
  ruleType: '',
  description: '',
  sqlContent: '',
  remark: '',
});

const readonly = computed(() => props.mode === 'view');
const title = computed(() => {
  if (props.mode === 'create') return '新增SQL规则';
  if (props.mode === 'edit') return '编辑SQL规则';
  return '查看SQL规则';
});

watch(
  () => [props.modelValue, props.rule],
  ([open]) => {
    if (!open) return;
    form.ruleName = props.rule?.ruleName || '';
    form.ruleType = props.rule?.ruleType || '';
    form.description = props.rule?.description || '';
    form.sqlContent = props.rule?.sqlContent || '';
    form.remark = props.rule?.remark || '';
  },
  { immediate: true },
);

function handleClose() {
  emit('update:modelValue', false);
}

function handleSubmit() {
  emit('submit', { ...form });
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    destroy-on-close
    top="4vh"
    width="1100px"
    @close="handleClose"
  >
    <el-form label-position="top">
      <div class="dialog-grid">
        <el-form-item label="医保规则名称" required>
          <el-input v-model="form.ruleName" :disabled="readonly" />
        </el-form-item>
        <el-form-item label="规则类型" required>
          <el-input v-model="form.ruleType" :disabled="readonly" />
        </el-form-item>
      </div>
      <el-form-item label="规则描述">
        <el-input v-model="form.description" :disabled="readonly" />
      </el-form-item>
      <el-form-item label="SQL内容" required>
        <SqlCodeEditor v-model="form.sqlContent" :readonly="readonly" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input
          v-model="form.remark"
          :autosize="{ minRows: 3, maxRows: 5 }"
          :disabled="readonly"
          type="textarea"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">{{ readonly ? '关闭' : '取消' }}</el-button>
      <el-button v-if="!readonly" :loading="saving" type="primary" @click="handleSubmit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 900px) {
  .dialog-grid {
    grid-template-columns: 1fr;
  }
}
</style>

