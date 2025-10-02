export function generateId(prefix = "id"): string {
  const rand = Math.random().toString(36).slice(2, 10)
  return `${prefix}_${rand}`
}

export function generateShortId(prefix = "id"): string {
  const rand = Math.random().toString(36).slice(2, 7)
  return `${prefix}_${rand}`
}

export function generateTimestampId(prefix = "id"): string {
  const ts = Date.now()
  const rand = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `${prefix}_${ts}_${rand}`
}
