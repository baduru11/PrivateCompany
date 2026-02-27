import { useEffect, useState } from "react";
import { cn } from "../../lib/utils";
import { dotClasses, getConfidenceLevel } from "../shared/ConfidenceBadge";

/**
 * Sticky left sidebar navigation for Deep Dive sections.
 * Highlights the active section based on scroll position via IntersectionObserver.
 *
 * Props:
 *  - sections: Array of { id, title, confidence }
 *  - activeSection: string (controlled) — if provided, overrides internal tracking
 */
export default function SectionNav({ sections = [], activeSection: controlledActive }) {
  const [observedActive, setObservedActive] = useState(sections[0]?.id || "");
  const activeSection = controlledActive ?? observedActive;

  useEffect(() => {
    const ids = sections.map((s) => s.id);
    const elements = ids.map((id) => document.getElementById(id)).filter(Boolean);

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the topmost visible section
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);

        if (visible.length > 0) {
          setObservedActive(visible[0].target.id);
        }
      },
      {
        rootMargin: "-10% 0px -60% 0px",
        threshold: 0.1,
      }
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  const handleClick = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <nav className="w-52 shrink-0 sticky top-0 h-fit py-4 pr-4">
      <ul className="space-y-1">
        {sections.map((section) => {
          const isActive = activeSection === section.id;
          const level = section.confidence != null
            ? getConfidenceLevel(section.confidence)
            : null;

          return (
            <li key={section.id}>
              <button
                type="button"
                onClick={() => handleClick(section.id)}
                className={cn(
                  "w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm text-left transition-colors",
                  isActive
                    ? "bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))] font-medium"
                    : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]/50 hover:text-[hsl(var(--foreground))]"
                )}
              >
                {level && (
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      dotClasses[level.color]
                    )}
                  />
                )}
                <span className="truncate">{section.title}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
