
## 分支规范

主分支：

```text
main
```

功能开发：

```text
feature/功能名
```

例如：

```text
feature/login
feature/order
feature/user
```

禁止直接提交到 main。

---

## 开发流程

### 1. 拉取最新代码

```bash
git checkout main
git pull
```

### 2. 创建功能分支

```bash
git checkout -b feature/login
```

### 3. 开发

```bash
git add .
git commit -m "feat: 登录功能"
```

### 4. 推送

```bash
git push origin feature/login
```

### 5. 提交 PR

```text
feature/login
    ↓
main
```

简单说明改了什么即可。

### 6. 合并

至少让另一个人看一眼。

确认没问题后合并到 main。

---

## Commit 规范

新增功能：

```text
feat: 登录功能
```

修复问题：

```text
fix: 修复登录异常
```

重构：

```text
refactor: 重构用户模块
```

文档：

```text
docs: 更新README
```

不要出现：

```text
update
修改
改一下
test
123
```

---

## 提交前检查

提交前至少保证：

```bash
npm run build
```

或

```bash
mvn package
```

能够成功执行。

不要把运行不了的代码提交到 main。

---

## 禁止提交

不要提交：

```text
node_modules
dist
target
.idea
.vscode
```

不要提交：

```text
.env
数据库密码
服务器账号
API密钥
```

---

## 冲突处理

合并前先同步 main：

```bash
git checkout main
git pull

git checkout feature/login
git merge main
```

解决冲突后再提交 PR。

---

## 原则

1. main 永远保持可运行
2. 一个功能一个分支
3. 不直接改 main
4. 合并前互相看代码
5. 提交信息写清楚

```
```
