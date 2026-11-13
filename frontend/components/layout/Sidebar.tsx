'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  LayoutDashboard,
  Code2,
  Bookmark,
  ClipboardList,
  Newspaper,
  MessageSquare,
  Mail,
  Shield,
  LogOut,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/hackathons', label: 'Hackathons', icon: Code2 },
  { href: '/bookmarks', label: 'Bookmarks', icon: Bookmark },
  { href: '/tracker', label: 'Tracker', icon: ClipboardList },
  { href: '/chat', label: 'SeerAI', icon: MessageSquare },
  { href: '/news', label: 'ScrollAI', icon: Newspaper },
  { href: '/emails', label: 'ScribeAI', icon: Mail },
]

const bottomItems = [
  { href: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, clearSession } = useAuthStore()

  const isAdmin = !!user?.is_admin

  return (
    <aside className="fixed left-0 top-0 h-full w-56 border-r border-border bg-card flex flex-col z-30">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
          <Image src="/favicon1.png" alt="Oppora" width={18} height={18} className="rounded-sm" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-none text-foreground">Oppora</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">Opportunity Oracle</p>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/')
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                active
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom nav */}
      <div className="px-2 py-3 border-t border-border space-y-0.5">
        {isAdmin && (
          <Link
            href="/admin"
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
              pathname === '/admin'
                ? 'bg-primary/15 text-primary'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            <Shield className="h-4 w-4 flex-shrink-0" />
            Admin
          </Link>
        )}

        {bottomItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                active
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          )
        })}

        <button
          type="button"
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors text-muted-foreground hover:bg-muted hover:text-foreground"
          onClick={() => {
            clearSession()
            router.replace('/signin')
          }}
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          Sign Out
        </button>
      </div>
    </aside>
  )
}
