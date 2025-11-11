import { useEffect, useState } from 'react'
import { Stack, useRouter, useSegments } from 'expo-router'

import { useAuthStore } from '@/src/state/authStore'

export default function RootLayout() {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore()
  const segments = useSegments()
  const router = useRouter()
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false)

  useEffect(() => {
    const initAuth = async () => {
      await checkAuth()
      setHasCheckedAuth(true)
    }
    initAuth()
  }, [checkAuth])

  useEffect(() => {
    // 等待认证检查完成后再进行路由判断
    if (!hasCheckedAuth || isLoading) return

    const inAuthGroup = segments[0] === 'login'

    if (!isAuthenticated && !inAuthGroup) {
      // 未登录，重定向到登录页
      router.replace('/login')
    } else if (isAuthenticated && inAuthGroup) {
      // 已登录，重定向到仪表板
      router.replace('/(app)/dashboard')
    }
  }, [isAuthenticated, isLoading, segments, router, hasCheckedAuth])

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'fade',
        contentStyle: { backgroundColor: '#0F1420' },
      }}
    />
  )
}

