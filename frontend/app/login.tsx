import { useState, useEffect } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Platform,
  KeyboardAvoidingView,
  ScrollView,
  Switch,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useRouter } from 'expo-router'

import { useAuthStore } from '@/src/state/authStore'

export default function LoginScreen() {
  const router = useRouter()
  const { login, isAuthenticated, isLoading, checkAuth } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)

  useEffect(() => {
    // 检查是否已登录
    checkAuth()
  }, [checkAuth])

  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/(app)/dashboard')
    }
  }, [isAuthenticated, router])

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      Alert.alert('错误', '请输入用户名和密码')
      return
    }

    try {
      await login(username.trim(), password, rememberMe)
      router.replace('/(app)/dashboard')
    } catch (error: any) {
      const message = error?.body || error?.message || '登录失败，请检查用户名和密码'
      if (Platform.OS === 'web') {
        alert(message)
      } else {
        Alert.alert('登录失败', message)
      }
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
          <View style={styles.content}>
            <Text style={styles.title}>财务数据平台</Text>
            <Text style={styles.subtitle}>请登录以继续</Text>

            <View style={styles.form}>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>用户名</Text>
                <TextInput
                  style={styles.input}
                  placeholder="请输入用户名"
                  placeholderTextColor="#64748B"
                  value={username}
                  onChangeText={setUsername}
                  autoCapitalize="none"
                  autoComplete="username"
                  editable={!isLoading}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>密码</Text>
                <TextInput
                  style={styles.input}
                  placeholder="请输入密码"
                  placeholderTextColor="#64748B"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  autoComplete="password"
                  editable={!isLoading}
                  onSubmitEditing={handleLogin}
                />
              </View>

              <View style={styles.rememberMeContainer}>
                <Switch
                  value={rememberMe}
                  onValueChange={setRememberMe}
                  trackColor={{ false: '#334155', true: '#3B82F6' }}
                  thumbColor={rememberMe ? '#FFFFFF' : '#94A3B8'}
                  disabled={isLoading}
                />
                <Text style={styles.rememberMeText}>记住我（30天）</Text>
              </View>

              <TouchableOpacity
                style={[styles.button, isLoading && styles.buttonDisabled]}
                onPress={handleLogin}
                disabled={isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.buttonText}>登录</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F1420',
  },
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  content: {
    width: '100%',
    maxWidth: 400,
    alignSelf: 'center',
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#94A3B8',
    textAlign: 'center',
    marginBottom: 48,
  },
  form: {
    gap: 24,
  },
  inputGroup: {
    gap: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#E2E8F0',
  },
  input: {
    backgroundColor: '#131A2B',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    color: '#F8FAFC',
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.2)',
  },
  button: {
    backgroundColor: '#3B82F6',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  rememberMeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: -8,
  },
  rememberMeText: {
    fontSize: 14,
    color: '#E2E8F0',
  },
})

