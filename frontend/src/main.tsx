import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import Alerts from "./pages/Alerts";
import Analysis from "./pages/Analysis";
import Dashboard from "./pages/Dashboard";
import Dividends from "./pages/Dividends";
import Import from "./pages/Import";
import Login from "./pages/Login";
import Notifications from "./pages/Notifications";
import Rebalance from "./pages/Rebalance";
import Screener from "./pages/Screener";
import Settings from "./pages/Settings";
import Tax from "./pages/Tax";
import Transactions from "./pages/Transactions";
import "./styles.css";

function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="empty">Carregando…</div>;
  if (!user) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="lancamentos" element={<Transactions />} />
        <Route path="proventos" element={<Dividends />} />
        <Route path="screener" element={<Screener />} />
        <Route path="analise" element={<Analysis />} />
        <Route path="analise/:ticker" element={<Analysis />} />
        <Route path="rebalanceamento" element={<Rebalance />} />
        <Route path="ir" element={<Tax />} />
        <Route path="alertas" element={<Alerts />} />
        <Route path="importar" element={<Import />} />
        <Route path="notificacoes" element={<Notifications />} />
        <Route path="configuracoes" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
