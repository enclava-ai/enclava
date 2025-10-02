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
  const form = new FormData()
  form.append('file', file)
  if (extraFields) Object.entries(extraFields).forEach(([k, v]) => form.append(k, v))

  const token = await tokenManager.getAccessToken()
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: form,
  })
  if (!res.ok) {
    let details: any
    try { details = await res.json() } catch { details = await res.text() }
    throw new Error(typeof details === 'string' ? details : (details?.error || 'Upload failed'))
  }
  return await res.json()
}

