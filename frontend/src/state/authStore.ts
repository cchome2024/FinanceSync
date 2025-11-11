import { create } from 'zustand'
import * as SecureStore from 'expo-secure-store'
import { Platform } from 'react-native'

import { apiClient } from '@/src/services/apiClient'

export type UserRole = 'admin' | 'finance' | 'viewer'

export interface User {
  id: string
  email: string
  displayName: string
  role: UserRole
  isActive: boolean
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  hasPermission: (permission: string) => boolean
}

const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  admin: [
    'data:import',
    'data:confirm',
    'data:view',
    'data:export',
    'data:analyze',
    'nlq:query',
    'user:manage',
    'system:config',
  ],
  finance: ['data:import', 'data:confirm', 'data:view', 'data:export'],
  viewer: ['data:view', 'data:export'],
}

const TOKEN_KEY = 'auth_token'

async function getStoredToken(): Promise<string | null> {
  if (Platform.OS === 'web') {
    return localStorage.getItem(TOKEN_KEY)
  }
  return await SecureStore.getItemAsync(TOKEN_KEY)
}

async function setStoredToken(token: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    await SecureStore.setItemAsync(TOKEN_KEY, token)
  }
}

async function removeStoredToken(): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.removeItem(TOKEN_KEY)
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true })
    try {
      const response = await apiClient.post<{ access_token: string; user: User }>('/api/v1/auth/login', {
        email,
        password,
      })
      await setStoredToken(response.access_token)
      set({
        token: response.access_token,
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  logout: async () => {
    await removeStoredToken()
    set({ token: null, user: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = await getStoredToken()
    if (!token) {
      set({ token: null, user: null, isAuthenticated: false })
      return
    }

    set({ isLoading: true })
    try {
      const user = await apiClient.get<User>('/api/v1/auth/me')
      set({
        token,
        user,
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error) {
      await removeStoredToken()
      set({ token: null, user: null, isAuthenticated: false, isLoading: false })
    }
  },

  hasPermission: (permission: string) => {
    const { user } = get()
    if (!user) return false
    const permissions = ROLE_PERMISSIONS[user.role] || []
    return permissions.includes(permission)
  },
}))

