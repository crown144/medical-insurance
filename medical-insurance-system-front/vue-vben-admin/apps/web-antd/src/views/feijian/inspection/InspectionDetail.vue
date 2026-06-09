<script lang="ts" setup>
import type { FeiJianRecord } from '#/api/core/feijian';

import { $t } from '#/locales';
import {
  Card,
  Descriptions,
  DescriptionsItem,
  Divider,
  Space,
  Table,
  Tag,
  Typography,
} from 'ant-design-vue';

defineOptions({ name: 'InspectionDetail' });

const props = defineProps<{
  record: FeiJianRecord;
}>();

const { Text, Paragraph } = Typography;

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    'draft': 'default',
    'pending': 'blue',
    'in-progress': 'processing',
    'completed': 'success',
    'cancelled': 'warning',
  };
  return map[status] || 'default';
}

function getResultColor(result: string) {
  const map: Record<string, string> = {
    'none': 'default',
    'compliant': 'success',
    'minor-issue': 'warning',
    'major-issue': 'orange',
    'violation': 'red',
  };
  return map[result] || 'default';
}

const teamColumns = [
  { title: $t('page.feijian.modal.memberName'), dataIndex: 'name', key: 'name' },
  { title: $t('page.feijian.modal.memberRole'), dataIndex: 'role', key: 'role' },
  { title: $t('page.feijian.modal.memberPhone'), dataIndex: 'phone', key: 'phone' },
];
</script>

<template>
  <div class="inspection-detail">
    <!-- 基本信息 -->
    <Card :title="$t('page.feijian.modal.baseInfo')" size="small" class="mb-4">
      <Descriptions :column="2" bordered size="small">
        <DescriptionsItem :label="$t('page.feijian.modal.inspectionNo')">
          {{ record.inspectionNo }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.inspectionType')">
          {{ record.inspectionTypeLabel }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.inspectionDate')">
          {{ record.inspectionDate }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.inspectionEndDate')">
          {{ record.inspectionEndDate }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.status')">
          <Tag :color="getStatusColor(record.status)">
            {{ record.statusLabel }}
          </Tag>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.result')">
          <Tag :color="getResultColor(record.result)">
            {{ record.resultLabel }}
          </Tag>
        </DescriptionsItem>
      </Descriptions>
    </Card>

    <!-- 医疗机构信息 -->
    <Card :title="$t('page.feijian.modal.hospitalInfo')" size="small" class="mb-4">
      <Descriptions :column="2" bordered size="small">
        <DescriptionsItem :label="$t('page.feijian.modal.hospitalName')">
          {{ record.hospital.name }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.hospitalType')">
          {{ record.hospital.typeLabel }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.hospitalAddress')" :span="2">
          {{ record.hospital.address }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.contactPerson')">
          {{ record.hospital.contactPerson }}
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.contactPhone')">
          {{ record.hospital.contactPhone }}
        </DescriptionsItem>
      </Descriptions>
    </Card>

    <!-- 检查组信息 -->
    <Card :title="$t('page.feijian.modal.teamInfo')" size="small" class="mb-4">
      <Descriptions :column="2" bordered size="small">
        <DescriptionsItem :label="$t('page.feijian.modal.teamLeader')">
          {{ record.teamLeader }}
        </DescriptionsItem>
      </Descriptions>
      <Divider orientation="left" plain>{{ $t('page.feijian.modal.teamMembers') }}</Divider>
      <Table
        :columns="teamColumns"
        :data-source="record.inspectionTeam"
        :pagination="false"
        row-key="id"
        size="small"
      />
    </Card>

    <!-- 检查结果 -->
    <Card :title="$t('page.feijian.modal.resultInfo')" size="small" class="mb-4">
      <Descriptions :column="1" bordered size="small">
        <DescriptionsItem :label="$t('page.feijian.modal.violationAmount')">
          <Text type="danger" strong>
            {{ record.violationAmount > 0 ? record.violationAmount.toLocaleString() + ' 元' : '无' }}
          </Text>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.findings')">
          <Paragraph v-if="record.findings" class="mb-0">
            {{ record.findings }}
          </Paragraph>
          <Text v-else type="secondary">暂无</Text>
        </DescriptionsItem>
        <DescriptionsItem :label="$t('page.feijian.modal.recommendation')">
          <Paragraph v-if="record.recommendation" class="mb-0">
            {{ record.recommendation }}
          </Paragraph>
          <Text v-else type="secondary">暂无</Text>
        </DescriptionsItem>
      </Descriptions>
    </Card>
  </div>
</template>