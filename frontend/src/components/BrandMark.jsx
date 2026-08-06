import { Gem } from "lucide-react";

// The NykaaPulse brand mark — one shared icon component instead of the
// literal 💄 emoji repeated across Header and every auth screen, so the
// logo always renders identically regardless of the viewer's OS emoji set.
export function BrandMark() {
  return (
    <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">
      <Gem size={16} strokeWidth={2} />
    </span>
  );
}
