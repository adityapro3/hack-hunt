'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Sidebar from '@/components/layout/Sidebar'
import { useAuthStore } from '@/store/authStore'

const PUBLIC_ROUTES = ['/signin', '/signup']

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { initialize, hydrated, accessToken, user } = useAuthStore()

  useEffect(() => {
    initialize()
  }, [initialize])

  useEffect(() => {
    if (!hydrated) return

    const isPublic = PUBLIC_ROUTES.includes(pathname)

    if (!accessToken && !isPublic) {
      router.replace('/signin')
      return
    }

    if (accessToken && isPublic) {
      router.replace('/dashboard')
      return
    }

    if (pathname.startsWith('/admin') && accessToken && user && !user.is_admin) {
      router.replace('/dashboard')
    }
  }, [hydrated, accessToken, pathname, router, user])

  if (!hydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  const isPublic = PUBLIC_ROUTES.includes(pathname)

  if (isPublic) {
    return <main className="min-h-screen">{children}</main>
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-56 flex-1 min-h-screen">{children}</main>
    </div>
  )
}
