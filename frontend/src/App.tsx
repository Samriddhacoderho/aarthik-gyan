import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AnalysisPage } from "./pages/AnalysisPage";
import { CompanyPage } from "./pages/CompanyPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { GraphPage } from "./pages/GraphPage";
import { NewAnalysisPage } from "./pages/NewAnalysisPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="analyses/new" element={<NewAnalysisPage />} />
          <Route path="analyses/:analysisId" element={<AnalysisPage />} />
          <Route path="companies/:companyId" element={<CompanyPage />} />
          <Route path="graph" element={<GraphPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
