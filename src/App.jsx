import { Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import LiveMonitor from './pages/LiveMonitor'
import PlaceholderPage from './pages/PlaceholderPage'
import UserManagementPage from './pages/UserManagementPage'

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
        <Route
          path="zone-config"
          element={
            <PlaceholderPage
              title="Zone Config"
              description="ROI drawing tools and safety zone configuration will be managed in this section."
            />
          }
        />
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
