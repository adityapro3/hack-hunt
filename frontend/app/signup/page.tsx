'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { signUp } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

export default function SignUpPage() {
  const router = useRouter()
  const { setSession } = useAuthStore()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isAdminSignup, setIsAdminSignup] = useState(false)
  const [adminSignupKey, setAdminSignupKey] = useState('')

  const mutation = useMutation({
    mutationFn: signUp,
    onSuccess: (session) => {
      setSession(session)
      toast.success('Account created successfully')
      router.replace('/dashboard')
    },
    onError: () => {
      toast.error('Failed to create account')
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign Up</CardTitle>
          <CardDescription>Create your Oppora account</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              mutation.mutate({
                full_name: fullName.trim() || undefined,
                email: email.trim(),
                password,
                admin_signup_key: isAdminSignup ? adminSignupKey.trim() || undefined : undefined,
              })
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="fullName">Full Name</Label>
              <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={isAdminSignup}
                  onChange={(e) => setIsAdminSignup(e.target.checked)}
                />
                Create as admin
              </label>
              {isAdminSignup && (
                <Input
                  placeholder="Admin signup key"
                  value={adminSignupKey}
                  onChange={(e) => setAdminSignupKey(e.target.value)}
                />
              )}
            </div>

            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-4 text-center">
            Already have an account?{' '}
            <Link href="/signin" className="text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
