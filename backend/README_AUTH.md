# 权限控制系统说明

## 概述

FinanceSync 实现了基于角色的访问控制（RBAC）系统，支持三种角色：
- **admin**: 管理员，拥有所有权限
- **finance**: 财务人员，可以录入、确认、查看和导出数据
- **viewer**: 查看者，只能查看和导出数据

## 快速开始

### 1. 运行数据库迁移

```bash
cd backend
poetry run alembic upgrade head
```

### 2. 创建第一个管理员用户

```bash
poetry run python scripts/create_admin.py admin@example.com your_password "管理员"
```

### 3. 启动后端服务

```bash
poetry run uvicorn app.main:app --reload
```

### 4. 启动前端应用

```bash
cd frontend
npm install  # 安装新依赖（expo-secure-store）
npm start
```

### 5. 登录

访问前端应用，使用创建的管理员账户登录。

## API 端点

### 认证相关

- `POST /api/v1/auth/register` - 注册新用户（需要管理员权限）
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/auth/me` - 获取当前用户信息（需要认证）

### 权限要求

所有 API 端点（除了登录和注册）都需要在请求头中包含 JWT token：

```
Authorization: Bearer <token>
```

## 权限映射

| 权限 | admin | finance | viewer |
|------|-------|---------|--------|
| data:import | ✅ | ✅ | ❌ |
| data:confirm | ✅ | ✅ | ❌ |
| data:view | ✅ | ✅ | ✅ |
| data:export | ✅ | ✅ | ✅ |
| data:analyze | ✅ | ❌ | ❌ |
| nlq:query | ✅ | ❌ | ❌ |
| user:manage | ✅ | ❌ | ❌ |
| system:config | ✅ | ❌ | ❌ |

## 环境变量

在 `.env` 文件中配置 JWT 密钥：

```env
JWT_SECRET_KEY=your-secret-key-change-in-production
```

## 前端集成

前端使用 `useAuthStore` 管理认证状态：

```typescript
import { useAuthStore } from '@/src/state/authStore'

// 登录
await login(email, password)

// 登出
await logout()

// 检查权限
const hasPermission = hasPermission('data:import')

// 获取当前用户
const user = useAuthStore((state) => state.user)
```

## 权限保护组件

使用 `PermissionGuard` 组件保护需要特定权限的功能：

```tsx
import { PermissionGuard } from '@/components/common/PermissionGuard'

<PermissionGuard permission="data:import">
  <Button>导入数据</Button>
</PermissionGuard>
```

## 注意事项

1. **单公司场景**: 当前实现为单公司场景，不需要用户-公司关系表
2. **Token 过期**: JWT token 默认有效期为 24 小时
3. **密码安全**: 密码使用 bcrypt 加密存储
4. **向后兼容**: `ImportJob` 表保留了 `initiator_id` 和 `initiator_role` 字段以保持向后兼容

