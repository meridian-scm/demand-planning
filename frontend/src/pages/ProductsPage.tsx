import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateProduct, useProducts } from "@/hooks/useQueries";
import { LoadingState, EmptyState, ErrorBanner } from "@/components/ui/LoadingState";
import { apiErrorMessage } from "@/api/client";
import { formatCurrency } from "@/lib/format";
import type { ProductCreateInput } from "@/types/api";

const EMPTY_FORM: ProductCreateInput = {
  sku: "",
  name: "",
  category: "",
  lead_time_days: 30,
  safety_stock_units: 0,
};

export function ProductsPage() {
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProductCreateInput>(EMPTY_FORM);

  const products = useProducts({ search: search || undefined, limit: 100 });
  const createProduct = useCreateProduct();
  const navigate = useNavigate();

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    createProduct.mutate(form, {
      onSuccess: () => {
        setForm(EMPTY_FORM);
        setShowForm(false);
      },
    });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Products</h1>
          <p className="page-subtitle">Master data for every SKU planned by the system.</p>
        </div>
        <div className="page-actions">
          <input
            className="input"
            placeholder="Search by SKU or name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 220 }}
          />
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "+ New Product"}
          </button>
        </div>
      </div>

      {showForm && (
        <form className="card" onSubmit={handleSubmit} style={{ marginBottom: 20 }}>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <div className="field">
              <label htmlFor="sku">SKU</label>
              <input
                id="sku"
                className="input"
                required
                value={form.sku}
                onChange={(e) => setForm({ ...form, sku: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="name">Name</label>
              <input
                id="name"
                className="input"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="category">Category</label>
              <input
                id="category"
                className="input"
                required
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="lead_time">Lead time (days)</label>
              <input
                id="lead_time"
                type="number"
                className="input"
                min={0}
                value={form.lead_time_days}
                onChange={(e) => setForm({ ...form, lead_time_days: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label htmlFor="safety_stock">Safety stock (units)</label>
              <input
                id="safety_stock"
                type="number"
                className="input"
                min={0}
                value={form.safety_stock_units}
                onChange={(e) => setForm({ ...form, safety_stock_units: Number(e.target.value) })}
              />
            </div>
          </div>
          {createProduct.isError && (
            <div style={{ marginTop: 12 }}>
              <ErrorBanner message={apiErrorMessage(createProduct.error)} />
            </div>
          )}
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" type="submit" disabled={createProduct.isPending}>
              {createProduct.isPending ? "Creating…" : "Create Product"}
            </button>
          </div>
        </form>
      )}

      <div className="card">
        {products.isLoading ? (
          <LoadingState />
        ) : products.isError ? (
          <ErrorBanner message={apiErrorMessage(products.error)} />
        ) : products.data && products.data.items.length > 0 ? (
          <div className="scrollable">
            <table className="table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Lead Time</th>
                  <th>Safety Stock</th>
                  <th>Unit Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {products.data.items.map((product) => (
                  <tr
                    key={product.id}
                    className="clickable"
                    onClick={() => navigate(`/products/${product.id}`)}
                  >
                    <td>
                      <Link to={`/products/${product.id}`} style={{ fontWeight: 600, textDecoration: "none" }}>
                        {product.sku}
                      </Link>
                    </td>
                    <td>{product.name}</td>
                    <td>{product.category}</td>
                    <td>{product.lead_time_days}d</td>
                    <td>{product.safety_stock_units}</td>
                    <td>{formatCurrency(product.unit_price)}</td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: product.active ? "var(--color-success-soft)" : "var(--color-border-soft)",
                          color: product.active ? "var(--color-success)" : "var(--color-text-faint)",
                        }}
                      >
                        {product.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No products found" description="Create a product or adjust your search." />
        )}
      </div>
    </div>
  );
}
