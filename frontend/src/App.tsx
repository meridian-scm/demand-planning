import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProductsPage } from "@/pages/ProductsPage";
import { ProductDetailPage } from "@/pages/ProductDetailPage";
import { ExceptionsPage } from "@/pages/ExceptionsPage";
import { ForecastRunPage } from "@/pages/ForecastRunPage";
import { DataUploadPage } from "@/pages/DataUploadPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />
        <Route path="exceptions" element={<ExceptionsPage />} />
        <Route path="forecast" element={<ForecastRunPage />} />
        <Route path="data" element={<DataUploadPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
