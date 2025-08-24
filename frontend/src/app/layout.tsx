import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/providers/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { Toaster as HotToaster } from 'react-hot-toast'
import { AuthProvider } from '@/contexts/AuthContext'
import { ModulesProvider } from '@/contexts/ModulesContext'
import { PluginProvider } from '@/contexts/PluginContext'
import { Navigation } from '@/components/ui/navigation'

const inter = Inter({ subsets: ['latin'] })

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'),
  title: 'Enclava Platform',
  description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
  keywords: ['AI', 'Enclava', 'Confidential Computing', 'LLM', 'TEE'],
  authors: [{ name: 'Enclava Team' }],
  robots: 'index, follow',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
    title: 'Enclava Platform',
    description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
    siteName: 'Enclava',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Enclava Platform',
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
              <PluginProvider>
                <div className="min-h-screen bg-background">
                  <Navigation />
                  <main className="container mx-auto px-4 py-8">
                    {children}
                  </main>
                </div>
                <Toaster />
                <HotToaster />
              </PluginProvider>
            </ModulesProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}