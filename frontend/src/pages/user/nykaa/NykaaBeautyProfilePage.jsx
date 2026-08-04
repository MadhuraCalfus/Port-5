import { useEffect, useState } from "react";
import { Check, ChevronDown, Loader2, Sparkles, Wand2 } from "lucide-react";
import clsx from "clsx";
import { api } from "../../../api";
import { Button, Card } from "../../../components/primitives";
import { ProductCard } from "./NykaaProductCard";

const SECTIONS = ["Skin", "Hair", "Makeup"];

// `value` is what's persisted (kept backward-compatible with the original
// 3-field profile, e.g. "Normal" stays "Normal" in the DB/seed data even
// though real Nykaa's quiz calls it "Balanced") — `label`/`hint` are display
// only.
const SKIN_TYPES = [
  { value: "Dry", label: "Dry" },
  { value: "Normal", label: "Balanced", hint: "I'm Blessed!" },
  { value: "Combination", label: "Combination" },
  { value: "Oily", label: "Oily" },
  { value: "Sensitive", label: "Sensitive" },
];
const SKIN_CONCERNS = [
  "Acne", "Tanning", "Dryness", "Fine Lines & Wrinkles", "Oiliness",
  "Dull Skin", "Dark Spots & Pigmentation", "Pores", "Dark Circles", "Blackheads & Whiteheads",
];
const HAIR_TYPES = ["Straight", "Wavy", "Curly", "Coily"];
const SCALP_TYPES = ["Oily", "Dry", "Balanced", "Sensitive"];
const HAIR_CONCERNS = [
  "Dandruff-Prone", "Damaged", "Frizzy", "Thinning", "Oily Scalp",
  "Dry Scalp", "Color-Treated", "Hair Fall", "Split Ends", "Premature Greying",
];
const SKIN_TONES = ["Fair", "Light", "Medium", "Tan", "Deep"];
const UNDERTONES = ["Warm", "Cool", "Neutral"];

const toOptions = (values) => values.map((v) => ({ value: v, label: v }));

const SECTION_QUESTIONS = {
  Skin: [
    { key: "skin_type", type: "single", label: "Skin Type", prompt: "Let's kick off with your skin type", sub: "Pick the one that suits you best", options: SKIN_TYPES },
    { key: "skin_concerns", type: "multi", label: "Skin Concern", prompt: "Tell us about your skin concerns", sub: "Select up to 5 that apply", options: toOptions(SKIN_CONCERNS), max: 5 },
    { key: "date_of_birth", type: "date", label: "Date of Birth", prompt: "When were you born?", sub: "Helps us fine-tune advice for your age" },
  ],
  Hair: [
    { key: "hair_type", type: "single", label: "Hair Type", prompt: "What's your hair type?", sub: "Pick the one that suits you best", options: toOptions(HAIR_TYPES) },
    { key: "scalp_type", type: "single", label: "Scalp Type", prompt: "How would you describe your scalp?", sub: "Pick the one that suits you best", options: toOptions(SCALP_TYPES) },
    { key: "hair_concerns", type: "multi", label: "Hair Concern", prompt: "Tell us about your hair concerns", sub: "Select up to 5 that apply", options: toOptions(HAIR_CONCERNS), max: 5 },
  ],
  Makeup: [
    { key: "skin_tone", type: "single", label: "Skin Tone", prompt: "What's your skin tone?", sub: "Pick the one that suits you best", options: toOptions(SKIN_TONES) },
    { key: "undertone", type: "single", label: "Undertone", prompt: "What's your undertone?", sub: "Pick the one that suits you best", options: toOptions(UNDERTONES) },
    { key: "makeup_preferences", type: "text", label: "Makeup Preferences", prompt: "Any makeup preferences?", sub: "Optional — e.g. natural everyday looks, bold color pops, cruelty-free only..." },
  ],
};

const EMPTY_ANSWERS = {
  skin_type: "", skin_concerns: [], date_of_birth: "",
  hair_type: "", scalp_type: "", hair_concerns: [],
  skin_tone: "", undertone: "", makeup_preferences: "",
};

function isAnswered(q, answers) {
  const v = answers[q.key];
  if (q.type === "multi") return Array.isArray(v) && v.length > 0;
  return Boolean(v);
}

