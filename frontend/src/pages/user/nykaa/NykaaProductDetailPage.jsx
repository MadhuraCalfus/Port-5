import { useEffect, useState } from "react";
import { ArrowLeft, Loader2, Minus, Plus, ShoppingBag } from "lucide-react";
import { api } from "../../../api";
import { Button, Card } from "../../../components/primitives";
import { formatDetailLabel, formatInr, ProductCard, ProductImage, ProductReviewsSection, useProductQA } from "./NykaaProductCard";

// A full product detail page — like any e-commerce PDP: bigger image,
// full details, reviews + ask-a-question, and related products below.
// Rendered in place of the catalog grid (mount this with `key={product.id}`
// from the caller so switching between products, including via a related
// product card below, resets all this page's state instead of reusing a
// stale instance).
export function NykaaProductDetailPage({ product, onBack, onAddToCart, onOpenProduct }) {
  const [quantity, setQuantity] = useState(1);
  const qa = useProductQA(product.id, { enabled: true });

  const [related, setRelated] = useState(null);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [relatedError, setRelatedError] = useState(null);
  const [relatedQuantities, setRelatedQuantities] = useState({});

  useEffect(() => {
    setLoadingRelated(true);
    setRelatedError(null);
    api
      .nykaaProductAlternatives(product.id)
      .then((r) => setRelated(r.products))
      .catch((e) => setRelatedError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingRelated(false));
  }, [product.id]);

  const detailEntries = Object.entries(product.details || {});

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-ink/60 dark:text-ink-dark/60 hover:text-ink dark:hover:text-ink-dark"
      >
        <ArrowLeft size={14} /> Back to results
      </button>

      <Card className="p-5 sm:p-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <ProductImage categoryName={product.category_name} size="h-64 sm:h-80" />

          <div className="flex flex-col">
            <span className="w-fit rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand dark:text-brand-dim">
              {product.category_name}
            </span>
            <h1 className="font-display mt-2 text-xl font-semibold text-ink dark:text-ink-dark sm:text-2xl">{product.name}</h1>
            <p className="mt-1 text-sm text-ink/50 dark:text-ink-dark/50">{product.brand_name}</p>
            <p className="font-display mt-3 text-2xl font-semibold text-brand dark:text-brand-dim">{formatInr(product.price_inr)}</p>

            {product.description && (
              <p className="mt-4 text-sm leading-relaxed text-ink/70 dark:text-ink-dark/70">{product.description}</p>
            )}

            {detailEntries.length > 0 && (
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-black/5 dark:border-white/10 pt-4 sm:grid-cols-3">
                {detailEntries.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-[10px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
                      {formatDetailLabel(key)}
                    </dt>
                    <dd className="text-xs font-medium text-ink dark:text-ink-dark">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}

            <div className="mt-auto flex items-center gap-3 border-t border-black/5 dark:border-white/10 pt-5">
              <div className="flex items-center gap-1 rounded-lg border border-black/10 dark:border-white/15">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  className="grid h-9 w-9 place-items-center text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
                  aria-label="Decrease quantity"
                >
                  <Minus size={14} />
                </button>
                <span className="w-7 text-center text-sm font-medium tabular-nums">{quantity}</span>
                <button
                  type="button"
                  onClick={() => setQuantity((q) => q + 1)}
                  className="grid h-9 w-9 place-items-center text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
                  aria-label="Increase quantity"
                >
                  <Plus size={14} />
                </button>
              </div>
              <Button onClick={() => onAddToCart?.(product, quantity)} className="flex-1">
                <ShoppingBag size={15} /> Add to bag
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card className="mt-4 p-5 sm:p-6">
        <h2 className="font-display text-base font-semibold text-ink dark:text-ink-dark">What customers say</h2>
        <div className="mt-3 space-y-2.5">
          <ProductReviewsSection qa={qa} onAddProduct={onAddToCart} onOpenDetail={onOpenProduct} />
        </div>
      </Card>

      <div className="mt-6">
        <h2 className="font-display text-base font-semibold text-ink dark:text-ink-dark">You may also like</h2>
        <div className="mt-3">
          {relatedError && <p className="text-xs text-red-600 dark:text-red-400">{relatedError}</p>}
          {!relatedError && loadingRelated && (
            <p className="flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
              <Loader2 size={12} className="animate-spin" /> Finding related products...
            </p>
          )}
          {!relatedError && !loadingRelated && related?.length === 0 && (
            <p className="text-xs text-ink/50 dark:text-ink-dark/50">No related products yet.</p>
          )}
          {related && related.length > 0 && (
            <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {related.map((p) => (
                <ProductCard
                  key={p.id}
                  product={p}
                  quantity={relatedQuantities[p.id] ?? 1}
                  onQuantityChange={(q) => setRelatedQuantities((prev) => ({ ...prev, [p.id]: q }))}
                  onAdd={(q) => onAddToCart?.(p, q)}
                  onAddProduct={onAddToCart}
                  onOpenDetail={onOpenProduct}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
