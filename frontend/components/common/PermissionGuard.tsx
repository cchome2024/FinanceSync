import { ReactNode } from 'react'
import { useAuthStore } from '@/src/state/authStore'

interface PermissionGuardProps {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}

export function PermissionGuard({ permission, children, fallback = null }: PermissionGuardProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission(permission))

  if (!hasPermission) {
    return <>{fallback}</>
  }

  return <>{children}</>
}

