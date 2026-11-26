import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'

const base = process.env.SMOKE_BASE || 'http://127.0.0.1:4178'
const out = process.env.SMOKE_OUT || '/opt/cursor/artifacts'
await mkdir(out, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

async function shot(name) {
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true })
}

await page.goto(base + '/luyen-tap/trac-nghiem', { waitUntil: 'networkidle' })
await page.getByRole('heading', { name: 'Trắc nghiệm tình huống' }).waitFor()
await page.getByRole('button', { name: 'Lừa đảo' }).waitFor()
await shot('quiz-cau-hoi')
await page.getByRole('button', { name: 'Lừa đảo' }).click()
await page.getByText('Nên làm gì').waitFor()
await shot('quiz-giai-thich')
for (let step = 0; step < 7; step += 1) {
  await page.getByRole('button', { name: 'Câu tiếp' }).click()
  await page.getByRole('button', { name: 'An toàn' }).click()
}
await page.getByRole('button', { name: 'Xem điểm' }).click()
await page.getByText('Dấu hiệu còn bỏ lỡ').waitFor()
await shot('quiz-tong-ket')

await page.setViewportSize({ width: 390, height: 844 })
await page.goto(base + '/luyen-tap/trac-nghiem', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Lừa đảo' }).waitFor()
await shot('quiz-cau-hoi-mobile')
await page.getByRole('button', { name: 'Lừa đảo' }).click()
await page.getByText('Nên làm gì').waitFor()
await shot('quiz-giai-thich-mobile')

await page.setViewportSize({ width: 1280, height: 900 })
await page.goto(base + '/luyen-tap', { waitUntil: 'networkidle' })
await page.locator('button.dossier').first().click()
await page.getByRole('button', { name: 'Bắt đầu kịch bản đã chọn' }).click()
await page.getByText('Tình huống này').waitFor()
await page.getByText('Đây là mô phỏng').waitFor()
await shot('luyen-tap-tinh-huong')

await page.setViewportSize({ width: 390, height: 844 })
await shot('luyen-tap-tinh-huong-mobile')

await browser.close()
console.log('quiz screenshots ok')
