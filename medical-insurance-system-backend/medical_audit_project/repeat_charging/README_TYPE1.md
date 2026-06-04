# 1016_type1 父子重复收费集成说明

## 概述
将 `d:\medical 3\1016_type1` 的父子重复收费检测逻辑（`type_1_1014.py`）集成到现有系统的 `repeat_charging` 模块：

- 新增 `ParentChildRelation` 模型存储父子编码映射
- 新增 `FatherChildDuplicateDetector` 检测器，按时间批次识别父/子项目同时收费
- 纳入 `EnhancedDuplicateDetector.detect_all_violations` 的总检测流程

## 数据与迁移
- 迁移文件：`repeat_charging/migrations/0001_initial.py`
- 导入CSV（与原项目一致）：
  - `python manage.py import_father_child_mapping --csv "d:\\medical 3\\1016_type1\\father-child.csv" --truncate`
- 环境变量回退：`FATHER_CHILD_CSV_PATH` 可指定CSV路径，数据库为空时使用

## 接口与结果格式
- 无需新增API端点；任务执行(`tasks/tasks.py`)已统一收集违规，`Result`入库格式保持一致：
  - `violation`, `rule{rule_id,type,drug_name,description}`, `reason`, `item`, `highlights`
- 前端通过现有 `/api/results/` 获取结果，无需改动

## 测试
- 单元测试：`repeat_charging/tests/test_father_child_detector.py`
- 覆盖父子同时收费的核心路径与返回结构

## 部署步骤
1. 运行数据库迁移：`python manage.py migrate`
2. 导入父子映射：见“数据与迁移”命令
3. 执行审核任务，验证 `/api/tasks/{id}/download-json-report` 与 `/api/results/` 数据

## 注意事项
- 不修改核心框架结构和公共组件；所有逻辑位于 `repeat_charging` 应用内部
- 结果结构严格对齐现有 `ResultSerializer` 约定
- 性能：按时间批次与代码分组处理，避免全量笛卡尔积对比