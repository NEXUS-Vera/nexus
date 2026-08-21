import { Navigate, Route, Routes } from 'react-router-dom';
import { ServiceRestartNotice } from './components/feedback/ServiceRestartNotice';
import { HomePage } from './pages/HomePage';
import { ProjectPage } from './pages/ProjectPage';

export default function App() {
  return (
    // A column the height of the viewport, so a notice above the routes takes
    // its space from the view rather than adding to the document. The project
    // workspace fills the rest of the screen and hides its own overflow, so a
    // notice that pushed instead of shared would put the composer the student
    // is being told to retype into below the fold, unreachable.
    <div className="app-root">
      {/* Above the routes, so a recovery is reported wherever the student was. */}
      <ServiceRestartNotice />
      <div className="app-routes">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}
