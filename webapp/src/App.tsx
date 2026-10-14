import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/ui'
import { ThemeProvider } from './theme'
import Dashboard from './pages/Dashboard'
import Patients from './pages/Patients'
import PatientDetail from './pages/PatientDetail'
import Sessions from './pages/Sessions'
import Games from './pages/Games'
import Datasets from './pages/Datasets'
import Settings from './pages/Settings'

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <HashRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="patients" element={<Patients />} />
              <Route path="patients/:pid" element={<PatientDetail />} />
              <Route path="sessions" element={<Sessions />} />
              <Route path="games" element={<Games />} />
              <Route path="datasets" element={<Datasets />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </HashRouter>
      </ToastProvider>
    </ThemeProvider>
  )
}
