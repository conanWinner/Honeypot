import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDay(iso?: string | null) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10)
  return date.toLocaleDateString('vi-VN')
}

export function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export const GOAL_LABELS: Record<string, string> = {
  ask_identity: 'Hỏi họ là ai',
  ask_purpose: 'Hỏi mục đích',
  feign_confusion: 'Giả vờ chưa hiểu',
  stall: 'Kéo dài, chưa làm gì',
  ask_link: 'Xin đường dẫn',
  ask_transfer_destination: 'Hỏi chuyển đi đâu',
  ask_account_number: 'Hỏi số tài khoản của họ',
  read_fake_otp: 'Đọc OTP giả',
  ask_next_instruction: 'Hỏi bước tiếp theo',
  emotional_hook: 'Lộ vẻ lo, bắt nói rõ',
  probe_hook: 'Đào đúng chi tiết vừa bịa',
  close_polite: 'Khép khi kịch bản đã đủ',
}
