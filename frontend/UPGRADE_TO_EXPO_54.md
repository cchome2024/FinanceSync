# 升级到 Expo SDK 54 指南

## 升级步骤

### 1. 使用 Expo 升级工具（推荐）

```bash
cd frontend
npx expo install expo@^54.0.0
npx expo install --fix
```

这会自动更新所有 Expo 相关包到兼容版本。

### 2. 手动更新 package.json（如果需要）

如果自动升级有问题，可以手动更新以下依赖：

```json
{
  "dependencies": {
    "expo": "^54.0.0",
    "react": "18.3.1",
    "react-native": "0.76.5",
    "expo-router": "^4.0.0",
    "expo-document-picker": "~15.0.0",
    "expo-secure-store": "~14.0.0",
    "expo-splash-screen": "~0.28.0",
    "expo-status-bar": "~2.0.0",
    "react-native-gesture-handler": "~2.20.0",
    "react-native-safe-area-context": "4.12.0",
    "react-native-screens": "~4.4.0",
    "react-native-svg": "15.8.0",
    "react-native-web": "~0.20.0"
  },
  "devDependencies": {
    "@types/react": "~18.3.0",
    "@types/react-native": "~0.76.0"
  }
}
```

### 3. 安装依赖

```bash
npm install
# 或
yarn install
```

### 4. 清理缓存

```bash
npx expo start --clear
```

## 需要注意的潜在问题

### 1. **victory-native**
   - 需要确认是否支持 React Native 0.76
   - 如果不行，可能需要更新或寻找替代方案

### 2. **React Native 0.76 破坏性变更**
   - 新架构（New Architecture）可能默认启用
   - 某些第三方库可能需要更新
   - 样式系统可能有变化

### 3. **TypeScript 类型**
   - `@types/react-native` 需要更新到匹配版本
   - 可能需要更新 `@types/react`

### 4. **测试**
   - 升级后需要全面测试所有功能
   - 特别注意：
     - 文件选择（expo-document-picker）
     - 路由导航（expo-router）
     - 图表显示（victory-native）
     - 样式渲染

## 回退方案

如果升级后遇到无法解决的问题，可以回退：

```bash
git checkout frontend/package.json frontend/package-lock.json
cd frontend
npm install
```

