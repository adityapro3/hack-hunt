'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { signIn } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

export default function SignInPage() {
  const router = useRouter()
  const { setSession } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: signIn,
    onSuccess: (session) => {
      setSession(session)
      toast.success('Signed in successfully')
      router.replace('/dashboard')
    },
    onError: () => {
      toast.error('Invalid email or password')
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign In</CardTitle>
          <CardDescription>Access your Oppora account</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              mutation.mutate({ email: email.trim(), password })
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-4 text-center">
            New user?{' '}
            <Link href="/signup" className="text-primary hover:underline">
              Create account
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
