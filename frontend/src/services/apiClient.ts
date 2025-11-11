import { Platform } from 'react-native'

const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export class HttpError extends Error {
  status: number
  body: string

  constructor(message: string, status: number, body: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.body = body
  }
}

import { useAuthStore } from '@/src/state/authStore'

export type FetchOptions = RequestInit & {
  authToken?: string
}

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const url = `${baseURL}${path}`
  const headers: HeadersInit = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  }

  // 优先使用传入的token，否则从store获取
  const token = options.authToken || useAuthStore.getState().token
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const init: RequestInit = { ...options, headers }

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(options.body)
  }

  const response = await fetch(url, init)
  if (!response.ok) {
    const text = await response.text()
    throw new HttpError(`Request failed: ${response.status}`, response.status, text)
  }

  if (response.status === 204) {
    return undefined as unknown as T
  }

  const contentType = response.headers.get('Content-Type') ?? ''
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }

  if (Platform.OS === 'web') {
    return (await response.text()) as unknown as T
  }

  throw new Error('Unsupported response format')
}

export const apiClient = {
  get: <T>(path: string, options?: FetchOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: FetchOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: FetchOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: FetchOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
}
