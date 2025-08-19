import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/providers/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { Toaster as HotToaster } from 'react-hot-toast'
import { AuthProvider } from '@/contexts/AuthContext'
import { ModulesProvider } from '@/contexts/ModulesContext'
import { Navigation } from '@/components/ui/navigation'

const inter = Inter({ subsets: ['latin'] })

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export const metadata: Metadata = {
  metadataBase: new URL('http://localhost:3000'),
  title: 'AI Gateway Platform',
  description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
  keywords: ['AI', 'Gateway', 'Confidential Computing', 'LLM', 'TEE'],
  authors: [{ name: 'AI Gateway Team' }],
  robots: 'index, follow',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'http://localhost:3000',
    title: 'AI Gateway Platform',
    description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
    siteName: 'AI Gateway',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AI Gateway Platform',
    description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            <ModulesProvider>
              <div className="min-h-screen bg-background">
                <Navigation />
                <main className="container mx-auto px-4 py-8">
                  {children}
                </main>
              </div>
              <Toaster />
              <HotToaster />
            </ModulesProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}