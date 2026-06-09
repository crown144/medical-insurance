import type {
  AlignmentResult,
  AuditTask,
  DiffRecord,
  FeiJianManageRecord,
  FeiJianRawRecord,
  FeiJianStats,
  ImportFile,
} from '../../api/model/feijianModel';

/** 模拟统计数据 */
export const mockStats: FeiJianStats = {
  totalImports: 28,
  totalRawRecords: 3842,
  auditTaskCount: 18,
  alignmentRate: 87.5,
  diffCount: 156,
  unresolvedDiffCount: 42,
};

/** 模拟导入文件 */
export const mockImportFiles: ImportFile[] = [
  { id: 'f1', fileName: '湖南省2026年第一季度飞检结果.xlsx', fileSize: 2458624, recordCount: 520, importTime: '2026-06-01 09:30:00', status: 'success', statusLabel: '导入成功' },
  { id: 'f2', fileName: '长沙市飞检专项检查结果.csv', fileSize: 1024576, recordCount: 180, importTime: '2026-05-25 14:15:00', status: 'success', statusLabel: '导入成功' },
  { id: 'f3', fileName: '株洲市2026年5月飞检通报.xlsx', fileSize: 3312896, recordCount: 640, importTime: '2026-05-20 10:00:00', status: 'success', statusLabel: '导入成功' },
  { id: 'f4', fileName: '湘潭市飞检回头看结果.xlsx', fileSize: 876544, recordCount: 95, importTime: '2026-05-15 16:45:00', status: 'success', statusLabel: '导入成功' },
  { id: 'f5', fileName: '常德市医保飞检报告（6月）.xlsx', fileSize: 5242880, recordCount: 0, importTime: '2026-06-05 11:20:00', status: 'processing', statusLabel: '处理中' },
];

/** 模拟原始记录 */
export const mockRawRecords: FeiJianRawRecord[] = [
  { id: 'r1', importBatchId: 'f1', hospitalizationNo: 'HN20260501001', patientName: '张建国', hospitalName: '湖南省人民医院', admissionDate: '2026-04-15', dischargeDate: '2026-04-28', issueCategory: '分解住院', issueDescription: '将一次住院分解为两次，套取医保基金', involvedAmount: 23500, auditOrg: '国家医保局飞检组', auditDate: '2026-05-10' },
  { id: 'r2', importBatchId: 'f1', hospitalizationNo: 'HN20260501002', patientName: '李美华', hospitalName: '湖南省人民医院', admissionDate: '2026-04-20', dischargeDate: '2026-05-05', issueCategory: '过度检查', issueDescription: '无指征进行全套生化检查及CT检查', involvedAmount: 8600, auditOrg: '国家医保局飞检组', auditDate: '2026-05-10' },
  { id: 'r3', importBatchId: 'f1', hospitalizationNo: 'HN20260501003', patientName: '王德发', hospitalName: '湖南省人民医院', admissionDate: '2026-04-10', dischargeDate: '2026-04-22', issueCategory: '虚假住院', issueDescription: '实际未住院，伪造住院记录套取基金', involvedAmount: 45200, auditOrg: '国家医保局飞检组', auditDate: '2026-05-11' },
  { id: 'r4', importBatchId: 'f2', hospitalizationNo: 'CS20260520001', patientName: '赵小明', hospitalName: '长沙市中心医院', admissionDate: '2026-05-01', dischargeDate: '2026-05-08', issueCategory: '超标准收费', issueDescription: '护理费、床位费超标准收取', involvedAmount: 3200, auditOrg: '湖南省医保局飞检组', auditDate: '2026-05-20' },
  { id: 'r5', importBatchId: 'f2', hospitalizationNo: 'CS20260520002', patientName: '陈丽丽', hospitalName: '长沙市中心医院', admissionDate: '2026-05-05', dischargeDate: '2026-05-15', issueCategory: '重复收费', issueDescription: '同日重复收取诊疗项目费用', involvedAmount: 5600, auditOrg: '湖南省医保局飞检组', auditDate: '2026-05-20' },
  { id: 'r6', importBatchId: 'f3', hospitalizationNo: 'ZZ20260518001', patientName: '刘伟强', hospitalName: '株洲市第一人民医院', admissionDate: '2026-05-01', dischargeDate: '2026-05-12', issueCategory: '挂床住院', issueDescription: '患者实际未在院，虚挂床位', involvedAmount: 18700, auditOrg: '湖南省医保局飞检组', auditDate: '2026-05-18' },
  { id: 'r7', importBatchId: 'f3', hospitalizationNo: 'ZZ20260518002', patientName: '孙晓芳', hospitalName: '株洲市第一人民医院', admissionDate: '2026-04-25', dischargeDate: '2026-05-10', issueCategory: '超限定用药', issueDescription: '超医保限定支付范围使用抗生素', involvedAmount: 12800, auditOrg: '湖南省医保局飞检组', auditDate: '2026-05-18' },
  { id: 'r8', importBatchId: 'f4', hospitalizationNo: 'XT20260510001', patientName: '周文博', hospitalName: '湘潭市中心医院', admissionDate: '2026-04-28', dischargeDate: '2026-05-06', issueCategory: '串换药品', issueDescription: '将自费药品串换为医保目录内药品', involvedAmount: 9500, auditOrg: '湘潭市医保局', auditDate: '2026-05-10' },
];

