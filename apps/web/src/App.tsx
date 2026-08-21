import { Navigate, Route, Routes } from 'react-router-dom';
import { ServiceRestartNotice } from './components/feedback/ServiceRestartNotice';
import { HomePage } from './pages/HomePage';
import { ProjectPage } from './pages/ProjectPage';

export default function App() {
  return (
    <>
      {/* Above the routes, so a recovery is reported wherever the student was. */}
      <ServiceRestartNotice />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
