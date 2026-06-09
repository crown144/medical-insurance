<script lang="ts" setup>
import type { FeiJianRecord, InspectorMember } from '#/api/core/feijian';

import { computed, reactive, ref } from 'vue';

import { $t } from '#/locales';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Divider,
  Form,
  FormItem,
  Input,
  InputNumber,
  Row,
  Select,
  SelectOption,
  Space,
  Textarea,
} from 'ant-design-vue';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue';
import dayjs, { Dayjs } from 'dayjs';

defineOptions({ name: 'InspectionForm' });

const props = defineProps<{
  record: FeiJianRecord | null;
}>();

const emit = defineEmits<{
  submit: [record: FeiJianRecord];
  cancel: [];
}>();

const isEdit = computed(() => !!props.record);

// ==================== 枚举选项 ====================

const hospitalTypeOptions = [
  { value: 'general', label: $t('page.feijian.hospitalType.general') },
  { value: 'specialist', label: $t('page.feijian.hospitalType.specialist') },
  { value: 'community', label: $t('page.feijian.hospitalType.community') },
  { value: 'private', label: $t('page.feijian.hospitalType.private') },
];

const inspectionTypeOptions = [
  { value: 'routine', label: $t('page.feijian.type.routine') },
  { value: 'special', label: $t('page.feijian.type.special') },
  { value: 'unannounced', label: $t('page.feijian.type.unannounced') },
  { value: 'follow-up', label: $t('page.feijian.type.follow-up') },
];

const statusOptions = [
  { value: 'draft', label: $t('page.feijian.status.draft') },
  { value: 'pending', label: $t('page.feijian.status.pending') },
  { value: 'in-progress', label: $t('page.feijian.status.in-progress') },
  { value: 'completed', label: $t('page.feijian.status.completed') },
  { value: 'cancelled', label: $t('page.feijian.status.cancelled') },
];

const resultOptions = [
  { value: 'none', label: $t('page.feijian.result.none') },
  { value: 'compliant', label: $t('page.feijian.result.compliant') },
  { value: 'minor-issue', label: $t('page.feijian.result.minor-issue') },
  { value: 'major-issue', label: $t('page.feijian.result.major-issue') },
  { value: 'violation', label: $t('page.feijian.result.violation') },
];

// ==================== 表单数据 ====================

const formRef = ref();

const formState = reactive({
  // 基本信息
  inspectionNo: '',
  inspectionType: undefined as string | undefined,
  inspectionDate: undefined as Dayjs | undefined,
  inspectionEndDate: undefined as Dayjs | undefined,
  status: undefined as string | undefined,

  // 医疗机构信息
  hospitalName: '',
  hospitalType: undefined as string | undefined,
  hospitalAddress: '',
  contactPerson: '',
  contactPhone: '',

  // 检查组信息
  teamLeader: '',
  teamMembers: [] as InspectorMember[],

  // 检查结果
  result: undefined as string | undefined,
  findings: '',
  recommendation: '',
  violationAmount: undefined as number | undefined,
});

// 初始化表单数据
if (props.record) {
  const r = props.record;
  formState.inspectionNo = r.inspectionNo;
  formState.inspectionType = r.inspectionType;
  formState.inspectionDate = dayjs(r.inspectionDate);
  formState.inspectionEndDate = dayjs(r.inspectionEndDate);
  formState.status = r.status;
  formState.hospitalName = r.hospital.name;
  formState.hospitalType = r.hospital.type;
  formState.hospitalAddress = r.hospital.address;
  formState.contactPerson = r.hospital.contactPerson;
  formState.contactPhone = r.hospital.contactPhone;
  formState.teamLeader = r.teamLeader;
  formState.teamMembers = r.inspectionTeam.map((m) => ({ ...m }));
  formState.result = r.result;
  formState.findings = r.findings;
  formState.recommendation = r.recommendation;
  formState.violationAmount = r.violationAmount;
} else {
  // 生成默认检查编号
  const now = dayjs();
  formState.inspectionNo = `FJ-${now.format('YYYY')}-${String(Math.floor(Math.random() * 9000) + 1000)}`;
  formState.inspectionDate = now;
  formState.inspectionEndDate = now.add(2, 'day');
  formState.status = 'draft';
  formState.teamMembers = [
    { id: '', name: '', role: '组长', phone: '' },
    { id: '', name: '', role: '检查员', phone: '' },
  ];
}

// 添加检查组成员
function addTeamMember() {
  formState.teamMembers.push({ id: '', name: '', role: '检查员', phone: '' });
}