/** 模拟审查任务 */
export const mockAuditTasks: AuditTask[] = [
  { id: 't1', taskName: '湖南省人民医院飞检审查', importBatchId: 'f1', totalCases: 520, status: 'completed', statusLabel: '已完成', progress: 100, createdAt: '2026-06-01 10:00:00', completedAt: '2026-06-01 14:30:00' },
  { id: 't2', taskName: '长沙市中心医院飞检审查', importBatchId: 'f2', totalCases: 180, status: 'completed', statusLabel: '已完成', progress: 100, createdAt: '2026-05-25 15:00:00', completedAt: '2026-05-25 17:20:00' },
  { id: 't3', taskName: '株洲市第一人民医院飞检审查', importBatchId: 'f3', totalCases: 640, status: 'completed', statusLabel: '已完成', progress: 100, createdAt: '2026-05-20 11:00:00', completedAt: '2026-05-21 09:15:00' },
  { id: 't4', taskName: '湘潭市中心医院飞检审查', importBatchId: 'f4', totalCases: 95, status: 'running', statusLabel: '进行中', progress: 65, createdAt: '2026-05-15 17:00:00' },
  { id: 't5', taskName: '常德市飞检审查', importBatchId: 'f5', totalCases: 0, status: 'pending', statusLabel: '待执行', progress: 0, createdAt: '2026-06-05 11:30:00' },
];

/** 模拟对齐结果 */
export const mockAlignmentResults: AlignmentResult[] = [
  { id: 'a1', auditTaskId: 't1', hospitalizationNo: 'HN20260501001', feijianIssue: '分解住院', feijianAmount: 23500, feijianCategory: '分解住院', systemIssue: '分解住院（两次住院间隔≤3天）', systemAmount: 23500, systemCategory: '分解住院', matchStatus: 'matched', matchStatusLabel: '完全匹配' },
  { id: 'a2', auditTaskId: 't1', hospitalizationNo: 'HN20260501002', feijianIssue: '过度检查', feijianAmount: 8600, feijianCategory: '过度检查', systemIssue: '无指征检查（CT+全套生化）', systemAmount: 8600, systemCategory: '过度检查', matchStatus: 'matched', matchStatusLabel: '完全匹配' },
  { id: 'a3', auditTaskId: 't1', hospitalizationNo: 'HN20260501003', feijianIssue: '虚假住院', feijianAmount: 45200, feijianCategory: '虚假住院', systemIssue: '', systemAmount: 0, systemCategory: '', matchStatus: 'unmatched', matchStatusLabel: '仅飞检发现' },
  { id: 'a4', auditTaskId: 't2', hospitalizationNo: 'CS20260520001', feijianIssue: '超标准收费', feijianAmount: 3200, feijianCategory: '超标准收费', systemIssue: '床位费超标收取', systemAmount: 2800, systemCategory: '超标准收费', matchStatus: 'partial', matchStatusLabel: '部分匹配' },
  { id: 'a5', auditTaskId: 't2', hospitalizationNo: 'CS20260520002', feijianIssue: '重复收费', feijianAmount: 5600, feijianCategory: '重复收费', systemIssue: '诊疗项目重复计费', systemAmount: 5600, systemCategory: '重复收费', matchStatus: 'matched', matchStatusLabel: '完全匹配' },
  { id: 'a6', auditTaskId: 't3', hospitalizationNo: 'ZZ20260518001', feijianIssue: '挂床住院', feijianAmount: 18700, feijianCategory: '挂床住院', systemIssue: '住院期间无诊疗记录', systemAmount: 18700, systemCategory: '挂床住院', matchStatus: 'matched', matchStatusLabel: '完全匹配' },
  { id: 'a7', auditTaskId: 't3', hospitalizationNo: 'ZZ20260518002', feijianIssue: '超限定用药', feijianAmount: 12800, feijianCategory: '超限定用药', systemIssue: '', systemAmount: 0, systemCategory: '', matchStatus: 'unmatched', matchStatusLabel: '仅飞检发现' },
];

