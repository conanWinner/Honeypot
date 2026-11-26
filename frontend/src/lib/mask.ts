const NOT_SECRET = /^(gì|gi|sao|đâu|dau|nào|nao)$/i

/** Warn in the composer. The server still receives the original text and masks it before saving. */
export function practiceWarning(text: string): boolean {
  const password = text.match(/mật\s*khẩu(?:\s+của\s+(?:tôi|em))?\s*(?:là|:)\s+(\S+)/i)
  if (password && !NOT_SECRET.test(password[1])) return true
  const chunks = text.match(/\d(?:[\d\s.-]{0,22}\d)?/g) ?? []
  for (const chunk of chunks) {
    const digits = chunk.replace(/\D/g, '')
    if (/^(?:19|20)\d{2}$/.test(digits)) continue
    if (/(?:triệu|nghìn|ngàn|tỷ|phút|giờ|ngày|k|%)\s*$/i.test(chunk) && digits.length <= 6) continue
    if (digits.length >= 4) return true
  }
  return false
}