// 删除检查组成员
function removeTeamMember(index: number) {
  if (formState.teamMembers.length > 1) {
    formState.teamMembers.splice(index, 1);
  }
}

// 表单验证规则
const rules = {
  inspectionNo: [{ required: true, message: '请输入检查编号', trigger: 'blur' }],
  inspectionType: [{ required: true, message: '请选择检查类型', trigger: 'change' }],
  inspectionDate: [{ required: true, message: '请选择检查开始日期', trigger: 'change' }],
  inspectionEndDate: [{ required: true, message: '请选择检查结束日期', trigger: 'change' }],
  hospitalName: [{ required: true, message: '请输入医疗机构名称', trigger: 'blur' }],
  hospitalType: [{ required: true, message: '请选择机构类型', trigger: 'change' }],
  hospitalAddress: [{ required: true, message: '请输入机构地址', trigger: 'blur' }],
  contactPerson: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contactPhone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
  teamLeader: [{ required: true, message: '请输入检查组组长', trigger: 'blur' }],
  status: [{ required: true, message: '请选择检查状态', trigger: 'change' }],
};

// 提交
async function handleSubmit() {
  try {
    await formRef.value?.validate();

    const hospitalTypeLabel =
      hospitalTypeOptions.find((o) => o.value === formState.hospitalType)?.label || '';

    const inspectionTypeLabel =
      inspectionTypeOptions.find((o) => o.value === formState.inspectionType)?.label || '';

    const resultLabel =
      resultOptions.find((o) => o.value === formState.result)?.label || '';

    const statusLabel =
      statusOptions.find((o) => o.value === formState.status)?.label || '';

    const record: FeiJianRecord = {
      id: props.record?.id || String(Date.now()),
      inspectionNo: formState.inspectionNo,
      hospital: {
        id: props.record?.hospital.id || String(Date.now()),
        name: formState.hospitalName,
        type: formState.hospitalType as any,
        typeLabel: hospitalTypeLabel,
        address: formState.hospitalAddress,
        contactPerson: formState.contactPerson,
        contactPhone: formState.contactPhone,
      },
      inspectionType: formState.inspectionType as any,
      inspectionTypeLabel,
      inspectionDate: formState.inspectionDate?.format('YYYY-MM-DD') || '',
      inspectionEndDate: formState.inspectionEndDate?.format('YYYY-MM-DD') || '',
      inspectionTeam: formState.teamMembers,
      teamLeader: formState.teamLeader,
      result: (formState.result as any) || 'none',
      resultLabel: resultLabel || '待定',
      status: formState.status as any,
      statusLabel,
      findings: formState.findings,
      recommendation: formState.recommendation,
      violationAmount: formState.violationAmount || 0,
      createdAt: props.record?.createdAt || dayjs().format('YYYY-MM-DD HH:mm:ss'),
      updatedAt: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    };

    emit('submit', record);
  } catch {
    // 表单验证失败
  }
}
</script>

