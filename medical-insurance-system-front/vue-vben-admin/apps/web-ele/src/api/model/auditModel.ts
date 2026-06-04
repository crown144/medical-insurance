// src/api/model/auditModel.ts

export interface ViolationItem {
  id: string;
  name: string;
  isViolation: '否' | '是';
  violationType: string;
  violationDetail: string;
  rule: string;
  ruleDetail: string;
  queryKeyword: string;
  analysis: string;
  evidenceText: string;
}

export interface AuditResponse {
  violations: ViolationItem[];
}

export interface AuditParams {
  template_id: string;
  patient_data: Record<string, any>;
}
