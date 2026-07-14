import React, {
  Children,
  isValidElement,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type ReactElement,
} from "react";

// ─── Exported types ─────────────────────────────────────────────────────────

export interface ResizableGroupProps {
  orientation: "horizontal" | "vertical";
  storageKey?: string;
  children: ReactNode;
  className?: string;
}
export interface ResizablePanelProps {
  defaultSize: number;
  minSize?: number;
  maxSize?: number;
  children: ReactNode;
  className?: string;
}
export interface ResizableSeparatorProps {
  className?: string;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const SEP = 6; // separator hit area in px

// ─── Helpers ────────────────────────────────────────────────────────────────

function isPanel(c: ReactNode): c is ReactElement<ResizablePanelProps> {
  return (
    isValidElement(c) &&
    (c.type as { displayName?: string }).displayName === "ResizablePanel"
  );
}
function isSep(c: ReactNode): c is ReactElement<ResizableSeparatorProps> {
  return (
    isValidElement(c) &&
    (c.type as { displayName?: string }).displayName === "ResizableSeparator"
  );
}

// ─── ResizableGroup ─────────────────────────────────────────────────────────

export function ResizableGroup({
  orientation,
  storageKey,
  children,
  className = "",
}: ResizableGroupProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [px, setPx] = useState(0);

  const arr = Children.toArray(children);
  const sepCount = arr.filter(isSep).length;
  const defaultSizes = useMemo(() => arr.filter(isPanel).map((p) => p.props.defaultSize), []);
  const constraints = useMemo(
    () => arr.filter(isPanel).map((p) => ({
      minSize: p.props.minSize ?? 0,
      maxSize: p.props.maxSize ?? 100,
    })),
    [],
  );

  const [sizes, setSizes] = useState<number[]>(() => {
    if (storageKey) {
      try {
        const s = localStorage.getItem(storageKey);
        if (s) {
          const p = JSON.parse(s);
          if (Array.isArray(p) && p.length === defaultSizes.length && p.every((n: unknown) => typeof n === "number" && n > 0)) return p;
        }
      } catch { /* */ }
    }
    return defaultSizes;
  });

  const szRef = useRef(sizes);
  szRef.current = sizes;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const m = () => {
      const r = el.getBoundingClientRect();
      setPx(orientation === "horizontal" ? r.width : r.height);
    };
    m();
    const ro = new ResizeObserver(m);
    ro.observe(el);
    return () => ro.disconnect();
  }, [orientation]);

  const avail = Math.max(1, px - sepCount * SEP);
  const isH = orientation === "horizontal";

  const onDown = useCallback(
    (sepIdx: number, e: React.MouseEvent) => {
      e.preventDefault();
      const el = ref.current;
      if (!el) return;
      const start = isH ? e.clientX : e.clientY;
      const init = [...szRef.current];

      const move = (ev: MouseEvent) => {
        const cur = isH ? ev.clientX : ev.clientY;
        let d = ((cur - start) / avail) * 100;
        const lMin = constraints[sepIdx]?.minSize ?? 0;
        const lMax = constraints[sepIdx]?.maxSize ?? 100;
        const rMin = constraints[sepIdx + 1]?.minSize ?? 0;
        const rMax = constraints[sepIdx + 1]?.maxSize ?? 100;
        if (init[sepIdx] + d < lMin) d = lMin - init[sepIdx];
        if (init[sepIdx] + d > lMax) d = lMax - init[sepIdx];
        if (init[sepIdx + 1] - d < rMin) d = init[sepIdx + 1] - rMin;
        if (init[sepIdx + 1] - d > rMax) d = init[sepIdx + 1] - rMax;
        const n = [...init];
        n[sepIdx] = init[sepIdx] + d;
        n[sepIdx + 1] = init[sepIdx + 1] - d;
        setSizes(n);
      };

      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        if (storageKey) {
          try { localStorage.setItem(storageKey, JSON.stringify(szRef.current)); } catch { /* */ }
        }
      };

      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
      document.body.style.cursor = isH ? "col-resize" : "row-resize";
      document.body.style.userSelect = "none";
    },
    [isH, avail, constraints, storageKey],
  );

  let pi = 0;
  let si = 0;
  const enhanced = arr.map((child) => {
    if (isPanel(child)) {
      const idx = pi++;
      const pxVal = Math.round((sizes[idx] / 100) * avail);
      return (
        <div
          key={`p-${idx}`}
          className={child.props.className}
          style={{
            flex: "0 0 auto",
            overflow: "hidden",
            minWidth: 0,
            minHeight: 0,
            [isH ? "width" : "height"]: pxVal,
            [isH ? "height" : "width"]: "100%",
          }}
        >
          {child.props.children}
        </div>
      );
    }
    if (isSep(child)) {
      const idx = si++;
      return <Separator key={`s-${idx}`} isH={isH} className={child.props.className} onDown={(e) => onDown(idx, e)} />;
    }
    return child;
  });

  return (
    <div
      ref={ref}
      className={className}
      style={{
        display: "flex",
        flexDirection: isH ? "row" : "column",
        height: "100%",
        width: "100%",
        overflow: "hidden",
      }}
    >
      {enhanced}
    </div>
  );
}
ResizableGroup.displayName = "ResizableGroup";

// ─── Separator visual ───────────────────────────────────────────────────────

function Separator({
  isH,
  onDown,
  className,
}: {
  isH: boolean;
  onDown: (e: React.MouseEvent) => void;
  className?: string;
}) {
  const [hov, setHov] = useState(false);
  return (
    <div
      className={className}
      style={{
        flex: "0 0 auto",
        position: "relative",
        background: "transparent",
        zIndex: 10,
        [isH ? "width" : "height"]: SEP,
        [isH ? "height" : "width"]: "100%",
        cursor: isH ? "col-resize" : "row-resize",
      }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      onMouseDown={onDown}
    >
      <div
        style={{
          position: "absolute",
          transition: "all 150ms ease",
          borderRadius: 1,
          ...(isH
            ? { top: 0, bottom: 0, left: "50%", transform: "translateX(-50%)", width: hov ? 2 : 1 }
            : { left: 0, right: 0, top: "50%", transform: "translateY(-50%)", height: hov ? 2 : 1 }),
          background: hov ? "var(--accent-primary)" : "var(--border-color)",
        }}
      />
    </div>
  );
}

// ─── Marker components (parsed by ResizableGroup, render nothing standalone) ─

export function ResizablePanel(_p: ResizablePanelProps) { return null; }
ResizablePanel.displayName = "ResizablePanel";
export function ResizableSeparator(_p: ResizableSeparatorProps) { return null; }
ResizableSeparator.displayName = "ResizableSeparator";
