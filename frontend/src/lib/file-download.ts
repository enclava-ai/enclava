import { tokenManager } from './token-manager'

export async function downloadFile(path: string, filename: string, params?: URLSearchParams | Record<string, string>) {
  const url = new URL(path, typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')
  if (params) {
    const p = params instanceof URLSearchParams ? params : new URLSearchParams(params)
    p.forEach((v, k) => url.searchParams.set(k, v))
  }

  const token = await tokenManager.getAccessToken()
  const res = await fetch(url.toString(), {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!res.ok) throw new Error(`Failed to download file (${res.status})`)
  const blob = await res.blob()

  if (typeof window !== 'undefined') {
    const link = document.createElement('a')
    const href = URL.createObjectURL(blob)
    link.href = href
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(href)
  }
}

export async function uploadFile(path: string, file: File, extraFields?: Record<string, string>) {
  if (typeof path !== 'string' || path.length === 0) {
    throw new TypeError('uploadFile path must be a non-empty string')
  }

  // Ensure path starts with / and construct full URL
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const url = `${typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'}${cleanPath}`

  // Debug logging
  console.log('uploadFile called with:', { path: cleanPath, url, fileName: file.name, fileSize: file.size })

  const form = new FormData()
  form.append('file', file)
  if (extraFields) {
    console.log('Adding extra fields:', extraFields)
    Object.entries(extraFields).forEach(([k, v]) => form.append(k, v))
  }

  const token = await tokenManager.getAccessToken()
  console.log('Making request to:', url)

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
    })

    console.log('Response status:', res.status, res.statusText)

    if (!res.ok) {
      const rawError = await res.text()
      console.log('Error payload:', rawError)

      let details: any
      try {
        details = rawError ? JSON.parse(rawError) : undefined
      } catch {
        details = rawError
      }

      const message = typeof details === 'string'
        ? details
        : details?.detail || details?.error || `Upload failed (${res.status})`

      throw new Error(message)
    }

    const result = await res.json()
    console.log('Upload successful:', result)
    return result
  } catch (error) {
    console.error('Upload failed:', error)
    throw error
  }
}
