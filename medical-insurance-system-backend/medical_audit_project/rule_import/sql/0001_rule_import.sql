-- ============================================================
-- 规则批量导入转换 (rule_import) — 可执行建表脚本
-- 数据库: medical_insurance (MySQL)
-- 说明: 与 Django 迁移 rule_import/migrations/0001_initial.py 等价。
--       正式部署推荐用 `python manage.py migrate`；
--       本脚本供 DBA 手工建表或核对使用。
-- 生成自: python manage.py sqlmigrate rule_import 0001
-- ============================================================

USE `medical_insurance`;

-- 任务表
CREATE TABLE `rule_import_ruleimporttask` (
  `id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `task_name` varchar(255) NOT NULL,
  `status` varchar(20) NOT NULL,
  `stage` varchar(20) NOT NULL,
  `progress` integer NOT NULL,
  `original_file` varchar(100) NULL,
  `file_name` varchar(512) NOT NULL,
  `file_size` bigint NOT NULL,
  `file_type` varchar(10) NOT NULL,
  `params` json NOT NULL,
  `table_count` integer NOT NULL,
  `rule_count` integer NOT NULL,
  `imported_count` integer NOT NULL,
  `error_detail` longtext NOT NULL,
  `celery_task_id` varchar(64) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `started_at` datetime(6) NULL,
  `finished_at` datetime(6) NULL
);

-- 抽取规则暂存表
CREATE TABLE `rule_import_extractedrule` (
  `id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `seq` integer NOT NULL,
  `rule_type` varchar(40) NOT NULL,
  `constrained_object` varchar(255) NOT NULL,
  `constraint_value` longtext NOT NULL,
  `evidence` json NOT NULL,
  `source` json NOT NULL,
  `is_selected` bool NOT NULL,
  `is_imported` bool NOT NULL,
  `imported_rule_id` varchar(50) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `import_task_id` bigint NOT NULL
);

-- 索引与外键
CREATE INDEX `rule_import_ruleimporttask_status_5a91218c`
  ON `rule_import_ruleimporttask` (`status`);
CREATE INDEX `rule_import_status_346b8a_idx`
  ON `rule_import_ruleimporttask` (`status`);

ALTER TABLE `rule_import_extractedrule`
  ADD CONSTRAINT `rule_import_extracte_import_task_id_25db5fde_fk_rule_impo`
  FOREIGN KEY (`import_task_id`) REFERENCES `rule_import_ruleimporttask` (`id`);

CREATE INDEX `rule_import_extractedrule_rule_type_6394b476`
  ON `rule_import_extractedrule` (`rule_type`);
CREATE INDEX `rule_import_rule_ty_c36b91_idx`
  ON `rule_import_extractedrule` (`rule_type`);
CREATE INDEX `rule_import_import__8c0c2d_idx`
  ON `rule_import_extractedrule` (`import_task_id`, `seq`);
