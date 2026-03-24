import { Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import LiveMonitor from './features/admin/components/LiveMonitor.jsx'
import PlaceholderPage from './features/admin/components/PlaceholderPage.jsx'
import UserManagementPage from './features/admin/components/UserManagementPage.jsx'
import ZoneConfig from './features/admin/components/ZoneConfig.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Navigate to="user-management" replace />} />
        <Route path="live-monitor" element={<LiveMonitor />} />
        <Route
          path="events-history"
          element={
            <PlaceholderPage
              title="Events History"
              description="Historical alerts, incident timelines, and event filtering will appear here."
            />
          }
        />
        <Route path="zone-config" element={<ZoneConfig />} />
        <Route
          path="ai-settings"
          element={
            <PlaceholderPage
              title="AI Settings"
              description="Detection sensitivity and model behavior settings will be configured here."
            />
          }
        />
        <Route path="user-management" element={<UserManagementPage />} />
        <Route path="*" element={<Navigate to="user-management" replace />} />
      </Route>
    </Routes>
  )
}
