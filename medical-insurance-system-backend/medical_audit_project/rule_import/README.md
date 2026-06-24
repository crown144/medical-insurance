# 规则批量导入转换 (rule_import)

从药品/收费目录文件（PDF / Excel）中，通过文件解析 + LLM 抽取医保审核规则，
经人工确认后写入正式规则库 `rules.Rule`。

复用现有技术栈：Django + DRF + Celery + Redis + MySQL，结构参考 `feijian`、`tasks` 两个 app。

## 目录结构

```
rule_import/
├── models.py            # RuleImportTask（任务）/ ExtractedRule（抽取规则暂存）
├── serializers.py       # DRF 序列化器 + 参数校验
├── views.py             # Controller：上传 / 列表 / 详情 / 抽取结果 / 确认入库 / 下载 / 取消
├── urls.py              # 路由（DefaultRouter）
├── tasks.py             # Celery 异步任务 run_rule_import_task
├── admin.py             # Django admin
├── tests.py             # 16 个基础测试
├── migrations/0001_initial.py
├── sql/0001_rule_import.sql   # 可执行建表脚本（等价于迁移）
└── services/
    ├── llm_client.py    # LLM 客户端（配置驱动，超时/重试/日志）
    ├── extractor.py     # 文件解析层（PDF/Excel -> 表格），迁移自 extractor.py
    ├── rule_discovery.py# 规则抽取层（表格 -> 规则），迁移自 convert-v2.py
    ├── facade.py        # 端到端算法编排（不碰 DB）
    └── importer.py      # 输出解析落库 + 确认入库 rules.Rule
```

## 配置（环境变量，禁止硬编码）

在 `settings.py` 中已接线，部署时通过环境变量提供：

| 变量 | 说明 | 默认 |
|---|---|---|
| `RULE_IMPORT_LLM_API_KEY` | LLM 密钥（自部署模型一般不校验，可不填） | `EMPTY` |
| `RULE_IMPORT_LLM_BASE_URL` | LLM 服务**基址**(须以 `/v1` 结尾，SDK 自动拼 `/chat/completions`) | `http://127.0.0.1:9234/v1` |
| `RULE_IMPORT_LLM_MODEL_HEADER` | 判表头模型 | `qwen` |
| `RULE_IMPORT_LLM_MODEL_EXTRACT` | 规则抽取模型 | `qwen` |
| `RULE_IMPORT_LLM_TIMEOUT` | 单次请求超时(秒) | 60 |
| `RULE_IMPORT_LLM_MAX_RETRIES` | 单次请求重试次数 | 2 |
| `RULE_IMPORT_MAX_FILE_SIZE` | 上传大小上限(字节) | 50MB |
| `RULE_IMPORT_DEFAULT_CHUNK_SIZE` | LLM 分块行数（仅后端配置，前端不暴露） | 10 |
| `RULE_IMPORT_TASK_SOFT_TIME_LIMIT` | Celery 软超时(秒) | 3600 |
| `RULE_IMPORT_TASK_TIME_LIMIT` | Celery 硬超时(秒) | 3900 |

> 默认调用服务器上自部署的 OpenAI 兼容模型(`http://127.0.0.1:9234/v1`)，
> 需保证 worker 所在机器能访问该地址；如改用外部 LLM，再通过上述环境变量覆盖。

## 部署 / 启动

```bash
conda activate web   # 见 run.md
pip install pdfplumber openai tqdm   # 新增依赖（已写入 requirements.txt）
python manage.py migrate rule_import
# Celery worker（已在 celery.py 注册 rule_import.tasks）
celery -A medical_audit_project worker -l info -P eventlet
```

## 接口

| 方法 | 路径 | 说明 | 同步/异步 |
|---|---|---|---|
| POST | `/api/rule-import/upload/` | 上传文件并发起转换 | 接口同步返回，转换异步 |
| GET | `/api/rule-import/tasks/` | 任务列表（分页，?status=&search=） | 同步 |
| GET | `/api/rule-import/tasks/{id}/` | 任务详情（轮询状态/进度） | 同步 |
| GET | `/api/rule-import/tasks/{id}/rules/` | 抽取规则明细（分页，?rule_type=） | 同步 |
| POST | `/api/rule-import/tasks/{id}/confirm/` | 选中规则入库 rules.Rule | 同步 |
| GET | `/api/rule-import/tasks/{id}/download/` | 下载抽取规则 JSON | 同步 |
| POST | `/api/rule-import/tasks/{id}/cancel/` | 取消任务 | 同步 |

鉴权：沿用项目现状（`AllowAny`）。返回结构遵循 DRF 风格（列表分页 / 操作类对象 / 错误 `{"error": ...}`），未改动既有接口。

## 测试

```bash
python manage.py test rule_import
```

测试不依赖网络/LLM/pdfplumber（mock 掉 Celery 投递，直接喂算法输出验证落库与映射）。
