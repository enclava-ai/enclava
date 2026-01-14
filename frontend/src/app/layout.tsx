import type { Metadata, Viewport } from 'next'
import { Inter, Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/providers/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { Toaster as HotToaster } from 'react-hot-toast'
import { Toaster as Sonner } from 'sonner'
import { AuthProvider } from '@/components/providers/auth-provider'
import { ModulesProvider } from '@/contexts/ModulesContext'
import { PluginProvider } from '@/contexts/PluginContext'
import { ToastProvider } from '@/contexts/ToastContext'
import { Navigation } from '@/components/ui/navigation'

// Font configuration matching website design
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
})

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400', '500', '600', '700', '800'],
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
})

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

// Function to determine the base URL with proper protocol
const getBaseUrl = () => {
  // In production, we need to detect if we're behind HTTPS
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'https' : 'http'
    const host = process.env.NEXT_PUBLIC_BASE_URL || window.location.hostname
    return `${protocol}://${host}`
  }
  // For build time/server side, default to HTTP for dev, HTTPS for production
  const protocol = process.env.NODE_ENV === 'production' ? 'https' : 'http'
  return `${protocol}://${process.env.NEXT_PUBLIC_BASE_URL || 'localhost'}`
}

export const metadata: Metadata = {
  metadataBase: new URL(getBaseUrl()),
  title: 'Enclava Platform',
  description: 'Secure AI processing platform with plugin-based architecture and confidential computing',
  keywords: ['AI', 'Enclava', 'Confidential Computing', 'LLM', 'TEE'],
  authors: [{ name: 'Enclava Team' }],
  robots: 'index, follow',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: getBaseUrl(),
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
      <body className={`${inter.variable} ${plusJakartaSans.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            <ModulesProvider>
              <PluginProvider>
                <ToastProvider>
                  <div className="min-h-screen bg-background">
                    <Navigation />
                    <main className="container mx-auto px-4 py-8">
                      {children}
                    </main>
                  </div>
                  <Toaster />
                </ToastProvider>
                <HotToaster />
                <Sonner />
              </PluginProvider>
            </ModulesProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}