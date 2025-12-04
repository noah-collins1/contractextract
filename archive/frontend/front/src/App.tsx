import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import RulePacks from "./pages/RulePacks";
import Documents from "./pages/Documents";
import "./theme.css";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/rule-packs" element={<RulePacks />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