function displayValue(q, answers) {
  const v = answers[q.key];
  if (q.type === "multi") {
    return (v || []).map((val) => q.options.find((o) => o.value === val)?.label ?? val).join(", ");
  }
  if (q.type === "single") return q.options.find((o) => o.value === v)?.label ?? "";
  if (q.type === "date" && v) return v.split("-").reverse().join("/");
  return v || "";
}

function firstUnansweredIndex(section, answers) {
  const questions = SECTION_QUESTIONS[section];
  const idx = questions.findIndex((q) => !isAnswered(q, answers));
  return idx === -1 ? null : idx;
}

function QuestionInput({ question, value, onChange }) {
  if (question.type === "single") {
    return (
      <div className="grid grid-cols-2 gap-3">
        {question.options.map((opt) => {
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={clsx(
                "rounded-xl border px-4 py-3 text-left text-sm font-medium transition",
                selected
                  ? "border-brand bg-brand/5 text-brand dark:text-brand-dim"
                  : "border-black/10 dark:border-white/15 text-ink dark:text-ink-dark hover:border-black/25 dark:hover:border-white/30",
              )}
            >
              {opt.label}
              {opt.hint && <span className="mt-0.5 block text-[10px] font-normal text-ink/40 dark:text-ink-dark/40">{opt.hint}</span>}
            </button>
          );
        })}
      </div>
    );
  }

  if (question.type === "multi") {
    const selected = value || [];
    const atMax = question.max && selected.length >= question.max;
    return (
      <div className="grid grid-cols-2 gap-3">
        {question.options.map((opt) => {
          const isSelected = selected.includes(opt.value);
          const disabled = atMax && !isSelected;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(isSelected ? selected.filter((v) => v !== opt.value) : [...selected, opt.value])
              }
              className={clsx(
                "rounded-xl border px-4 py-3 text-left text-sm font-medium transition",
                isSelected
                  ? "border-brand bg-brand/5 text-brand dark:text-brand-dim"
                  : "border-black/10 dark:border-white/15 text-ink dark:text-ink-dark hover:border-black/25 dark:hover:border-white/30",
                disabled && "opacity-40",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    );
  }

  if (question.type === "date") {
    return (
      <input
        type="date"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
      />
    );
  }

  return (
    <input
      type="text"
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Type here..."
      className="w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40"
    />
  );
}

function BeautyWizard({ answers, setAnswers, confirmedSections, setConfirmedSections, persist, saving, saveError }) {
  const [activeSection, setActiveSection] = useState("Skin");
  // Pinned once at mount from whatever was already saved — deliberately NOT
  // recomputed as `answers` changes, otherwise picking an option would
  // instantly collapse+advance the question instead of waiting for "Next".
  const [expandedIndex, setExpandedIndex] = useState(() =>
    Object.fromEntries(SECTIONS.map((s) => [s, firstUnansweredIndex(s, answers)])),
  );
  const [savedFlash, setSavedFlash] = useState(false);

  function goToSection(section) {
    setActiveSection(section);
  }

  async function handleNext(section, index) {
    await persist(answers);
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1500);

    const questions = SECTION_QUESTIONS[section];
    if (index + 1 < questions.length) {
      setExpandedIndex((prev) => ({ ...prev, [section]: index + 1 }));
      return;
    }
    // Last question in the section — "Confirm" locks it in and collapses
    // everything back to summary rows; auto-advance to the next section
    // (Skin -> Hair -> Makeup) but don't loop back around after Makeup.
    setConfirmedSections((prev) => ({ ...prev, [section]: true }));
    setExpandedIndex((prev) => ({ ...prev, [section]: null }));
    const sectionIdx = SECTIONS.indexOf(section);
    if (sectionIdx < SECTIONS.length - 1) setActiveSection(SECTIONS[sectionIdx + 1]);
  }

  const questions = SECTION_QUESTIONS[activeSection];
  const expanded = expandedIndex[activeSection];

  return (
    <Card className="mx-auto max-w-xl p-6">
      <div className="flex items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-brand/10 text-brand dark:text-brand-dim">
          <Sparkles size={16} />
        </span>
        <div>
          <h2 className="font-display text-base font-semibold text-ink dark:text-ink-dark">My Beauty Profile</h2>
          <p className="text-xs text-ink/50 dark:text-ink-dark/50">
            Tell us a bit about yourself so other shoppers can see reviews from people like them.
          </p>
        </div>
      </div>

      <div className="mt-5 flex gap-2 border-b border-black/8 dark:border-white/10 pb-3">
        {SECTIONS.map((section) => (
          <button
            key={section}
            type="button"
            onClick={() => goToSection(section)}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition",
              activeSection === section
                ? "bg-brand text-white"
                : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
            )}
          >
            {confirmedSections[section] && <Check size={12} />}
            {section}
          </button>
        ))}
      </div>

      {saveError && (
        <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{saveError}</p>
      )}

      <div className="mt-2">
        {questions.map((q, i) => {
          if (i === expanded) {
            const isLast = i === questions.length - 1;
            const nextLabel = isLast ? "Confirm" : "Next";
            return (
              <div key={q.key} className="border-b border-black/8 dark:border-white/10 py-4 last:border-b-0">
                <p className="text-sm font-semibold text-ink dark:text-ink-dark">{q.prompt}</p>
                {q.sub && <p className="mt-0.5 text-xs text-ink/50 dark:text-ink-dark/50">{q.sub}</p>}
                <div className="mt-3">
                  <QuestionInput question={q} value={answers[q.key]} onChange={(v) => setAnswers((prev) => ({ ...prev, [q.key]: v }))} />
                </div>
                <div className="mt-4 flex items-center gap-3">
                  <Button onClick={() => handleNext(activeSection, i)} disabled={saving} className="px-5 py-2 text-xs">
                    {saving ? <Loader2 size={13} className="animate-spin" /> : null}
                    {nextLabel}
                  </Button>
                  {savedFlash && <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Saved</span>}
                </div>
              </div>
            );
          }
          return (
            <button
              key={q.key}
              type="button"
              onClick={() => setExpandedIndex((prev) => ({ ...prev, [activeSection]: i }))}
              className="flex w-full items-center justify-between gap-3 border-b border-black/8 dark:border-white/10 py-3 text-left last:border-b-0"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <span
                  className={clsx(
                    "grid h-5 w-5 shrink-0 place-items-center rounded-full",
                    isAnswered(q, answers) ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-black/5 dark:bg-white/10",
                  )}
                >
                  {isAnswered(q, answers) && <Check size={12} />}
                </span>
                <span className="truncate text-sm">
                  <span className="text-ink/50 dark:text-ink-dark/50">{q.label}:</span>{" "}
                  <span className="font-semibold text-ink dark:text-ink-dark">{displayValue(q, answers) || "Not set"}</span>
                </span>
              </span>
              <ChevronDown size={16} className="shrink-0 text-ink/40 dark:text-ink-dark/40" />
            </button>
          );
        })}
      </div>
    </Card>
  );
}

