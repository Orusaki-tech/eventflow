"use client";

import { IconPlus, IconX } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listMyProducts, createProduct, type ProductRow } from "@/lib/eventflow-api";

export default function ProductsPage() {
  const { token } = usePortalAuth();
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [description, setDescription] = useState("");
  const [imageUri, setImageUri] = useState("");

  const reload = async () => {
    try { setProducts(await listMyProducts(token)); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const p = await listMyProducts(token);
        if (!cancelled) setProducts(p);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const add = async () => {
    setErr(null); setStatus(null);
    try {
      if (!title.trim() || !price.trim()) throw new Error("Title and price required");
      await createProduct(token, {
        title: title.trim(),
        price_minor_units: parseInt(price) || 0,
        description: description.trim() || undefined,
        image_uri: imageUri.trim() || undefined,
      });
      setTitle(""); setPrice(""); setDescription(""); setImageUri("");
      setStatus("Product created.");
      await reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (loading) return <p style={{ color: "#888", padding: 24 }}>Loading…</p>;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">New product</div>
          <span className="portal-tag portal-tag-post">POST</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Title</div>
            <input className="portal-inp" type="text" placeholder="Product name" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Price (minor units, e.g. 150000 = KES 1,500)</div>
            <input className="portal-inp" type="number" placeholder="150000" value={price} onChange={(e) => setPrice(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Description</div>
            <input className="portal-inp" type="text" placeholder="Optional description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Image URI</div>
            <input className="portal-inp" type="url" placeholder="https://cdn.example.com/pic.jpg" value={imageUri} onChange={(e) => setImageUri(e.target.value)} />
          </div>
          <div className="portal-acts" style={{ marginTop: 12 }}>
            <button type="button" className="portal-act" onClick={() => void add()}>
              <IconPlus size={12} /> Create product
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">My products</div>
          <span className="portal-tag portal-tag-info">{products.length} products</span>
        </div>
        <div className="portal-card-bd">
          {products.length === 0 ? (
            <p style={{ fontSize: 12, color: "#888", margin: 0 }}>No products yet. Create your first product above.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {products.map((p) => (
                <div key={p.product_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", background: "#f5f5f5", borderRadius: 8 }}>
                  {p.image_uri ? (
                    <img src={p.image_uri} alt="" style={{ width: 44, height: 44, borderRadius: 6, objectFit: "cover", background: "#ddd" }} />
                  ) : (
                    <div style={{ width: 44, height: 44, borderRadius: 6, background: "#ddd", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#888" }}>No img</div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>{p.title}</div>
                    <div style={{ fontSize: 11, color: "#888" }}>KES {(p.price_minor_units / 100).toFixed(2)}{p.description ? ` • ${p.description}` : ""}</div>
                  </div>
                  <span className={`portal-tag ${p.is_active ? "portal-tag-success" : "portal-tag-err"}`}>{p.is_active ? "Active" : "Inactive"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}
    </>
  );
}
