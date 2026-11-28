import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { Shell } from './components/Shell'
import { AdminPage } from './pages/AdminPage'
import { AnalystLayout, ArchitecturePage, SystemStatusPage } from './pages/AnalystLayout'
import { ChatPage } from './pages/ChatPage'
import { DebriefPage } from './pages/DebriefPage'
import { DemoPage } from './pages/DemoPage'
import { DestinationsPage } from './pages/DestinationsPage'
import { DossierPage } from './pages/DossierPage'
import { HomePage } from './pages/HomePage'
import { IntelPage } from './pages/IntelPage'
import { QuizPage } from './pages/QuizPage'
import { ReportPage } from './pages/ReportPage'
import { ScriptPage } from './pages/ScriptPage'
import { SimulationPage } from './pages/SimulationPage'
import { TrainingHubPage } from './pages/TrainingHubPage'
import { TrendsPage } from './pages/TrendsPage'
import { VictimHelpPage } from './pages/VictimHelpPage'
import { WarningsPage } from './pages/WarningsPage'

function LegacyScriptRedirect() {
  const { id } = useParams()
  return <Navigate to={`/canh-bao/kich-ban/${id ?? ''}`} replace />
}

function LegacyChatRedirect() {
  const { id } = useParams()
  return <Navigate to={id ? `/phan-tich/hoi-thoai/${id}` : '/phan-tich/hoi-thoai'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<HomePage />} />
        <Route path="luyen-tap" element={<TrainingHubPage />} />
        <Route path="luyen-tap/trac-nghiem" element={<QuizPage />} />
        <Route path="luyen-tap/:sessionId/ket-qua" element={<DebriefPage />} />
        <Route path="luyen-tap/:sessionId" element={<SimulationPage />} />
        <Route path="canh-bao" element={<WarningsPage />} />
        <Route path="canh-bao/kich-ban/:id" element={<ScriptPage />} />
        <Route path="xu-huong" element={<TrendsPage />} />
        <Route path="bao-cao" element={<ReportPage />} />
        <Route path="bi-lua" element={<VictimHelpPage />} />
        <Route path="phan-tich" element={<AnalystLayout />}>
          <Route index element={<SystemStatusPage />} />
          <Route path="kien-truc" element={<ArchitecturePage />} />
          <Route path="hoi-thoai" element={<ChatPage />} />
          <Route path="hoi-thoai/:id" element={<ChatPage />} />
          <Route path="mang-luoi" element={<IntelPage />} />
          <Route path="noi-nhan-tien" element={<DestinationsPage />} />
          <Route path="ho-so/:id" element={<DossierPage />} />
          <Route path="kiem-duyet" element={<AdminPage />} />
          <Route path="demo" element={<DemoPage />} />
        </Route>
        <Route path="kiem-tra" element={<Navigate to="/" replace />} />
        <Route path="thu-vien" element={<Navigate to="/canh-bao?tab=kich-ban" replace />} />
        <Route path="kich-ban/:id" element={<LegacyScriptRedirect />} />
        <Route path="hoi-thoai" element={<Navigate to="/phan-tich/hoi-thoai" replace />} />
        <Route path="hoi-thoai/:id" element={<LegacyChatRedirect />} />
        <Route path="mang-luoi" element={<Navigate to="/phan-tich/mang-luoi" replace />} />
        <Route path="kiem-duyet" element={<Navigate to="/phan-tich/kiem-duyet" replace />} />
        <Route path="demo" element={<Navigate to="/phan-tich/demo" replace />} />
        <Route path="*" element={<p className="text-ink-soft">Không có trang này.</p>} />
      </Route>
    </Routes>
  )
}
