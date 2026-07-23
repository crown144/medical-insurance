<script lang="ts" setup>
import type { SqlRule } from '#/api/core/sql-analysis';

import { computed, reactive, watch } from 'vue';

import { Form, FormItem, Input, Modal } from 'ant-design-vue';

import SqlCodeEditor from './SqlCodeEditor.vue';

type Mode = 'create' | 'edit' | 'view';

const props = defineProps<{
  mode: Mode;
  open: boolean;
  rule: null | SqlRule;
  submitting?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  submit: [payload: {
    ruleName: string;
    ruleType: string;
    description: string;
    sqlContent: string;
    remark: string;
  }];
}>();

const formState = reactive({
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
  () => [props.open, props.rule, props.mode],
  ([open]) => {
    if (!open) return;
    formState.ruleName = props.rule?.ruleName || '';
    formState.ruleType = props.rule?.ruleType || '';
    formState.description = props.rule?.description || '';
    formState.sqlContent = props.rule?.sqlContent || '';
    formState.remark = props.rule?.remark || '';
  },
  { immediate: true },
);

function handleSubmit() {
  emit('submit', { ...formState });
}
</script>

<template>
  <Modal
    :confirm-loading="submitting"
    :ok-text="readonly ? '关闭' : '保存'"
    :open="open"
    :title="title"
    destroy-on-close
    width="1100px"
    @cancel="emit('close')"
    @ok="readonly ? emit('close') : handleSubmit()"
  >
    <Form layout="vertical">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FormItem label="医保规则名称" required>
          <Input v-model:value="formState.ruleName" :disabled="readonly" />
        </FormItem>
        <FormItem label="规则类型" required>
          <Input v-model:value="formState.ruleType" :disabled="readonly" />
        </FormItem>
      </div>
      <FormItem label="规则描述">
        <Input v-model:value="formState.description" :disabled="readonly" />
      </FormItem>
      <FormItem label="SQL内容" required>
        <SqlCodeEditor v-model="formState.sqlContent" :readonly="readonly" />
      </FormItem>
      <FormItem label="备注">
        <Input.TextArea
          v-model:value="formState.remark"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          :disabled="readonly"
        />
      </FormItem>
    </Form>
  </Modal>
</template>
