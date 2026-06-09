"""
飞检数据导入服务
使用 ExcelColumnAnalyzer 识别列映射，然后批量导入数据
"""

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from django.core.files.uploadedfile import UploadedFile
from ..models import FeiJianImportBatch, FeiJianRawRecord
from .excel_analyzer import ExcelColumnAnalyzer, AnalysisResult, ColumnMatch


class FeiJianImporter:
    """飞检数据导入器"""

    def __init__(self, enable_llm: bool = True):
        self.analyzer = ExcelColumnAnalyzer(enable_llm=enable_llm)

    def upload_and_analyze(
        self,
        file: UploadedFile,
    ) -> Tuple[FeiJianImportBatch, AnalysisResult]:
        """
        上传文件并分析列结构

        Returns:
            (batch, analysis_result)
        """
        # 保存文件
        batch = FeiJianImportBatch.objects.create(
            file_name=file.name,
            file_size=file.size,
            status=FeiJianImportBatch.Status.ANALYZING,
        )
        batch.original_file.save(file.name, file, save=True)

        # 分析列结构
        try:
            result = self.analyzer.analyze(batch.original_file.path)

            # 更新批次信息
            batch.detected_columns = result.columns
            batch.sample_rows = result.sample_rows
            batch.column_mapping = {
                m.field_key: {
                    'column': m.column_name,
                    'confidence': round(m.confidence, 2),
                    'method': m.method,
                    'label': m.field_label,
                }
                for m in result.mappings
            }
            batch.status = FeiJianImportBatch.Status.MAPPING
            batch.save()

            return batch, result

        except Exception as e:
            batch.status = FeiJianImportBatch.Status.FAILED
            batch.error_detail = str(e)
            batch.save()
            raise

    def import_with_mapping(
        self,
        batch: FeiJianImportBatch,
        column_mapping: Dict[str, str],
    ) -> FeiJianImportBatch:
        """
        使用确认的列映射执行导入

        Args:
            batch: 导入批次
            column_mapping: 用户确认的列映射
                {"hospitalization_no": "住院号列名", "issue_category": "问题类型列名", ...}

        Returns:
            更新后的批次
        """
        batch.status = FeiJianImportBatch.Status.IMPORTING
        batch.column_mapping = column_mapping
        batch.save()

        try:
            # 读取全部数据
            df = self._read_dataframe(batch.original_file.path)
            total = len(df)
            batch.record_count = total
            batch.records.all().delete()

            records_to_create = []
            error_count = 0
            errors = []

            for idx, (_, row) in enumerate(df.iterrows()):
                try:
                    record = self._build_record(batch, idx, row, column_mapping)
                    records_to_create.append(record)
                except Exception as e:
                    error_count += 1
                    if len(errors) < 20:
                        errors.append(f"第{idx+2}行: {str(e)}")

                # 每500条批量写入
                if len(records_to_create) >= 500:
                    self._bulk_create(batch, records_to_create)
                    records_to_create = []

            # 写入剩余
            if records_to_create:
                self._bulk_create(batch, records_to_create)

            batch.success_count = total - error_count
            batch.error_count = error_count
            batch.error_detail = '\n'.join(errors) if errors else ''
            batch.status = FeiJianImportBatch.Status.SUCCESS
            batch.save()

        except Exception as e:
            batch.status = FeiJianImportBatch.Status.FAILED
            batch.error_detail = str(e)
            batch.save()
            raise

        return batch

    def _build_record(
        self,
        batch: FeiJianImportBatch,
        row_index: int,
        row: pd.Series,
        mapping: Dict[str, str],
    ) -> FeiJianRawRecord:
        """从行数据构建记录"""
        # 提取映射字段
        def get_val(field_key: str) -> str:
            col = mapping.get(field_key, '')
            if col and col in row.index:
                val = row[col]
                if pd.isna(val):
                    return ''
                return str(val).strip()
            return ''

        def get_amount(field_key: str) -> Decimal:
            col = mapping.get(field_key, '')
            if col and col in row.index:
                val = row[col]
                if pd.isna(val):
                    return Decimal('0')
                try:
                    # 处理可能的格式: "1,234.56" 或 "1234.56元"
                    cleaned = str(val).replace(',', '').replace('元', '').replace(' ', '')
                    return Decimal(cleaned)
                except (InvalidOperation, ValueError):
                    return Decimal('0')
            return Decimal('0')

        # 构建原始数据
        def clean_text(field_key: str, max_length: int) -> str:
            value = get_val(field_key)
            return value[:max_length] if len(value) > max_length else value

        raw_data = {}
        for col in row.index:
            val = row[col]
            if pd.isna(val):
                raw_data[str(col)] = ''
            elif isinstance(val, (pd.Timestamp,)):
                raw_data[str(col)] = val.strftime('%Y-%m-%d')
            else:
                raw_data[str(col)] = str(val)

        return FeiJianRawRecord(
            import_batch=batch,
            row_index=row_index,
            hospitalization_no=clean_text('hospitalization_no', 64),
            patient_name=clean_text('patient_name', 128),
            hospital_name=clean_text('hospital_name', 256),
            admission_date=clean_text('admission_date', 32),
            discharge_date=clean_text('discharge_date', 32),
            issue_category=clean_text('issue_category', 256),
            issue_description=get_val('issue_description'),
            involved_amount=get_amount('involved_amount'),
            audit_org=clean_text('audit_org', 256),
            audit_date=clean_text('audit_date', 32),
            raw_data=raw_data,
        )

    def _bulk_create(
        self,
        batch: FeiJianImportBatch,
        records: List[FeiJianRawRecord],
    ):
        """批量写入"""
        FeiJianRawRecord.objects.bulk_create(records, batch_size=500)

    def get_preview(
        self,
        batch: FeiJianImportBatch,
        column_mapping: Dict[str, str],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        用映射预览导入结果

        Returns:
            预览记录列表
        """
        df = self._read_dataframe(batch.original_file.path, nrows=limit)
        preview = []
        for idx, (_, row) in enumerate(df.iterrows()):
            record = self._build_record(batch, idx, row, column_mapping)
            preview.append({
                'row_index': idx + 2,  # Excel行号(含表头)
                'hospitalization_no': record.hospitalization_no,
                'patient_name': record.patient_name,
                'hospital_name': record.hospital_name,
                'issue_category': record.issue_category,
                'issue_description': record.issue_description[:100] if record.issue_description else '',
                'involved_amount': float(record.involved_amount),
                'audit_org': record.audit_org,
                'audit_date': record.audit_date,
            })
        return preview

    def _read_dataframe(self, file_path: str, nrows: Optional[int] = None) -> pd.DataFrame:
        """读取飞检导入文件，兼容 Excel 和 CSV。"""
        suffix = Path(file_path).suffix.lower()
        if suffix == '.csv':
            return pd.read_csv(file_path, nrows=nrows)
        return pd.read_excel(file_path, nrows=nrows)
