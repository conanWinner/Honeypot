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

async function expectPath(path, includes) {
  await page.goto(base + path, { waitUntil: 'networkidle' })
  await page.waitForURL((url) => url.pathname + url.search === includes || url.pathname === includes, { timeout: 8000 })
}

await page.goto(base + '/', { waitUntil: 'networkidle' })
await page.getByRole('heading', { name: 'Tin nhắn này có phải lừa đảo không?' }).waitFor()
await shot('home')

await page.getByRole('button', { name: 'Giả công an' }).click()
await page.getByText('Luyện tình huống này').waitFor({ timeout: 15000 })
await shot('home-ket-qua')

await page.goto(base + '/luyen-tap', { waitUntil: 'networkidle' })
await page.getByRole('heading', { name: 'Luyện tập nhận diện lừa đảo' }).waitFor()
await shot('luyen-tap')

await page.locator('button.dossier').first().click()
await page.getByRole('button', { name: 'Bắt đầu kịch bản đã chọn' }).click()
await page.getByText('Đây là mô phỏng').waitFor()
await shot('luyen-tap-chat')

const box = page.getByPlaceholder('Nhắn lại…')
await box.fill('Anh là ai vậy')
await page.getByRole('button', { name: 'Gửi' }).click()
await page.getByText('Anh là ai vậy').waitFor()
await box.fill('Tôi sẽ gọi công an phường để xác minh')
await page.getByRole('button', { name: 'Gửi' }).click()
await page.getByText('xác minh').waitFor()
await page.getByRole('button', { name: 'Gác máy / chặn' }).click()
await page.getByText('Cờ đỏ nhận ra').waitFor({ timeout: 10000 })
await shot('luyen-tap-tong-ket')

await page.goto(base + '/luyen-tap/trac-nghiem', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Lừa đảo' }).waitFor()
await shot('quiz')

await page.goto(base + '/canh-bao', { waitUntil: 'networkidle' })
await page.getByRole('heading', { name: 'Cảnh báo' }).waitFor()
await shot('canh-bao')

await page.goto(base + '/phan-tich', { waitUntil: 'networkidle' })
await page.getByRole('heading', { name: 'Trạng thái hệ thống' }).waitFor()
await shot('phan-tich')

await expectPath('/kiem-tra', '/')
await expectPath('/thu-vien', '/canh-bao?tab=kich-ban')
await expectPath('/hoi-thoai', '/phan-tich/hoi-thoai')
await expectPath('/demo', '/phan-tich/demo')

await page.setViewportSize({ width: 390, height: 844 })
for (const [path, name, heading] of [
  ['/', 'home-mobile', 'Tin nhắn này có phải lừa đảo không?'],
  ['/luyen-tap', 'luyen-tap-mobile', 'Luyện tập nhận diện lừa đảo'],
  ['/luyen-tap/trac-nghiem', 'quiz-mobile', null],
  ['/canh-bao', 'canh-bao-mobile', 'Cảnh báo'],
  ['/phan-tich', 'phan-tich-mobile', 'Phòng phân tích'],
  ['/bao-cao', 'bao-cao-mobile', 'Báo cáo lừa đảo'],
]) {
  await page.goto(base + path, { waitUntil: 'networkidle' })
  if (heading) await page.getByRole('heading', { name: heading }).waitFor()
  await shot(name)
}

await page.goto(base + '/luyen-tap', { waitUntil: 'networkidle' })
await page.locator('button.dossier').first().click()
await page.getByRole('button', { name: 'Bắt đầu kịch bản đã chọn' }).click()
await page.getByText('Đây là mô phỏng').waitFor()
await shot('luyen-tap-chat-mobile')
await page.getByRole('button', { name: 'Gác máy / chặn' }).click()
await page.getByText('Cờ đỏ nhận ra').waitFor({ timeout: 10000 })
await shot('luyen-tap-tong-ket-mobile')

await browser.close()
console.log('smoke ok')