<template>
  <div class="inspection-form">
    <Form ref="formRef" :model="formState" :rules="rules" layout="vertical">
      <!-- 基本信息 -->
      <Card :title="$t('page.feijian.modal.baseInfo')" size="small" class="mb-4">
        <Row :gutter="16">
          <Col :span="8">
            <FormItem :label="$t('page.feijian.modal.inspectionNo')" name="inspectionNo">
              <Input v-model:value="formState.inspectionNo" />
            </FormItem>
          </Col>
          <Col :span="8">
            <FormItem :label="$t('page.feijian.modal.inspectionType')" name="inspectionType">
              <Select v-model:value="formState.inspectionType">
                <SelectOption
                  v-for="opt in inspectionTypeOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :span="8">
            <FormItem :label="$t('page.feijian.modal.status')" name="status">
              <Select v-model:value="formState.status">
                <SelectOption
                  v-for="opt in statusOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
        </Row>
        <Row :gutter="16">
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.inspectionDate')" name="inspectionDate">
              <DatePicker v-model:value="formState.inspectionDate" style="width: 100%" />
            </FormItem>
          </Col>
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.inspectionEndDate')" name="inspectionEndDate">
              <DatePicker v-model:value="formState.inspectionEndDate" style="width: 100%" />
            </FormItem>
          </Col>
        </Row>
      </Card>

      <!-- 医疗机构信息 -->
      <Card :title="$t('page.feijian.modal.hospitalInfo')" size="small" class="mb-4">
        <Row :gutter="16">
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.hospitalName')" name="hospitalName">
              <Input v-model:value="formState.hospitalName" />
            </FormItem>
          </Col>
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.hospitalType')" name="hospitalType">
              <Select v-model:value="formState.hospitalType">
                <SelectOption
                  v-for="opt in hospitalTypeOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
        </Row>
        <Row :gutter="16">
          <Col :span="24">
            <FormItem :label="$t('page.feijian.modal.hospitalAddress')" name="hospitalAddress">
              <Input v-model:value="formState.hospitalAddress" />
            </FormItem>
          </Col>
        </Row>
        <Row :gutter="16">
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.contactPerson')" name="contactPerson">
              <Input v-model:value="formState.contactPerson" />
            </FormItem>
          </Col>
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.contactPhone')" name="contactPhone">
              <Input v-model:value="formState.contactPhone" />
            </FormItem>
          </Col>
        </Row>
      </Card>

      <!-- 检查组信息 -->
      <Card :title="$t('page.feijian.modal.teamInfo')" size="small" class="mb-4">
        <Row :gutter="16">
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.teamLeader')" name="teamLeader">
              <Input v-model:value="formState.teamLeader" />
            </FormItem>
          </Col>
        </Row>

        <Divider orientation="left" plain>{{ $t('page.feijian.modal.teamMembers') }}</Divider>

        <div
          v-for="(member, index) in formState.teamMembers"
          :key="index"
          class="mb-3"
        >
          <Row :gutter="12" align="middle">
            <Col :span="7">
              <FormItem
                :label="index === 0 ? $t('page.feijian.modal.memberName') : ''"
                :name="['teamMembers', index, 'name']"
                :rules="[{ required: true, message: '请输入姓名' }]"
              >
                <Input v-model:value="member.name" placeholder="姓名" />
              </FormItem>
            </Col>
            <Col :span="7">
              <FormItem
                :label="index === 0 ? $t('page.feijian.modal.memberRole') : ''"
                :name="['teamMembers', index, 'role']"
                :rules="[{ required: true, message: '请输入角色' }]"
              >
                <Input v-model:value="member.role" placeholder="角色" />
              </FormItem>
            </Col>
            <Col :span="7">
              <FormItem
                :label="index === 0 ? $t('page.feijian.modal.memberPhone') : ''"
                :name="['teamMembers', index, 'phone']"
              >
                <Input v-model:value="member.phone" placeholder="联系电话" />
              </FormItem>
            </Col>
            <Col :span="3" class="text-center">
              <Button
                v-if="formState.teamMembers.length > 1"
                danger
                size="small"
                shape="circle"
                @click="removeTeamMember(index)"
              >
                <template #icon><MinusCircleOutlined /></template>
              </Button>
            </Col>
          </Row>
        </div>

        <Button type="dashed" block @click="addTeamMember">
          <template #icon><PlusOutlined /></template>
          {{ $t('page.feijian.modal.addMember') }}
        </Button>
      </Card>

      <!-- 检查结果 -->
      <Card :title="$t('page.feijian.modal.resultInfo')" size="small" class="mb-4">
        <Row :gutter="16">
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.result')" name="result">
              <Select v-model:value="formState.result" allow-clear>
                <SelectOption
                  v-for="opt in resultOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :span="12">
            <FormItem :label="$t('page.feijian.modal.violationAmount')" name="violationAmount">
              <InputNumber
                v-model:value="formState.violationAmount"
                :min="0"
                :precision="2"
                style="width: 100%"
                placeholder="0.00"
              />
            </FormItem>
          </Col>
        </Row>
        <Row :gutter="16">
          <Col :span="24">
            <FormItem :label="$t('page.feijian.modal.findings')" name="findings">
              <Textarea
                v-model:value="formState.findings"
                :rows="3"
                placeholder="请输入检查发现的问题..."
              />
            </FormItem>
          </Col>
        </Row>
        <Row :gutter="16">
          <Col :span="24">
            <FormItem :label="$t('page.feijian.modal.recommendation')" name="recommendation">
              <Textarea
                v-model:value="formState.recommendation"
                :rows="3"
                placeholder="请输入处理建议..."
              />
            </FormItem>
          </Col>
        </Row>
      </Card>

      <!-- 底部按钮 -->
      <div class="flex justify-end">
        <Space>
          <Button @click="emit('cancel')">
            {{ $t('page.feijian.modal.cancel') }}
          </Button>
          <Button type="primary" @click="handleSubmit">
            {{ $t('page.feijian.modal.submit') }}
          </Button>
        </Space>
      </div>
    </Form>
  </div>
</template>

<style scoped>
.inspection-form :deep(.ant-form-item) {
  margin-bottom: 8px;
}
</style>