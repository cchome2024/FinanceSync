# 手机访问配置指南

## 问题说明

默认情况下，后端服务只监听 `localhost:8000`，手机无法访问。要让手机访问后台服务，需要进行以下配置。

## 配置步骤

### 1. 获取电脑的局域网 IP 地址

**macOS:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```
或者：
```bash
ipconfig getifaddr en0
```

**Linux:**
```bash
hostname -I | awk '{print $1}'
```

**Windows:**
```cmd
ipconfig
```
查找 "IPv4 地址"，通常是 `192.168.x.x` 或 `10.x.x.x`

### 2. 启动后端服务器（允许外部访问）

**方法一：使用启动脚本（推荐）**

```bash
cd backend
chmod +x start_server.sh
./start_server.sh
```

**方法二：手动启动**

```bash
cd backend
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**关键参数说明：**
- `--host 0.0.0.0`: 监听所有网络接口，允许外部访问
- `--port 8000`: 端口号（默认 8000）
- `--reload`: 开发模式，代码变更自动重启

### 3. 配置前端 API 地址

**方法一：使用环境变量文件（推荐）**

1. 复制示例文件：
```bash
cd frontend
cp .env.example.mobile .env
```

2. 编辑 `.env` 文件，将 IP 地址替换为你的电脑 IP：
```env
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000
```

3. 重启前端：
```bash
npx expo start --clear
```

**方法二：临时设置环境变量**

```bash
cd frontend
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000 npx expo start
```

### 4. 配置防火墙（如果需要）

**macOS:**
1. 系统设置 → 网络 → 防火墙
2. 点击"防火墙选项"
3. 确保允许传入连接，或添加 Python/uvicorn 到允许列表

**Linux:**
```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

**Windows:**
1. 控制面板 → 系统和安全 → Windows Defender 防火墙
2. 高级设置 → 入站规则 → 新建规则
3. 选择"端口" → TCP → 8000 → 允许连接

### 5. 验证配置

1. **在电脑浏览器测试：**
   ```
   http://你的IP:8000/health
   ```
   应该返回：`{"status":"ok"}`

2. **在手机浏览器测试：**
   - 确保手机连接到同一 Wi-Fi
   - 访问：`http://你的IP:8000/health`
   - 应该返回：`{"status":"ok"}`

3. **启动前端应用：**
   ```bash
   cd frontend
   npx expo start
   ```
   - 使用 Expo Go 扫描二维码
   - 或访问显示的 Web 地址

## 常见问题

### Q1: 手机无法连接到服务器

**检查清单：**
1. ✅ 后端是否使用 `--host 0.0.0.0` 启动？
2. ✅ 手机和电脑是否在同一 Wi-Fi 网络？
3. ✅ 防火墙是否允许 8000 端口？
4. ✅ IP 地址是否正确？
5. ✅ 前端 `.env` 文件是否配置正确？

### Q2: IP 地址经常变化

**解决方案：**
1. 在路由器中为电脑设置静态 IP
2. 或使用动态 DNS 服务
3. 或每次启动时更新 `.env` 文件

### Q3: 使用 Expo Tunnel 模式

如果局域网访问有问题，可以使用 Expo Tunnel：

```bash
cd frontend
npx expo start --tunnel
```

这会创建一个公共 URL，但速度可能较慢。

### Q4: 开发环境 vs 生产环境

**开发环境（当前）：**
- 后端：`--host 0.0.0.0` 允许局域网访问
- 前端：使用电脑 IP 地址

**生产环境：**
- 后端：部署到云服务器，使用域名
- 前端：配置生产环境 API 地址

## 快速启动命令

**一键启动（后端）：**
```bash
cd backend && ./start_server.sh
```

**一键启动（前端）：**
```bash
cd frontend && npx expo start
```

## 安全注意事项

⚠️ **开发环境警告：**
- `--host 0.0.0.0` 允许所有网络接口访问，仅用于开发
- 生产环境应使用反向代理（如 Nginx）和 HTTPS
- 不要在生产环境使用 `allow_origins=["*"]` 的 CORS 配置

