import { Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { AdminPage } from './pages/AdminPage'
import { ChatPage } from './pages/ChatPage'
import { CheckPage } from './pages/CheckPage'
import { DemoPage } from './pages/DemoPage'
import { HomePage } from './pages/HomePage'
import { IntelPage } from './pages/IntelPage'
import { LibraryPage } from './pages/LibraryPage'
import { ScriptPage } from './pages/ScriptPage'
import { TrendsPage } from './pages/TrendsPage'
import { WarningsPage } from './pages/WarningsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<HomePage />} />
        <Route path="hoi-thoai" element={<ChatPage />} />
        <Route path="hoi-thoai/:id" element={<ChatPage />} />
        <Route path="thu-vien" element={<LibraryPage />} />
        <Route path="kich-ban/:id" element={<ScriptPage />} />
        <Route path="kiem-tra" element={<CheckPage />} />
        <Route path="xu-huong" element={<TrendsPage />} />
        <Route path="canh-bao" element={<WarningsPage />} />
        <Route path="mang-luoi" element={<IntelPage />} />
        <Route path="kiem-duyet" element={<AdminPage />} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="*" element={<p className="text-ink-soft">Không có trang này.</p>} />
      </Route>
    </Routes>
  )
}
