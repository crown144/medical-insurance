# 统一门户用户权限集成

本应用实现统一门户规范中的 6 个用户权限 action：

| action | URL |
|---|---|
| `app_admin_set` | `POST /api/portal/actions/app-admin-set` |
| `query_user_status` | `POST /api/portal/actions/query-user-status` |
| `remove_user` | `POST /api/portal/actions/remove-user` |
| `disable_user` | `POST /api/portal/actions/disable-user` |
| `enable_user` | `POST /api/portal/actions/enable-user` |
| `default_role_callback` | `POST /api/portal/actions/default-role` |

响应统一为 `{"code": 0, "message": "操作成功", "data": ...}`。写操作使用数据库事务和行锁，重复调用会收敛到相同的最终状态。

## 环境变量

| 变量 | 说明 |
|---|---|
| `PORTAL_BASE_URL` | 门户 API 基址 |
| `PORTAL_APP_ID` | 应用 ID |
| `PORTAL_USER_DETAIL_PATH` | 3.7.1 用户详情路径 |
| `PORTAL_REQUEST_TIMEOUT_SECONDS` | 门户请求超时，默认 10 秒 |
| `PORTAL_ENCRYPT_ENABLED` | `true/false`，是否启用 SM2/SM3 |
| `PORTAL_PUBLIC_KEY` | 门户 SM2 公钥，原始十六进制格式 |
| `PORTAL_APP_PUBLIC_KEY` | 应用 SM2 公钥，原始十六进制格式 |
| `PORTAL_APP_PRIVATE_KEY` | 应用 SM2 私钥，原始十六进制格式 |

开启加密后，请求体使用 `{"data": "<base64 ciphertext>"}`，并通过 `eywa-signature` 请求头传递 SM3withSM2 签名。响应只加密 `data`，并在 `App-Signature` 响应头返回应用签名。密文模式为 C1C2C3。

私钥只能通过受控的服务器环境变量注入，不得提交到 Git。

## 发布

发布前执行：

```text
python manage.py migrate --plan
python manage.py migrate
```

由于新增了 `gmssl` 及其密码学依赖，发布时需完整重建后端镜像，不能只覆盖应用代码。
