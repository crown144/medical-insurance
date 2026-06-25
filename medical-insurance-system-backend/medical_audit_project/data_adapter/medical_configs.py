from typing import Any, Dict


def build_converter_config() -> Dict[str, Any]:
    module_mappings = {
        "病理": {"住院流水号": "INHOS_NO", "检查流水号": "PTHLG_RCD_NO", "临床诊断": "DIAG_DSCPT", "病理检查类型": "PTHLG_EXAM_TP_NM",
                 "检查项目": "EXAM_ITM_NM", "标本部位": "BPSY_PRT_NM", "标本来源": "SPCM_CLLT_WAY_NM", "标本类型": "SPCM_CGY_NM",
                 "病理诊断结果": "PTHLG_DIAG", "镜下所见": "EXAM_RPT_RSLT_MICSCPC",
                 "肉眼所见": "EXAM_RPT_RSLT_MACSCPC", "报告内容": "",
                 "免疫组化结果": "IMNHSTCHMCL_DTCT_RSLT", "检查时间": "EXAM_DT",
                 "报告时间": "RPT_DT", "TNM分期": "TNM_STG_VRSN", "病理分期": "PTHLG_STG"},
        "医嘱": {"医嘱号": "ODR_NO", "医嘱组号": "ODR_GRP_NO", "住院流水号": "INHOS_NO", "医嘱类型名称": "ODR_ITM_TP_NM",
                 "医嘱类型": "ODR_ITM_TP_CD", "医嘱下达时间": "ODR_OPN_DT_TM", "医嘱开始时间": "ODR_STRT_DT", "状态": "ODR_EXEC_STTS_NM",
                 "医嘱停止时间": "ODR_STP_DT_TM", "医嘱ID": "ODR_SQNC_NO", "医嘱项类别": "ODR_ITM_CD",
                 "医嘱项目名称": "ODR_ITM_NM", "医嘱项规格": "DRG_SPCF", "单次剂量": "DRG_USE_ONCE_DOSG",
                 "剂量单位": "DRG_USE_ONCE_DOSG_UNT",
                 "单次给药数量": "DRG_USE_TOT_DOSG", "药物使用总剂量单位": "DRG_USE_TOT_DOSG_UNT", "给药途径": "DOS_RUT_NM",
                 "使用频率": "DRG_USE_FRQ_NM"},
        "检查": {"住院流水号": "INHOS_NO", "检查ID": "EXAM_RCD_NO", "检查项目类型": "EXAM_ITM_TP_NM",
                 "检查项目": "EXAM_ITM_NM", "检查部位": "EXAM_PRT_NM", "检查所见": "EXAM_RPT_RSLT_OBJCT",
                 "检查结论": "EXAM_RSLT", "图像分析": "EXAM_RPT_RSLT_SBJCT", "检查描述": "EXAM_PRCS_DSCPT", "申请时间": "APL_DT_TM",
                 "检查时间": "EXAM_DT", "报告时间": "EXAM_RPT_DT"},
        "检验": {"住院流水号": "INHOS_NO", "检验ID": "TEST_RCD_NO", "检验项目": "TEST_ITM_NM",
                "检测值": "TEST_RSLT_VLU", "单位": "TEST_RSLT_VLU_UNT",
                 "正常值上限": "NML_VLU_MAX", "正常值下限": "NML_VLU_MIN", "申请时间": "APL_DT_TM",
                 "检验时间": "TEST_DT", "报告时间": "TEST_RPT_DT", "检验详情": "",
                 "院内检验子项目代码": "TEST_CHD_ITM_CD", "院内检验子项目名称": "TEST_CHD_ITM_NM"},
        "诊断": {"住院流水号": "INHOS_NO", "ICD10编码": "DIAG_ICD10_CD", "诊断编号": "DIAG_RCD_NO", "ICD10名称": "DIAG_ICD10_NM",
                 "诊断时间": "DIAG_DT", "诊断名称": "DIAG_DSCPT", "诊断类型": "DIAG_CGY_NM",
                 "院内诊断编码": "DIAG_CD"},
        "诊断信息": {"住院流水号": "INHOS_NO", "诊断名称": "DIAG_NM", "ICD编码": "DIAG_CD",
                   "诊断排序": "DIAG_SRL_NO", "主诊断标志": "MAIN_DIAG_FLG"},
        "病案首页诊断信息": {"住院流水号": "INHOS_NO", "出院主要诊断编码": "DIAG_CD",
                      "出院主要诊断名称": "DIAG_NM", "入院诊断编码": "INHOS_CDT_CD",
                      "主诊断标识": "MAIN_DIAG_FLG"},
        "医保": {
            "医疗保险类别代码": "MDCR_CGY_CD",
            "医疗保险类别名称": "MDCR_CGY_NM",
            "性别": "GDR_NM",
            "年龄": "AGE",
            "年龄单位": "AGE_UNT",
        },
        "收费": {
            "住院号": "INHOS_NO",
            "收费项目名称": "CHRG_ITM_NM",
            "收费项目代码": "CHRG_ITM_CD",
            "收费日期": "CHRG_DT",
            "项目数量": "ITM_QTY",
            "项目单价": "ITM_UNT_PRICE",
            "项目单位": "ITM_UNT",
            "项目费用": "ITM_FEE",
            "费用类别": "FEE_CGY_NM",
            "ORDER_NO": "ORDER_NO",
            "ORDER_ITEM_CODE": "ORDER_ITEM_CODE",
        },
        "用药信息": {
            "药品名": "CHRG_ITM_NM",
            "药品类别": "FEE_CGY_NM",
            "药品通用名": "DRG_CMN_NM",
            "药品国家编码": "MDCR_DRG_CD_CTRY",
            "药品收费时间": "CHRG_DT"
        },
        "手术记录": {
            "住院流水号": "INHOS_NO",
            "记录时间": "CRT_TM",
            "手术日期": "OPRT_DT_TM",
            "手术开始时间": "OPRT_STRT_DT_TM",
            "手术结束时间": "OPRT_END_DT_TM",
            "手术编码": "OPRT_CD",
            "手术名称": "OPRT_NM",
            "术前主要诊断编码": "POPRT_DIAG_CD",
            "术前主要诊断名称": "POPRT_DIAG_NM",
            "术后主要诊断编码": "OPRT_AFTR_DIAG_CD",
            "术后主要诊断名称": "OPRT_AFTR_DIAG_NM",
            "文档内容": "OPRT_RCD_DCMT_CTT",
            "输血成份类型1": "INTOPRT_TRSFS_ITM",
            "输血量1": "TRSFS_VLU",
            "术前诊断": "POPRT_DIAG_NM",
            "术后诊断": "OPRT_AFTR_DIAG_NM",
            "手术经过": "OPRT_PRCS_DSCPT",
            "术中出血": "HMHG_VLU",
            "手术方式": "OPRT_WAY_DSCPT",
            "麻醉方式": "ATHS_WAY_NM",
            "手术者及助手姓名": "OPRT_DCT_NM",
            "麻醉医生": "ATHS_DCT_NM",
            "手术部位": "OPRT_PRT_NM",
            "切口类别": "OPRT_INCS_CGY_NM",
            "手术级别代码": "OPRT_LVL_CD",
            "手术级别": "OPRT_LVL_NM",
            "手术体位代码": "OPRT_PSTN_CD",
            "手术体位名称": "OPRT_PSTN_NM",
            "皮肤消毒描述": "SKIN_DSINFCT_DSCPT"
        },
        "化疗记录": {
            "化疗药品名称": "化疗药品名称",
            "药品剂量": "药品剂量",
            "化疗方案": "化疗方案",
            "化疗周期": "化疗周期",
            "化疗日期": "化疗日期",
            "化疗反应": "化疗反应",
            "化疗效果": "化疗效果",
            "备注": "备注"
        },
        "病案首页手术信息": {
            "住院流水号": "INHOS_NO",
            "手术操作编码": "OPRT_CD",
            "手术操作名称": "OPRT_NM",
            "主手术标识": "MAIN_OPRT_FLG"
        },
        "病案首页": {
            "住院流水号": "INHOS_NO",
            "医疗机构名称": "MDC_ORG_NM",
            "实际住院天数": "PRCTCL_INHOS_DAYS",
            "入院途径": "ADMN_RUT_NM",
            "离院方式": "DSCG_WAY_CD",
            "有无药物过敏": "DRG_ALGN_FLG",
            "过敏药物名称": "ALGN_DRG",
            "入院诊断编码": "ADMN_DIAG_ICD10_CD",
            "入院诊断名称": "ADMN_DIAG_ICD10_NM",
            "出院主要诊断编码": "DSCG_MAIN_DIAG_ICD10_CD",
            "出院主要诊断名称": "DSCG_MAIN_DIAG_ICD10_NM",
            "主要病理号": "PTHLG_NO",
            "主要病理诊断名称": "PTHLG_DIAG_NM",
            "主要病理诊断编码": "PTHLG_DIAG_CD",
            "主要手术操作编码": "OPRT_CD",
            "主要手术操作名称": "OPRT_NM",
            "主要手术操作日期": "OPRT_DT",
        }
    }

    nursing_mapping = {
        "护理记录名": "出院小结(死亡小结)",
        "时间": "",
        "内容": {
            "基本信息": {
                "出院诊断": "CDT_TNOVR_NM", "床号": "BED_NO", "科别": "ADMN_DPT_NM",
                "入院时间": "ADMN_DT_TM", "出院时间": "DSCG_DT_TM", "姓名": "NM",
                "性别": "GDR_NM", "年龄": "AGE", "住院号": "INHOS_NO",
                "入院诊断": "ADMN_DIAG_WTM_DIAG_NM",
                "年龄单位": "AGE_UNT"
            },
            "入院时简要病史": "BRF_DSES_HST",
            "体检摘要": "",
            "生命体征": {
                "T": "TPR", "P": "PLS_RATE", "R": "BRTH_FRQ", "BP高": "STLC_PRS", "BP低": "DTLC_PRS"
            },
            "住院期间医疗情况": "",
            "出院时情况": "DSCG_CDT",
            "病程与治疗情况": "DIAG_TRTMT_PRCS_DSCPT",
            "出院后用药建议": "DSCG_ODR",
            "病人信息": {
                "姓名": "NM", "性别": "GDR_NM", "科室": "ADMN_DPT_NM", "床号": "BED_NO",
                "住院号": "INHOS_NO", "住院流水号": "INHOS_NO", "年龄": "AGE", "出生年月": "",
                "入院时间": "ADMN_DT_TM", "出院时间": "DSCG_DT_TM"
            }
        }
    }

    assessment_mapping = {"文书名": "", "时间": "", "基础评估": "", "置管状态": ""}

    fields_to_concat = {
        "病理": {"报告内容": ["EXAM_RPT_RSLT_MICSCPC", "EXAM_RPT_RSLT_MACSCPC"]},
        "手术记录": {"手术经过": ["OPRT_PRCS_DSCPT", "OPRT_WAY_DSCPT"]},
        "护理记录": {
            "入院诊断": ["ADMN_DIAG_WTM_DIAG_NM", "ADMN_DIAG_TCM_DSES_NM"],
            "住院期间医疗情况": ["MAIN_TEST_RSLT", "LBRTR_EXAM_MAIN_CSTT", "ESPCL_EXAM", "PSTV_AXLR_EXAM_RSLT",
                             "OTHR_MDC_DSPST"]
        }
    }

    fields_with_units = {
        "手术记录": {
            "费用相关": {
                "fields": ["TRTMT_TP_OPRT_TRTMT_FEE", "TRTMT_TP_OPRT_FEE_ATHS_FEE", "TRTMT_TP_OPRT_FEE_OPRT_FEE"],
                "units": ["元", "元", "元"],
                "prefixes": ["治疗类-手术治疗费", "治疗类-手术治疗费-麻醉费", "治疗类-手术治疗费-手术费"]
            },
            "术中出血": {"field": "HMHG_VLU", "unit": "ml"}
        },
        "检验": {
            "检验结果": {"field": "TEST_RSLT_VLU", "unit_field": "TEST_RSLT_VLU_UNT"},
            "检验详情": {"field": "TEST_RSLT_VLU", "unit_field": "TEST_RSLT_VLU_UNT"}
        },
        "护理记录": {
            "体检摘要": {"fields": ["HGT", "WGT"], "units": ["cm", "kg"]}
        },
        "医嘱": {
            "单次剂量": {"field": "DRG_USE_ONCE_DOSG", "unit_field": "DRG_USE_ONCE_DOSG_UNT"},
            "单次给药数量": {"field": "DRG_USE_TOT_DOSG", "unit_field": "DRG_USE_TOT_DOSG_UNT"}
        }
    }

    return {
        "module_mappings": module_mappings,
        "nursing_mapping": nursing_mapping,
        "assessment_mapping": assessment_mapping,
        "fields_to_concat": fields_to_concat,
        "fields_with_units": fields_with_units,
    }


