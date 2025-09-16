export function generateId(): string {
  return Math.random().toString(36).substr(2, 9);
}

export function generateUniqueId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function generateChatId(): string {
  return `chat_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
}

export function generateSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).substr(2, 8)}`;
}

export function generateShortId(): string {
  return Math.random().toString(36).substr(2, 6);
}

export function generateTimestampId(): string {
  return `ts_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
}

export function isValidId(id: string): boolean {
  return typeof id === 'string' && id.length > 0;
}

export function extractIdFromUrl(url: string): string | null {
  const match = url.match(/\/([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})$/);
  return match ? match[1] : null;
}