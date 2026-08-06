import { useEffect, useState } from "react";
import clsx from "clsx";
import { CheckCircle2, Loader2, Receipt, Search, ShoppingBag, Trash2, Wand2 } from "lucide-react";
import { api } from "../../../api";
import { Button, Card, SlideOver } from "../../../components/primitives";
import { formatInr, ProductCard } from "./NykaaProductCard";
import { NykaaProductDetailPage } from "./NykaaProductDetailPage";
import { NykaaOrdersPage } from "./NykaaOrdersPage";
import { NykaaBeautyProfilePage } from "./NykaaBeautyProfilePage";
import { NykaaAppFeedbackWidget } from "./NykaaAppFeedbackWidget";
import { NykaaHeroSlider } from "./NykaaHeroSlider";

export { formatInr };

function SidebarSection({ title, options, selected, onSelect, getLabel = (o) => o.name, getKey = (o) => o.id }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{title}</p>
      <div className="mt-1.5 space-y-0.5">
        <button
          onClick={() => onSelect("")}
          className={clsx(
            "block w-full rounded-lg px-2 py-1.5 text-left text-xs",
            selected === "" ? "bg-brand/10 font-medium text-brand dark:text-brand-dim" : "text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10",
          )}
        >
          All
        </button>
        {options.map((o) => (
          <button
            key={getKey(o)}
            onClick={() => onSelect(String(getKey(o)))}
            className={clsx(
              "block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs",
              selected === String(getKey(o))
                ? "bg-brand/10 font-medium text-brand dark:text-brand-dim"
                : "text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10",
            )}
          >
            {getLabel(o)}
          </button>
        ))}
      </div>
    </div>
  );
}

