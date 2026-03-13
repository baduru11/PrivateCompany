import { useEffect, useState } from "react";
import { cn } from "../../lib/utils";
import { dotClasses, getConfidenceLevel } from "../shared/ConfidenceBadge";

export default function SectionNav({ sections = [], activeSection: controlledActive }) {
  const [observedActive, setObservedActive] = useState(sections[0]?.id || "");
  const activeSection = controlledActive ?? observedActive;

  useEffect(() => {
    const ids = sections.map((s) => s.id);
    const elements = ids.map((id) => document.getElementById(id)).filter(Boolean);

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
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
    <nav className="w-48 shrink-0 sticky top-0 h-fit py-5 pr-4 pl-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]/60 px-3 mb-3">
        Sections
      </p>
      <ul className="space-y-0.5">
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
                  "w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-left transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
                  isActive
                    ? "bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))] font-medium border-l-2 border-[hsl(var(--primary))] -ml-px"
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
