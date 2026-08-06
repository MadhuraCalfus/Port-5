import { useEffect, useState } from "react";
import clsx from "clsx";
import { ChevronLeft, ChevronRight } from "lucide-react";

// Static promotional images — marketing chrome, not customer data, so no
// backend endpoint needed. Auto-advances like a real storefront hero
// banner; arrows/dots let a shopper override the timer. Each path is served
// as-is from frontend/public/hero-slides/ (e.g. /hero-slides/img1.png).
const SLIDES = [
  { image: "/hero-slides/img1.jpeg" },
  { image: "/hero-slides/img2.jpeg" },
  { image: "/hero-slides/img3.jpg" },
];

const AUTO_ADVANCE_MS = 5000;

export function NykaaHeroSlider() {
  const [index, setIndex] = useState(0);
  // Falls back to a plain tinted panel whenever a slide's image file hasn't
  // been dropped into public/hero-slides/ yet (or fails to load).
  const [failedImages, setFailedImages] = useState(() => new Set());

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % SLIDES.length), AUTO_ADVANCE_MS);
    return () => clearInterval(id);
  }, []);

  const slide = SLIDES[index];
  const showImage = !failedImages.has(slide.image);

  return (
    <div className="relative h-96 w-full overflow-hidden rounded-2xl border border-black/8 dark:border-white/10 sm:h-[34rem]">
      {showImage ? (
        <img
          src={slide.image}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setFailedImages((prev) => new Set(prev).add(slide.image))}
        />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-brand/15 via-canvas to-brand/5" />
      )}

      <button
        type="button"
        onClick={() => setIndex((i) => (i - 1 + SLIDES.length) % SLIDES.length)}
        aria-label="Previous slide"
        className="absolute left-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-white/70 text-ink hover:bg-white"
      >
        <ChevronLeft size={16} />
      </button>
      <button
        type="button"
        onClick={() => setIndex((i) => (i + 1) % SLIDES.length)}
        aria-label="Next slide"
        className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-white/70 text-ink hover:bg-white"
      >
        <ChevronRight size={16} />
      </button>

      <div className="absolute bottom-3 left-0 right-0 flex items-center justify-center gap-1.5">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={`Go to slide ${i + 1}`}
            className={clsx("h-1.5 rounded-full transition-all", i === index ? "w-6 bg-white" : "w-1.5 bg-white/50")}
          />
        ))}
      </div>
    </div>
  );
}