// The Nykaa Pulse "shop" — one e-commerce-style dashboard rather than
// separate Orders/Place Order/Beauty Profile tabs. This page IS the
// storefront (search + category pills + sidebar filters + product grid);
// Cart, My Orders, and Beauty Portfolio all live as icon buttons in the top
// bar and open their content in a slide-over drawer on top of the shop,
// the way a real e-commerce site's header works.
export function NykaaCatalogPage() {
  const [categories, setCategories] = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [subcategoryFilter, setSubcategoryFilter] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [search, setSearch] = useState("");
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [quantities, setQuantities] = useState({});
  const [cart, setCart] = useState([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [ordersOpen, setOrdersOpen] = useState(false);
  const [beautyOpen, setBeautyOpen] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [placedOrder, setPlacedOrder] = useState(null);
  const [error, setError] = useState(null);
  const [openProduct, setOpenProduct] = useState(null);

  // Only one drawer open at a time — they're all right-anchored at the same
  // z-index, so stacking two would just overlap.
  function openCart() {
    setOrdersOpen(false);
    setBeautyOpen(false);
    setCartOpen(true);
  }
  function openOrders() {
    setCartOpen(false);
    setBeautyOpen(false);
    setOrdersOpen(true);
  }
  function openBeauty() {
    setCartOpen(false);
    setOrdersOpen(false);
    setBeautyOpen(true);
  }

  useEffect(() => {
    api.nykaaListCategories().then((r) => setCategories(r.categories)).catch(() => {});
  }, []);

  // Category pills drive both the subcategory and brand sidebar lists —
  // cascading, so picking "Skincare" only ever shows Skincare's own
  // subcategories and the brands that actually sell something in it.
  useEffect(() => {
    api.nykaaListSubcategories(categoryFilter || undefined).then((r) => {
      setSubcategories(r.subcategories);
      if (subcategoryFilter && !r.subcategories.some((s) => String(s.id) === subcategoryFilter)) setSubcategoryFilter("");
    }).catch(() => {});
    api.nykaaListBrands(categoryFilter || undefined).then((r) => {
      setBrands(r.brands);
      if (brandFilter && !r.brands.some((b) => String(b.id) === brandFilter)) setBrandFilter("");
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryFilter]);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      api
        .nykaaListProducts({
          categoryId: categoryFilter || undefined,
          brandId: brandFilter || undefined,
          subcategoryId: subcategoryFilter || undefined,
          search: search.trim() || undefined,
        })
        .then((r) => setProducts(r.products))
        .catch(() => setProducts([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [categoryFilter, brandFilter, subcategoryFilter, search]);

  function addToCart(product, quantity) {
    setCart((prev) => {
      const existing = prev.find((c) => c.product_id === product.id);
      if (existing) {
        return prev.map((c) =>
          c.product_id === product.id ? { ...c, quantity: c.quantity + quantity } : c,
        );
      }
      return [...prev, { product_id: product.id, name: product.name, price_inr: product.price_inr, quantity }];
    });
    openCart();
  }

  function removeFromCart(productId) {
    setCart((prev) => prev.filter((c) => c.product_id !== productId));
  }

  const cartCount = cart.reduce((sum, c) => sum + c.quantity, 0);
  const cartTotal = cart.reduce((sum, c) => sum + c.price_inr * c.quantity, 0);

  async function placeOrder() {
    if (cart.length === 0) return;
    setPlacing(true);
    setError(null);
    try {
      const order = await api.nykaaPlaceOrder(cart.map((c) => ({ product_id: c.product_id, quantity: c.quantity })));
      setPlacedOrder(order);
      setCart([]);
      setCartOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPlacing(false);
    }
  }

  return (
    <div>
      <div className="mb-4">
        <NykaaHeroSlider />
      </div>

      {placedOrder && (
        <Card className="mx-auto mb-4 max-w-lg p-6 text-center">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 size={24} />
          </span>
          <h2 className="mt-4 font-display text-lg font-semibold text-ink dark:text-ink-dark">Order placed!</h2>
          <p className="mt-1.5 text-sm text-ink/60 dark:text-ink-dark/60">
            Order #{placedOrder.id} · {placedOrder.items.length} item{placedOrder.items.length === 1 ? "" : "s"} ·{" "}
            {formatInr(placedOrder.total_amount)}
          </p>
          <p className="mt-1 text-xs text-ink/50 dark:text-ink-dark/50">
            Track it, rate your delivery, and review your products from My Orders.
          </p>
          <div className="mt-5 flex items-center justify-center gap-3">
            <Button variant="ghost" onClick={() => setPlacedOrder(null)}>
              Keep shopping
            </Button>
            <Button
              onClick={() => {
                setPlacedOrder(null);
                openOrders();
              }}
            >
              <Receipt size={14} /> View My Orders
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-lg border border-black/10 dark:border-white/15 px-3 py-2 text-sm text-ink/50 dark:text-ink-dark/50">
            <Search size={15} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search products..."
              className="w-full bg-transparent text-sm text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none"
            />
          </label>

          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={openBeauty}
              className="inline-flex items-center gap-1.5 rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-xs font-medium text-ink/70 dark:text-ink-dark/70 hover:bg-black/10 dark:hover:bg-white/15"
            >
              <Wand2 size={15} /> Beauty Portfolio
            </button>
            <button
              onClick={openOrders}
              className="inline-flex items-center gap-1.5 rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-xs font-medium text-ink/70 dark:text-ink-dark/70 hover:bg-black/10 dark:hover:bg-white/15"
            >
              <Receipt size={15} /> My Orders
            </button>
            <button
              onClick={openCart}
              className="relative inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-xs font-semibold text-white hover:opacity-90"
            >
              <ShoppingBag size={15} /> Cart
              {cartCount > 0 && (
                <span className="grid h-4 min-w-[16px] place-items-center rounded-full bg-white/25 px-1 text-[10px] font-semibold leading-none">
                  {cartCount}
                </span>
              )}
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-black/5 dark:border-white/10 pt-3">
          <button
            onClick={() => setCategoryFilter("")}
            className={clsx(
              "shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition",
              categoryFilter === "" ? "bg-brand text-white" : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
            )}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => setCategoryFilter(String(c.id))}
              className={clsx(
                "shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition",
                categoryFilter === String(c.id) ? "bg-brand text-white" : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
              )}
            >
              {c.name}
            </button>
          ))}
          {loading && <Loader2 size={14} className="ml-1 shrink-0 animate-spin text-ink/40 dark:text-ink-dark/40" />}
        </div>
      </Card>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[15rem_1fr]">
        <Card className="hidden h-fit max-h-[calc(100vh-8rem)] space-y-4 overflow-y-auto overscroll-contain thin-scroll p-4 lg:block">
          <SidebarSection
            title="Subcategory"
            options={subcategories}
            selected={subcategoryFilter}
            onSelect={setSubcategoryFilter}
          />
          <SidebarSection title="Brand" options={brands} selected={brandFilter} onSelect={setBrandFilter} />
        </Card>

        {openProduct ? (
          <NykaaProductDetailPage
            key={openProduct.id}
            product={openProduct}
            onBack={() => setOpenProduct(null)}
            onAddToCart={addToCart}
            onOpenProduct={setOpenProduct}
          />
        ) : (
          <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                quantity={quantities[product.id] ?? 1}
                onQuantityChange={(q) => setQuantities((prev) => ({ ...prev, [product.id]: q }))}
                onAdd={(q) => addToCart(product, q)}
                onAddProduct={addToCart}
                onOpenDetail={setOpenProduct}
              />
            ))}
            {!loading && products.length === 0 && (
              <p className="col-span-full py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                No products match your filters.
              </p>
            )}
          </div>
        )}
      </div>

      {cartOpen && (
        <SlideOver title="Your Bag" onClose={() => setCartOpen(false)} widthClassName="max-w-sm">
          {cart.length === 0 ? (
            <p className="text-sm text-ink/50 dark:text-ink-dark/50">Add products to build an order.</p>
          ) : (
            <>
              <div className="space-y-2.5">
                {cart.map((c) => (
                  <div key={c.product_id} className="flex items-start justify-between gap-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink dark:text-ink-dark">{c.name}</p>
                      <p className="text-xs text-ink/50 dark:text-ink-dark/50">
                        {c.quantity} × {formatInr(c.price_inr)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFromCart(c.product_id)}
                      className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-ink/40 dark:text-ink-dark/40 hover:bg-black/5 dark:hover:bg-white/10"
                      aria-label={`Remove ${c.name}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-black/5 dark:border-white/10 pt-3 text-sm font-semibold text-ink dark:text-ink-dark">
                <span>Total</span>
                <span>{formatInr(cartTotal)}</span>
              </div>
              {error && <p className="mt-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
              <Button className="mt-3 w-full" onClick={placeOrder} disabled={placing}>
                {placing ? <Loader2 size={15} className="animate-spin" /> : <ShoppingBag size={15} />}
                {placing ? "Placing order..." : "Place order"}
              </Button>
            </>
          )}
        </SlideOver>
      )}

      {ordersOpen && (
        <SlideOver title="My Orders" onClose={() => setOrdersOpen(false)} widthClassName="max-w-4xl">
          <NykaaOrdersPage onNavigateToBeautyProfile={openBeauty} />
        </SlideOver>
      )}

      {beautyOpen && (
        <SlideOver title="Beauty Portfolio" onClose={() => setBeautyOpen(false)} widthClassName="max-w-4xl">
          <NykaaBeautyProfilePage onAddToCart={addToCart} />
        </SlideOver>
      )}

      <NykaaAppFeedbackWidget />
    </div>
  );
}