def build_module_queries(inhos_no: str, mdc_org_cd: str) -> Dict[str, str]:
    return {
        "病理": f"""
                SELECT rcd.INHOS_NO as RCD_INHOS_NO, rcd.PTHLG_RCD_NO, rcd.PTHLG_EXAM_TP_NM, rcd.EXAM_ITM_NM, rcd.BPSY_PRT_NM, rcd.SPCM_CLLT_WAY_NM, rcd.SPCM_CGY_NM, rcd.EXAM_DT,
                    rpt.PTHLG_DIAG, rpt.EXAM_RPT_RSLT_MICSCPC, rpt.EXAM_RPT_RSLT_MACSCPC,
                    rpt.IMNHSTCHMCL_DTCT_RSLT, rpt.EXAM_RSLT, rpt.RPT_DT,
                    rpt.TNM_STG_VRSN, rpt.PTHLG_STG,
                    rcd.PTHLG_RCD_NO as RCD_PTHLG_RCD_NO, rpt.PTHLG_RCD_NO as RPT_PTHLG_RCD_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rpt.INVLD_FLG as RPT_INVLD_FLG,
                    GROUP_CONCAT(DISTINCT diag.DIAG_DSCPT SEPARATOR '，') as DIAG_DSCPT
                FROM ODS_FACT_PTHLG_RCD rcd
                LEFT JOIN ODS_FACT_PTHLG_RPT rpt ON rcd.PTHLG_RCD_NO = rpt.PTHLG_RCD_NO AND rcd.MDC_ORG_CD = rpt.MDC_ORG_CD
                LEFT JOIN ODS_FACT_INHOS_DIAG_INFMT diag ON rcd.INHOS_NO = diag.INHOS_NO AND rcd.MDC_ORG_CD = diag.MDC_ORG_CD AND diag.INVLD_FLG = 0
                WHERE rcd.INHOS_NO = '{inhos_no}' AND rcd.MDC_ORG_CD = '{mdc_org_cd}'
                GROUP BY rcd.INHOS_NO, rcd.PTHLG_RCD_NO, rcd.PTHLG_EXAM_TP_NM, rcd.EXAM_ITM_NM, rcd.BPSY_PRT_NM, rcd.SPCM_CLLT_WAY_NM, rcd.SPCM_CGY_NM, rcd.EXAM_DT,
                    rpt.PTHLG_DIAG, rpt.EXAM_RPT_RSLT_MICSCPC, rpt.EXAM_RPT_RSLT_MACSCPC,
                    rpt.IMNHSTCHMCL_DTCT_RSLT, rpt.EXAM_RSLT, rpt.RPT_DT,
                    rpt.TNM_STG_VRSN, rpt.PTHLG_STG,
                    rcd.PTHLG_RCD_NO, rpt.PTHLG_RCD_NO,
                    rcd.INVLD_FLG, rpt.INVLD_FLG;
            """,
        "医嘱": f"""
                SELECT ODR_NO, ODR_GRP_NO, ODR_OPN_DT_TM, ODR_STRT_DT, ODR_END_DT, ODR_SQNC_NO, INHOS_NO, ODR_ITM_TP_NM,
                    ODR_ITM_TP_CD, ODR_EXEC_STRT_DT, ODR_EXEC_CPLT_DT, ODR_EXEC_STTS_NM,
                    ODR_STP_DT_TM, ODR_ITM_CD, ODR_ITM_NM, DRG_SPCF, DRG_USE_ONCE_DOSG,
                    DRG_USE_ONCE_DOSG_UNT, DRG_USE_TOT_DOSG, DRG_USE_TOT_DOSG_UNT,
                    DOS_RUT_NM, DRG_USE_FRQ_NM, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_ODR_INFMT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "检查": f"""
                SELECT DISTINCT
                    rcd.INHOS_NO as INHOS_NO, rcd.EXAM_RCD_NO as EXAM_RCD_NO, rcd.EXAM_ITM_TP_NM, rcd.EXAM_PRT_NM, rcd.EXAM_ITM_NM,
                    rcd.EXAM_PRCS_DSCPT, rcd.APL_DT_TM, rcd.EXAM_DT,
                    rpt.EXAM_RPT_RSLT_OBJCT, rpt.EXAM_RSLT, rpt.EXAM_RPT_RSLT_SBJCT, rpt.EXAM_RPT_DT,
                    rpt.EXAM_RCD_NO as RPT_EXAM_RCD_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rpt.INVLD_FLG as RPT_INVLD_FLG
                FROM ODS_FACT_EXAM_RCD rcd
                LEFT JOIN ODS_FACT_EXAM_RPT rpt ON rcd.EXAM_RCD_NO = rpt.EXAM_RCD_NO AND rcd.MDC_ORG_CD = rpt.MDC_ORG_CD
                WHERE rcd.INHOS_NO = '{inhos_no}' AND rcd.MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "检验": f"""
                SELECT DISTINCT
                    rcd.INHOS_NO as RCD_INHOS_NO, rcd.TEST_RCD_NO, rcd.APL_DT_TM, rcd.TEST_DT, rcd.TEST_RPT_DT,
                    rcd.TEST_ITM_NM as RCD_TEST_ITM_NM, rcd.TEST_ITM_TP_NM, rslt.TEST_RSLT, rslt.TEST_RSLT_VLU,
                    rslt.TEST_RSLT_VLU_UNT, rslt.NML_VLU_MAX, rslt.NML_VLU_MIN, rslt.TEST_ITM_NM as RSLT_TEST_ITM_NM,
                    rslt.TEST_CHD_ITM_CD, rslt.TEST_CHD_ITM_NM,
                    rcd.TEST_RPT_NO as RCD_TEST_RPT_NO, rslt.TEST_RPT_NO as RSLT_TEST_RPT_NO,
                    rcd.INVLD_FLG as RCD_INVLD_FLG, rslt.INVLD_FLG as RSLT_INVLD_FLG
                FROM ODS_FACT_TEST_RCD rcd
                LEFT JOIN ODS_FACT_TEST_RPT_CVT_RSLT rslt
                ON rcd.TEST_RPT_NO = rslt.TEST_RPT_NO AND rcd.TEST_ITM_NM = rslt.TEST_ITM_NM AND rcd.MDC_ORG_CD = rslt.MDC_ORG_CD
                WHERE rcd.INHOS_NO = '{inhos_no}' AND rcd.MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "诊断": f"""
                SELECT INHOS_NO, DIAG_ICD10_CD,DIAG_ICD10_NM, DIAG_RCD_NO, DIAG_DT, DIAG_DSCPT, DIAG_CGY_NM, DIAG_CD, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_DIAG_INFMT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "入院主要诊断": f"""
                SELECT INHOS_NO, DIAG_ICD10_CD, DIAG_ICD10_NM, DIAG_DT, DIAG_RCD_NO, DIAG_CGY_NM, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_DIAG_INFMT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}' AND DIAG_CGY_NM = '入院诊断'
                ORDER BY DIAG_DT, DIAG_RCD_NO
                LIMIT 1;
            """,
        "出院主要诊断": f"""
                SELECT INHOS_NO, DIAG_ICD10_CD, DIAG_ICD10_NM, DIAG_DT, DIAG_RCD_NO, DIAG_CGY_NM, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_DIAG_INFMT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}' AND DIAG_CGY_NM = '出院主要诊断'
                ORDER BY DIAG_DT, DIAG_RCD_NO
                LIMIT 1;
            """,
        "诊断信息": f"""
                SELECT INHOS_NO, DIAG_NM, DIAG_CD, DIAG_SRL_NO, MAIN_DIAG_FLG, MDC_ORG_CD
                FROM ODS_FACT_MDC_RCD_HMPG_DIAG
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "病案首页诊断信息": f"""
                SELECT INHOS_NO, DIAG_CD, DIAG_NM, INHOS_CDT_CD, MAIN_DIAG_FLG, MDC_ORG_CD
                FROM ODS_FACT_MDC_RCD_HMPG_DIAG
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}' AND MAIN_DIAG_FLG = 1;
            """,
        "用药信息": f"""
                SELECT
                    fee.CHRG_ITM_NM,
                    fee.FEE_CGY_NM,
                    fee.CHRG_DT,
                    fee.CHRG_ITM_CD,
                    fee.PRM_KEY,
                    fee.CHRG_RTRN_FLG,
                    drug_dim.DRG_CMN_NM,
                    drug_dim.MDCR_DRG_CD_CTRY
                FROM ODS_FACT_INHOS_FEE_DTL fee
                LEFT JOIN (
                    SELECT MDC_ORG_CD, DRG_CD,
                           MAX(DRG_CMN_NM) AS DRG_CMN_NM,
                           MAX(MDCR_DRG_CD_CTRY) AS MDCR_DRG_CD_CTRY
                    FROM ODS_DIM_DRG_INFMT
                    GROUP BY MDC_ORG_CD, DRG_CD
                ) drug_dim
                  ON drug_dim.DRG_CD = fee.CHRG_ITM_CD
                 AND drug_dim.MDC_ORG_CD = fee.MDC_ORG_CD
                WHERE fee.INHOS_NO = '{inhos_no}' AND fee.MDC_ORG_CD = '{mdc_org_cd}'
                    AND fee.FEE_CGY_NM IN ('中成药', '中草药', '西药')
                    AND fee.CHRG_RTRN_FLG = 1
                    AND fee.INVLD_FLG = 0
                ORDER BY fee.CHRG_ITM_NM, fee.CHRG_DT;
            """,
        "手术记录": f"""
                SELECT
                    o.INHOS_NO,
                    o.CRT_TM,
                    o.OPRT_DT_TM,
                    o.OPRT_STRT_DT_TM,
                    o.OPRT_END_DT_TM,
                    o.OPRT_CD,
                    o.OPRT_NM,
                    o.MAIN_OPRT_FLG,
                    d.POPRT_DIAG_CD AS POPRT_DIAG_CD,
                    d.POPRT_DIAG_NM AS POPRT_DIAG_NM,
                    d.OPRT_AFTR_DIAG_CD AS OPRT_AFTR_DIAG_CD,
                    d.OPRT_AFTR_DIAG_NM AS OPRT_AFTR_DIAG_NM,
                    r.OPRT_RCD_DCMT_CTT,
                    o.INTOPRT_TRSFS_ITM,
                    o.TRSFS_VLU,
                    o.OPRT_PRCS_DSCPT,
                    o.HMHG_VLU,
                    o.OPRT_WAY_DSCPT,
                    o.ATHS_WAY_NM,
                    o.OPRT_DCT_NM,
                    o.ATHS_DCT_NM,
                    o.OPRT_PRT_NM,
                    o.OPRT_INCS_CGY_NM,
                    o.OPRT_LVL_CD,
                    o.OPRT_LVL_NM,
                    o.OPRT_PSTN_CD,
                    o.OPRT_PSTN_NM,
                    o.SKIN_DSINFCT_DSCPT,
                    o.INVLD_FLG as O_INVLD_FLG
                FROM ODS_FACT_OPRT_EXEC_INFMT o
                LEFT JOIN (
                    SELECT
                        x.POPRT_DIAG_CD,
                        x.POPRT_DIAG_NM,
                        x.OPRT_AFTR_DIAG_CD,
                        x.OPRT_AFTR_DIAG_NM
                    FROM ODS_FACT_OPRT_EXEC_INFMT x
                    WHERE x.INHOS_NO = '{inhos_no}' AND x.MDC_ORG_CD = '{mdc_org_cd}'
                      AND x.MAIN_OPRT_FLG = 1
                      AND (x.INVLD_FLG = 0 OR x.INVLD_FLG IS NULL)
                    ORDER BY COALESCE(x.OPRT_DT_TM, x.CRT_TM) DESC
                    LIMIT 1
                ) d ON 1 = 1
                LEFT JOIN (
                    SELECT
                        rr.INHOS_NO,
                        rr.MDC_ORG_CD,
                        GROUP_CONCAT(
                            CONCAT(COALESCE(rr.ITM_NM, ''), '：', COALESCE(rr.ITM_VLU, ''))
                            ORDER BY rr.CRT_TM DESC, rr.OPRT_RCD_NO, rr.ITM_NUM
                            SEPARATOR '\n'
                        ) AS OPRT_RCD_DCMT_CTT
                    FROM ODS_FACT_OPRT_RCD_S rr
                    WHERE rr.INHOS_NO = '{inhos_no}' AND rr.MDC_ORG_CD = '{mdc_org_cd}'
                      AND (rr.INVLD_FLG = 0 OR rr.INVLD_FLG IS NULL)
                    GROUP BY rr.INHOS_NO, rr.MDC_ORG_CD
                ) r ON r.INHOS_NO = o.INHOS_NO AND r.MDC_ORG_CD = o.MDC_ORG_CD
                WHERE o.INHOS_NO = '{inhos_no}' AND o.MDC_ORG_CD = '{mdc_org_cd}'
                  AND (o.INVLD_FLG = 0 OR o.INVLD_FLG IS NULL)
                ORDER BY COALESCE(o.OPRT_DT_TM, o.CRT_TM) DESC
                ;
            """,
        "病案首页手术信息": f"""
                SELECT INHOS_NO, OPRT_CD, OPRT_NM, MAIN_OPRT_FLG, MDC_ORG_CD
                FROM ODS_FACT_MDC_RCD_HMPG_OPRT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "收费": f"""
                SELECT
                    fee.INHOS_NO,
                    fee.CHRG_ITM_NM,
                    fee.CHRG_ITM_CD,
                    fee.CHRG_DT,
                    fee.ITM_QTY,
                    fee.ITM_UNT_PRICE,
                    fee.ITM_UNT,
                    fee.ITM_FEE,
                    fee.FEE_CGY_NM,
                    fee.PRM_KEY,
                    fee.CHRG_RTRN_FLG,
                    fee.MDC_ORG_CD
                FROM ODS_FACT_INHOS_FEE_DTL fee
                WHERE fee.INHOS_NO = '{inhos_no}' AND fee.MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "医保": f"""
                SELECT DISTINCT INHOS_NO, MDCR_CGY_CD, MDCR_CGY_NM, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_FEE_STLMT
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "病案首页": f"""
                SELECT
                    m.INHOS_NO,
                    m.MDC_ORG_NM,
                    m.PRCTCL_INHOS_DAYS,
                    m.ADMN_RUT_NM,
                    m.DSCG_WAY_CD,
                    m.DRG_ALGN_FLG,
                    m.ALGN_DRG,
                    admn_diag.DIAG_ICD10_CD AS ADMN_DIAG_ICD10_CD,
                    admn_diag.DIAG_ICD10_NM AS ADMN_DIAG_ICD10_NM,
                    dscg_diag.DIAG_ICD10_CD AS DSCG_MAIN_DIAG_ICD10_CD,
                    dscg_diag.DIAG_ICD10_NM AS DSCG_MAIN_DIAG_ICD10_NM,
                    m.PTHLG_NO,
                    m.PTHLG_DIAG_NM,
                    m.PTHLG_DIAG_CD,
                    main_oprt.OPRT_DT,
                    main_oprt.OPRT_CD,
                    main_oprt.OPRT_NM
                FROM ODS_FACT_MDC_RCD_HMPG m
                LEFT JOIN (
                    SELECT d.INHOS_NO, d.MDC_ORG_CD, d.DIAG_ICD10_CD, d.DIAG_ICD10_NM
                    FROM ODS_FACT_INHOS_DIAG_INFMT d
                    WHERE d.INHOS_NO = '{inhos_no}' AND d.MDC_ORG_CD = '{mdc_org_cd}'
                      AND d.DIAG_CGY_NM = '入院诊断'
                      AND (d.INVLD_FLG = 0 OR d.INVLD_FLG IS NULL)
                    ORDER BY d.DIAG_DT, d.DIAG_RCD_NO
                    LIMIT 1
                ) admn_diag ON admn_diag.INHOS_NO = m.INHOS_NO AND admn_diag.MDC_ORG_CD = m.MDC_ORG_CD
                LEFT JOIN (
                    SELECT d.INHOS_NO, d.MDC_ORG_CD, d.DIAG_ICD10_CD, d.DIAG_ICD10_NM
                    FROM ODS_FACT_INHOS_DIAG_INFMT d
                    WHERE d.INHOS_NO = '{inhos_no}' AND d.MDC_ORG_CD = '{mdc_org_cd}'
                      AND d.DIAG_CGY_NM = '出院主要诊断'
                      AND (d.INVLD_FLG = 0 OR d.INVLD_FLG IS NULL)
                    ORDER BY d.DIAG_DT, d.DIAG_RCD_NO
                    LIMIT 1
                ) dscg_diag ON dscg_diag.INHOS_NO = m.INHOS_NO AND dscg_diag.MDC_ORG_CD = m.MDC_ORG_CD
                LEFT JOIN (
                    SELECT o.INHOS_NO, o.MDC_ORG_CD, o.OPRT_DT, o.OPRT_CD, o.OPRT_NM
                    FROM ODS_FACT_MDC_RCD_HMPG_OPRT o
                    WHERE o.INHOS_NO = '{inhos_no}' AND o.MDC_ORG_CD = '{mdc_org_cd}'
                      AND o.MAIN_OPRT_FLG = 1
                    ORDER BY o.OPRT_DT, o.OPRT_CD, o.OPRT_NM
                    LIMIT 1
                ) main_oprt ON main_oprt.INHOS_NO = m.INHOS_NO AND main_oprt.MDC_ORG_CD = m.MDC_ORG_CD
                WHERE m.INHOS_NO = '{inhos_no}' AND m.MDC_ORG_CD = '{mdc_org_cd}'
                LIMIT 1;
            """,
        "入出院文书合并": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_MDC_HTR_RCD_S
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "病程文书合并": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "入院记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_MDC_HTR_RCD_S
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}' AND RCD_TP_NM NOT IN ('出院记录', '疾病诊断证明');
            """,
        "首次病程记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE RCD_TP_NM LIKE '%首次病程记录%' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "上级医生查房记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE RCD_TP_NM LIKE '%医师查房记录%' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "日常病程记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE RCD_TP_NM LIKE '%日常病程记录%' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "化疗记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE RCD_TP_NM LIKE '%化疗记录%' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "出院记录": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_MDC_HTR_RCD_S
                WHERE RCD_TP_NM LIKE '%出院记录%' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "在院评估单": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_INHOS_CRS_RCD_S
                WHERE RCD_TP_NM = '在院评估单' AND INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """,
        "手术记录详情": f"""
                SELECT *, INVLD_FLG, MDC_ORG_CD
                FROM ODS_FACT_OPRT_RCD_S
                WHERE INHOS_NO = '{inhos_no}' AND MDC_ORG_CD = '{mdc_org_cd}';
            """
    }
