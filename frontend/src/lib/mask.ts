export function maskPracticeInput(text: string): { text: string; warned: boolean } {
  let warned = false
  const mark = () => {
    warned = true
    return '[ĐÃ CHE]'
  }
  const next = text
    .replace(/(mật\s*khẩu\s*(?:là|:)?\s*)(\S+)/gi, (_match, prefix: string) => {
      warned = true
      return `${prefix}[ĐÃ CHE]`
    })
    .replace(/(?<!\d)\d{13,19}(?!\d)/g, mark)
    .replace(/(?<!\d)\d{12}(?!\d)/g, mark)
    .replace(/(?<!\d)\d{4,8}(?!\d)/g, mark)
  return { text: next, warned }
}