/** 模拟差异记录 */
export const mockDiffRecords: DiffRecord[] = [
  { id: 'd1', auditTaskId: 't1', hospitalizationNo: 'HN20260501001', patientName: '张建国', hospitalName: '湖南省人民医院', issueSummary: '分解住院', feijianFindings: '2026-04-15至04-28被拆分为两次住院', systemFindings: '系统已识别为分解住院，金额一致', discrepancyType: 'amount-mismatch', discrepancyTypeLabel: '金额差异', amountDiff: 0, severity: 'low', severityLabel: '低', status: 'reviewed', statusLabel: '已复核', remark: '金额已核对一致' },
  { id: 'd2', auditTaskId: 't1', hospitalizationNo: 'HN20260501003', patientName: '王德发', hospitalName: '湖南省人民医院', issueSummary: '虚假住院', feijianFindings: '飞检发现实际未住院，伪造住院记录', systemFindings: '系统未检出该虚假住院行为', discrepancyType: 'feijian-extra', discrepancyTypeLabel: '飞检多发现', amountDiff: 45200, severity: 'high', severityLabel: '高', status: 'confirmed', statusLabel: '已确认' },
  { id: 'd3', auditTaskId: 't2', hospitalizationNo: 'CS20260520001', patientName: '赵小明', hospitalName: '长沙市中心医院', issueSummary: '超标准收费-金额差异', feijianFindings: '飞检认定超标准收费3200元', systemFindings: '系统识别超标收费2800元', discrepancyType: 'amount-mismatch', discrepancyTypeLabel: '金额差异', amountDiff: 400, severity: 'medium', severityLabel: '中', status: 'pending', statusLabel: '待处理' },
  { id: 'd4', auditTaskId: 't3', hospitalizationNo: 'ZZ20260518002', patientName: '孙晓芳', hospitalName: '株洲市第一人民医院', issueSummary: '超限定用药', feijianFindings: '飞检发现超限定使用抗生素12800元', systemFindings: '系统未识别出该用药限制问题', discrepancyType: 'feijian-extra', discrepancyTypeLabel: '飞检多发现', amountDiff: 12800, severity: 'high', severityLabel: '高', status: 'pending', statusLabel: '待处理' },
  { id: 'd5', auditTaskId: 't1', hospitalizationNo: 'HN20260501004', patientName: '吴大伟', hospitalName: '湖南省人民医院', issueSummary: '系统额外发现-过度诊疗', feijianFindings: '飞检未涉及此项', systemFindings: '系统审查发现理疗项目过度使用', discrepancyType: 'system-extra', discrepancyTypeLabel: '系统多发现', amountDiff: 6800, severity: 'medium', severityLabel: '中', status: 'confirmed', statusLabel: '已确认' },
  { id: 'd6', auditTaskId: 't2', hospitalizationNo: 'CS20260520003', patientName: '黄丽萍', hospitalName: '长沙市中心医院', issueSummary: '分类不一致-违规vs超限', feijianFindings: '飞检定性为违规收费', systemFindings: '系统定性为超限定支付范围', discrepancyType: 'category-mismatch', discrepancyTypeLabel: '分类差异', amountDiff: 3500, severity: 'medium', severityLabel: '中', status: 'pending', statusLabel: '待处理' },
];