const REC_TABS = [
  { key: "skin", label: "Skin" },
  { key: "hair", label: "Hair" },
  { key: "makeup", label: "Makeup" },
];

function RecommendedProducts({ onAddToCart }) {
  const [activeTab, setActiveTab] = useState("skin");
  const [cache, setCache] = useState({});
  const [loadingTab, setLoadingTab] = useState(null);
  const [error, setError] = useState(null);
  const [quantities, setQuantities] = useState({});

  useEffect(() => {
    if (cache[activeTab]) return;
    setLoadingTab(activeTab);
    setError(null);
    api
      .nykaaRecommendedProducts(activeTab)
      .then((r) => setCache((prev) => ({ ...prev, [activeTab]: r.products })))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingTab(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const products = cache[activeTab];

  return (
    <div>
      <div className="flex gap-2">
        {REC_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            className={clsx(
              "rounded-full px-3.5 py-1.5 text-xs font-semibold transition",
              activeTab === t.key
                ? "bg-brand text-white"
                : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-3">
        {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
        {!error && loadingTab === activeTab && (
          <p className="flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
            <Loader2 size={12} className="animate-spin" /> Finding products for you...
          </p>
        )}
        {!error && loadingTab !== activeTab && products?.length === 0 && (
          <p className="text-xs text-ink/50 dark:text-ink-dark/50">No recommendations yet.</p>
        )}
        {!error && products && products.length > 0 && (
          <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                quantity={quantities[p.id] ?? 1}
                onQuantityChange={(q) => setQuantities((prev) => ({ ...prev, [p.id]: q }))}
                onAdd={(q) => onAddToCart?.(p, q)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// A routine step now renders the *actual* product (fetched by the step's
// product_id — the routine endpoint only returns id/name/reason, see
// nykaa_ai_features.generate_beauty_routine) as a full ProductCard, so a
// customer can inspect it (reviews, "what customers say") and add it to
// their cart directly from the routine, not just read its name.
function RoutineStepCard({ step, index, product, quantity, onQuantityChange, onAdd }) {
  return (
    <div>
      <div className="mb-2 flex items-start gap-2.5">
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand/10 text-[11px] font-semibold text-brand dark:text-brand-dim">
          {index + 1}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{step.step}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-ink/60 dark:text-ink-dark/60">{step.reason}</p>
        </div>
      </div>
      {product ? (
        <ProductCard product={product} quantity={quantity} onQuantityChange={onQuantityChange} onAdd={onAdd} />
      ) : (
        <Card className="flex items-center justify-center gap-2 p-6 text-xs text-ink/50 dark:text-ink-dark/50">
          <Loader2 size={13} className="animate-spin" /> Loading product...
        </Card>
      )}
    </div>
  );
}

const ROUTINE_TABS = [
  { key: "skincare_routine", label: "Skincare" },
  { key: "haircare_routine", label: "Haircare" },
];

function RoutineGenerator({ onAddToCart }) {
  const [routine, setRoutine] = useState(null);
  const [products, setProducts] = useState({});
  const [activeTab, setActiveTab] = useState("skincare_routine");
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.nykaaBeautyRoutine();
      setRoutine(r);
      const ids = [...new Set([...r.skincare_routine, ...r.haircare_routine].map((s) => s.product_id))];
      const fetched = await Promise.all(ids.map((id) => api.nykaaGetProduct(id).catch(() => null)));
      setProducts(Object.fromEntries(ids.map((id, i) => [id, fetched[i]]).filter(([, p]) => p)));
      if (r.skincare_routine.length === 0 && r.haircare_routine.length > 0) setActiveTab("haircare_routine");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = routine && routine.skincare_routine.length === 0 && routine.haircare_routine.length === 0;
  const activeSteps = routine ? routine[activeTab] : [];

  return (
    <Card className="mt-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-base font-semibold text-ink dark:text-ink-dark">Your personal routine</h2>
          <p className="mt-1 text-xs text-ink/60 dark:text-ink-dark/60">
            A full step-by-step routine matched to your skin/hair type and concerns, grounded in ratings where available.
          </p>
        </div>
        <Button onClick={generate} disabled={loading} className="px-4 py-2 text-xs">
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
          {loading ? "Building your routine..." : "✨ Generate My Routine"}
        </Button>
      </div>

      {error && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {isEmpty && (
        <p className="mt-4 text-center text-xs text-ink/50 dark:text-ink-dark/50">
          No Skincare/Hair Care products in the catalog yet to build a routine from.
        </p>
      )}

      {routine && !isEmpty && (
        <div className="mt-5">
          <div className="flex gap-2">
            {ROUTINE_TABS.filter((t) => routine[t.key].length > 0).map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveTab(t.key)}
                className={clsx(
                  "rounded-full px-3.5 py-1.5 text-xs font-semibold transition",
                  activeTab === t.key
                    ? "bg-brand text-white"
                    : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 items-start gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {activeSteps.map((s, i) => (
              <RoutineStepCard
                key={s.step}
                step={s}
                index={i}
                product={products[s.product_id]}
                quantity={quantities[s.product_id] ?? 1}
                onQuantityChange={(q) => setQuantities((prev) => ({ ...prev, [s.product_id]: q }))}
                onAdd={(q) => onAddToCart?.(products[s.product_id], q)}
              />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

// "My Beauty Portfolio" — a customer works through a short Skin/Hair/Makeup
// quiz once (accordion-style: one question expanded at a time, answered ones
// collapse into a checkmarked summary row), and it's shown alongside their
// reviews so other shoppers see "someone with my skin type liked this" (see
// WhatCustomersSay's fit_notes + review skin/hair badges in
// NykaaCatalogPage.jsx). Every field is independently optional — same
// "nothing forced" principle as the review form — so "Next" always advances
// even if the current question is left blank.
export function NykaaBeautyProfilePage({ onAddToCart }) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [answers, setAnswers] = useState(EMPTY_ANSWERS);
  // A section only counts once its own "Confirm" has been clicked — not
  // merely once every field in it happens to be filled — except on load,
  // where a returning customer's already-complete section is treated as
  // already confirmed (see isAnswered/SECTION_QUESTIONS below).
  const [confirmedSections, setConfirmedSections] = useState({ Skin: false, Hair: false, Makeup: false });
  const [updatedAt, setUpdatedAt] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    // StrictMode double-mounts this effect in dev — without the `cancelled`
    // guard, the throwaway first mount's fetch can resolve after the real
    // mount, clobbering whatever the customer has since answered in the
    // wizard with the empty pre-save snapshot it captured at request time.
    let cancelled = false;
    api
      .nykaaGetBeautyProfile()
      .then((profile) => {
        if (cancelled) return;
        const loaded = {
          skin_type: profile.skin_type ?? "",
          skin_concerns: profile.skin_concerns ?? [],
          date_of_birth: profile.date_of_birth ?? "",
          hair_type: profile.hair_type ?? "",
          scalp_type: profile.scalp_type ?? "",
          hair_concerns: profile.hair_concerns ?? [],
          skin_tone: profile.skin_tone ?? "",
          undertone: profile.undertone ?? "",
          makeup_preferences: profile.makeup_preferences ?? "",
        };
        setAnswers(loaded);
        setConfirmedSections(
          Object.fromEntries(SECTIONS.map((s) => [s, SECTION_QUESTIONS[s].every((q) => isAnswered(q, loaded))])),
        );
        setUpdatedAt(profile.updated_at ?? null);
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function persist(current) {
    setSaving(true);
    setSaveError(null);
    try {
      const profile = await api.nykaaUpdateBeautyProfile({
        skin_type: current.skin_type || null,
        skin_concerns: current.skin_concerns.length ? current.skin_concerns : null,
        date_of_birth: current.date_of_birth || null,
        hair_type: current.hair_type || null,
        scalp_type: current.scalp_type || null,
        hair_concerns: current.hair_concerns.length ? current.hair_concerns : null,
        skin_tone: current.skin_tone || null,
        undertone: current.undertone || null,
        makeup_preferences: current.makeup_preferences.trim() || null,
      });
      setUpdatedAt(profile.updated_at ?? null);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink/50 dark:text-ink-dark/50">
        <Loader2 size={16} className="animate-spin" /> Loading your beauty profile...
      </div>
    );
  }

  const allConfirmed = SECTIONS.every((s) => confirmedSections[s]);

  return (
    <div>
      {loadError && (
        <p className="mx-auto mb-3 max-w-xl rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{loadError}</p>
      )}

      <BeautyWizard
        answers={answers}
        setAnswers={setAnswers}
        confirmedSections={confirmedSections}
        setConfirmedSections={setConfirmedSections}
        persist={persist}
        saving={saving}
        saveError={saveError}
      />

      {!allConfirmed && (
        <p className="mx-auto mt-4 max-w-xl text-center text-xs text-ink/50 dark:text-ink-dark/50">
          Confirm all three sections above (Skin, Hair, Makeup) to see your summary and recommendations.
        </p>
      )}

      {allConfirmed && (
        <Card className="mx-auto mt-4 max-w-xl p-5">
          <h3 className="text-sm font-semibold text-ink dark:text-ink-dark">Your Beauty Profile, at a glance</h3>
          <dl className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {SECTIONS.flatMap((s) => SECTION_QUESTIONS[s]).map((q) => (
              <div key={q.key}>
                <dt className="text-[10px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{q.label}</dt>
                <dd className="text-sm font-medium text-ink dark:text-ink-dark">{displayValue(q, answers) || "Not set"}</dd>
              </div>
            ))}
          </dl>
          {updatedAt && (
            <p className="mt-3 text-[11px] text-ink/40 dark:text-ink-dark/40">Last updated {new Date(updatedAt).toLocaleString()}</p>
          )}
        </Card>
      )}

      {allConfirmed && (
        <div className="mx-auto mt-6 max-w-6xl">
          <h2 className="font-display text-base font-semibold text-ink dark:text-ink-dark">Recommended for you</h2>
          <div className="mt-3">
            <RecommendedProducts onAddToCart={onAddToCart} />
          </div>
        </div>
      )}

      <div className="mx-auto max-w-6xl">
        <RoutineGenerator onAddToCart={onAddToCart} />
      </div>
    </div>
  );
}
