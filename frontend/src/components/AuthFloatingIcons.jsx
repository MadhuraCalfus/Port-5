import {
  Bell,
  CheckCircle2,
  Clock,
  Headphones,
  HelpCircle,
  Inbox,
  LifeBuoy,
  Mail,
  MessageSquare,
  ShieldCheck,
  Smile,
  Sparkles,
  Users,
  Zap,
} from "lucide-react";

/* Far ring: well clear of the card on any viewport width. */
const ICONS = [
  { Icon: Sparkles, top: "8%", left: "12%", size: 36, duration: "15s", delay: "0s" },
  { Icon: Headphones, top: "30%", left: "6%", size: 40, duration: "19s", delay: "2s" },
  { Icon: LifeBuoy, top: "56%", left: "8%", size: 30, duration: "17s", delay: "4s" },
  { Icon: Inbox, top: "80%", left: "10%", size: 32, duration: "21s", delay: "1s" },
  { Icon: MessageSquare, top: "14%", left: "88%", size: 32, duration: "17s", delay: "3s" },
  { Icon: Bell, top: "38%", left: "92%", size: 28, duration: "20s", delay: "0.5s" },
  { Icon: Clock, top: "62%", left: "90%", size: 34, duration: "23s", delay: "5s" },
  { Icon: CheckCircle2, top: "84%", left: "86%", size: 30, duration: "16s", delay: "2.5s" },
  { Icon: Mail, top: "6%", left: "50%", size: 26, duration: "18s", delay: "3.5s" },
  { Icon: Users, top: "92%", left: "48%", size: 30, duration: "22s", delay: "1.5s" },
  // Near ring: tucked right up against the card's corners, smaller so they read as an accent, not clutter.
  { Icon: Zap, top: "20%", left: "30%", size: 22, duration: "14s", delay: "0s" },
  { Icon: ShieldCheck, top: "22%", left: "68%", size: 22, duration: "16s", delay: "2s" },
  { Icon: Smile, top: "78%", left: "30%", size: 22, duration: "18s", delay: "1s" },
  { Icon: HelpCircle, top: "76%", left: "68%", size: 20, duration: "15s", delay: "3s" },
];

export function AuthFloatingIcons() {
  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      {ICONS.map(({ Icon, top, left, size, duration, delay }, i) => (
        <span
          key={i}
          className="auth-float-icon absolute"
          style={{ top, left, animationDuration: duration, animationDelay: delay }}
        >
          <Icon size={size} strokeWidth={1.5} />
        </span>
      ))}
    </div>
  );
}