/** 模拟管理记录 */
export const mockManageRecords: FeiJianManageRecord[] = [
  { id: 'm1', hospitalizationNo: 'HN20260501001', patientName: '张建国', hospitalName: '湖南省人民医院', importBatchId: 'f1', importDate: '2026-06-01', issueCategory: '分解住院', issueDescription: '将一次住院分解为两次', involvedAmount: 23500, auditTaskId: 't1', auditStatus: '已完成', matchStatus: '完全匹配', diffSeverity: '低', diffStatus: '已复核', status: 'resolved', statusLabel: '已办结' },
  { id: 'm2', hospitalizationNo: 'HN20260501002', patientName: '李美华', hospitalName: '湖南省人民医院', importBatchId: 'f1', importDate: '2026-06-01', issueCategory: '过度检查', issueDescription: '无指征进行全套生化及CT检查', involvedAmount: 8600, auditTaskId: 't1', auditStatus: '已完成', matchStatus: '完全匹配', diffSeverity: '-', diffStatus: '-', status: 'aligned', statusLabel: '已对齐' },
  { id: 'm3', hospitalizationNo: 'HN20260501003', patientName: '王德发', hospitalName: '湖南省人民医院', importBatchId: 'f1', importDate: '2026-06-01', issueCategory: '虚假住院', issueDescription: '实际未住院，伪造住院记录', involvedAmount: 45200, auditTaskId: 't1', auditStatus: '已完成', matchStatus: '仅飞检发现', diffSeverity: '高', diffStatus: '已确认', status: 'diff-analyzed', statusLabel: '已分析' },
  { id: 'm4', hospitalizationNo: 'CS20260520001', patientName: '赵小明', hospitalName: '长沙市中心医院', importBatchId: 'f2', importDate: '2026-05-25', issueCategory: '超标准收费', issueDescription: '护理费、床位费超标准收取', involvedAmount: 3200, auditTaskId: 't2', auditStatus: '已完成', matchStatus: '部分匹配', diffSeverity: '中', diffStatus: '待处理', status: 'diff-analyzed', statusLabel: '已分析' },
  { id: 'm5', hospitalizationNo: 'CS20260520002', patientName: '陈丽丽', hospitalName: '长沙市中心医院', importBatchId: 'f2', importDate: '2026-05-25', issueCategory: '重复收费', issueDescription: '同日重复收取诊疗项目费用', involvedAmount: 5600, auditTaskId: 't2', auditStatus: '已完成', matchStatus: '完全匹配', diffSeverity: '-', diffStatus: '-', status: 'aligned', statusLabel: '已对齐' },
  { id: 'm6', hospitalizationNo: 'ZZ20260518001', patientName: '刘伟强', hospitalName: '株洲市第一人民医院', importBatchId: 'f3', importDate: '2026-05-20', issueCategory: '挂床住院', issueDescription: '患者实际未在院，虚挂床位', involvedAmount: 18700, auditTaskId: 't3', auditStatus: '已完成', matchStatus: '完全匹配', diffSeverity: '-', diffStatus: '-', status: 'aligned', statusLabel: '已对齐' },
  { id: 'm7', hospitalizationNo: 'ZZ20260518002', patientName: '孙晓芳', hospitalName: '株洲市第一人民医院', importBatchId: 'f3', importDate: '2026-05-20', issueCategory: '超限定用药', issueDescription: '超医保限定支付范围使用抗生素', involvedAmount: 12800, auditTaskId: 't3', auditStatus: '已完成', matchStatus: '仅飞检发现', diffSeverity: '高', diffStatus: '待处理', status: 'diff-analyzed', statusLabel: '已分析' },
  { id: 'm8', hospitalizationNo: 'XT20260510001', patientName: '周文博', hospitalName: '湘潭市中心医院', importBatchId: 'f4', importDate: '2026-05-15', issueCategory: '串换药品', issueDescription: '将自费药品串换为医保目录内药品', involvedAmount: 9500, auditTaskId: 't4', auditStatus: '进行中', matchStatus: '-', diffSeverity: '-', diffStatus: '-', status: 'audited', statusLabel: '审查中' },
];