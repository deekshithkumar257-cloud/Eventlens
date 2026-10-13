import { Link, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import AlertsPage from './pages/AlertsPage';
import AlertDetailPage from './pages/AlertDetailPage';
import EventsPage from './pages/EventsPage';
import UploadPage from './pages/UploadPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route
          path="*"
          element={
            <div className="panel px-6 py-10 text-center">
              <div className="text-base font-semibold text-slate-100">Page not found</div>
              <Link to="/" className="btn-secondary mt-4">Back to overview</Link>
            </div>
          }
        />
      </Routes>
    </Layout>
  );
}
