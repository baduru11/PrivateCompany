import { useRef, useMemo, useCallback, useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

// Muted, slightly desaturated palette (Obsidian-style)
const SUB_SECTOR_COLORS = [
  "#6B93D6", "#5EAD8A", "#D4915E", "#A76BBF", "#5EB8D4",
  "#CF6B6B", "#D4B85E", "#4A9E6B", "#8B5EC2", "#4A8EBF",
];

function getSectorColor(subSector, sectorMap) {
  if (!subSector) return SUB_SECTOR_COLORS[0];
  if (!sectorMap.has(subSector)) {
    sectorMap.set(subSector, SUB_SECTOR_COLORS[sectorMap.size % SUB_SECTOR_COLORS.length]);
  }
  return sectorMap.get(subSector);
}

function fundingToRadius(funding, maxFunding, fundingLabel) {
  if (!maxFunding) return 12;
  if ((!funding || funding === 0) && fundingLabel && /public|ipo/i.test(fundingLabel)) {
    return 30;
  }
  if (!funding || funding === 0) return 12;
  const normalized = Math.min(funding / maxFunding, 1);
  return 10 + normalized * 26;
}

// Parse hex color to r,g,b
function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return {
    r: parseInt(h.substring(0, 2), 16),
    g: parseInt(h.substring(2, 4), 16),
    b: parseInt(h.substring(4, 6), 16),
  };
}

export default function ForceGraph({
  companies = [],
  onNodeClick,
  selectedNode,
}) {
  const graphRef = useRef(null);
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Track container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Configure forces for tighter clustering
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;
    // Stronger center gravity to keep graph compact
    fg.d3Force("center")?.strength(1);
    // Moderate repulsion — enough to prevent overlap, not too much spread
    fg.d3Force("charge")?.strength(-120).distanceMax(250);
    // Shorter link distance to keep connected nodes close
    fg.d3Force("link")?.distance(60).strength(0.4);
  }, []);

  // Zoom to fit after data loads
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || companies.length === 0) return;
    const timer = setTimeout(() => {
      fg.zoomToFit(400, 40);
    }, 600);
    return () => clearTimeout(timer);
  }, [companies]);

  const maxFunding = useMemo(() => {
    return Math.max(...companies.map((c) => c.funding_numeric || 0), 1);
  }, [companies]);

  // Build neighbor sets for hover highlighting
  const { graphData, neighborMap, sectorLegend } = useMemo(() => {
    const sectorColorMap = new Map();
    const nodes = companies.map((c) => ({
      id: c.id || c.name,
      name: c.name,
      sub_sector: c.sub_sector,
      funding_numeric: c.funding_numeric || 0,
      founding_year: c.founding_year,
      description: c.description,
      confidence: c.confidence,
      funding: c.funding || c.funding_amount,
      funding_stage: c.funding_stage || c.stage,
      headquarters: c.headquarters || c.hq,
      key_investors: c.key_investors,
      color: getSectorColor(c.sub_sector, sectorColorMap),
      radius: fundingToRadius(c.funding_numeric, maxFunding, c.funding || c.funding_total || c.funding_amount),
      initial: c.name ? c.name.charAt(0).toUpperCase() : "?",
    }));

    const links = [];
    const bySector = {};
    nodes.forEach((n) => {
      if (!n.sub_sector) return;
      if (!bySector[n.sub_sector]) bySector[n.sub_sector] = [];
      bySector[n.sub_sector].push(n.id);
    });
    Object.values(bySector).forEach((ids) => {
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          links.push({ source: ids[i], target: ids[j] });
        }
      }
    });

    // Build neighbor map for hover dimming
    const nMap = new Map();
    nodes.forEach((n) => nMap.set(n.id, new Set()));
    links.forEach((l) => {
      const sid = typeof l.source === "object" ? l.source.id : l.source;
      const tid = typeof l.target === "object" ? l.target.id : l.target;
      nMap.get(sid)?.add(tid);
      nMap.get(tid)?.add(sid);
    });

    const legend = [];
    sectorColorMap.forEach((color, name) => legend.push({ name, color }));

    return {
      graphData: { nodes, links },
      neighborMap: nMap,
      sectorLegend: legend,
    };
  }, [companies, maxFunding]);

  // Check if a node is a neighbor of the hovered node
  const isNeighbor = useCallback(
    (nodeId) => {
      if (!hoveredNode) return true; // no hover = all visible
      if (nodeId === hoveredNode.id) return true;
      return neighborMap.get(hoveredNode.id)?.has(nodeId) || false;
    },
    [hoveredNode, neighborMap]
  );

  const nodeCanvasObject = useCallback(
    (node, ctx, globalScale) => {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

      const r = node.radius || 6;
      const isSelected = selectedNode && (selectedNode === node.id || selectedNode === node.name);
      const isHovered = hoveredNode && (hoveredNode.id === node.id);
      const isNbr = isNeighbor(node.id);

      // Obsidian-style dimming: non-connected nodes fade to ~12% opacity
      const nodeAlpha = hoveredNode ? (isNbr ? 1.0 : 0.12) : 1.0;
      ctx.globalAlpha = nodeAlpha;

      const { r: cr, g: cg, b: cb } = hexToRgb(node.color);

      // Subtle outer glow for all nodes
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
      const glowGrad = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r + 4);
      glowGrad.addColorStop(0, `rgba(${cr},${cg},${cb},0.15)`);
      glowGrad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
      ctx.fillStyle = glowGrad;
      ctx.fill();

      // Stronger glow for hovered/selected
      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 10, 0, 2 * Math.PI);
        const hoverGrad = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r + 10);
        hoverGrad.addColorStop(0, `rgba(${cr},${cg},${cb},0.35)`);
        hoverGrad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
        ctx.fillStyle = hoverGrad;
        ctx.fill();
      }

      // Main circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(${cr},${cg},${cb},0.85)`;
      ctx.fill();

      // Border ring
      ctx.strokeStyle = isSelected
        ? `rgba(255,255,255,0.9)`
        : `rgba(${cr},${cg},${cb},0.4)`;
      ctx.lineWidth = isSelected ? 2 : 0.8;
      ctx.stroke();

      // Initial letter (always visible inside node)
      ctx.fillStyle = `rgba(255,255,255,${nodeAlpha * 0.9})`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = `bold ${Math.max(r * 0.65, 8)}px -apple-system, system-ui, sans-serif`;
      ctx.fillText(node.initial, node.x, node.y);

      // Label below node — zoom-based fading (Obsidian-style LOD)
      const zoom = globalScale || 1;
      const labelAlpha = zoom > 1.5 ? 1.0
        : zoom > 0.8 ? (zoom - 0.8) / 0.7
        : 0;
      // Always show label for hovered/selected nodes regardless of zoom
      const showLabel = labelAlpha > 0.01 || isHovered || isSelected;
      if (showLabel) {
        const finalLabelAlpha = (isHovered || isSelected) ? 0.9 : labelAlpha * 0.6;
        ctx.fillStyle = `rgba(255,255,255,${finalLabelAlpha * nodeAlpha})`;
        ctx.font = `${Math.max(Math.min(r * 0.45, 10), 7)}px -apple-system, system-ui, sans-serif`;
        ctx.fillText(node.name, node.x, node.y + r + 8);
      }

      ctx.globalAlpha = 1.0;
    },
    [selectedNode, hoveredNode, isNeighbor]
  );

  // Link rendering — Obsidian-style: dim non-connected links on hover
  const linkCanvasObject = useCallback(
    (link, ctx) => {
      const source = link.source;
      const target = link.target;
      if (!Number.isFinite(source.x) || !Number.isFinite(target.x)) return;

      const sid = typeof source === "object" ? source.id : source;
      const tid = typeof target === "object" ? target.id : target;

      let alpha, width;
      if (!hoveredNode) {
        // Default: subtle visible links
        alpha = 0.08;
        width = 0.5;
      } else if (hoveredNode.id === sid || hoveredNode.id === tid) {
        // Connected to hovered node: highlight
        alpha = 0.35;
        width = 1.2;
      } else {
        // Not connected: very dim
        alpha = 0.02;
        width = 0.3;
      }

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = width;
      ctx.stroke();
    },
    [hoveredNode]
  );

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
    const r = (node.radius || 6) + 5; // Slightly larger hit area
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  }, []);

  const handleNodeHover = useCallback((node) => {
    setHoveredNode(node || null);
    const el = containerRef.current;
    if (el) el.style.cursor = node ? "pointer" : "default";
  }, []);

  const handleNodeClick = useCallback(
    (node) => { onNodeClick?.(node); },
    [onNodeClick]
  );

  const handleMouseMove = useCallback((e) => {
    setTooltipPos({ x: e.clientX, y: e.clientY });
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-0 bg-[hsl(var(--background))]"
      onMouseMove={handleMouseMove}
    >
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={nodePointerAreaPaint}
        linkCanvasObject={linkCanvasObject}
        onNodeHover={handleNodeHover}
        onNodeClick={handleNodeClick}
        // Obsidian-style force physics
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.25}
        d3AlphaMin={0.001}
        warmupTicks={80}
        cooldownTicks={200}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        // Force configuration
        dagMode={null}
        onEngineStop={() => graphRef.current?.zoomToFit(300, 50)}
      />

      {/* Sector legend */}
      {sectorLegend.length > 0 && (
        <div className="absolute top-3 left-3 px-3.5 py-3 rounded-xl glass border border-[hsl(var(--border))] shadow-xl">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]/70 mb-2.5">
            Sectors
          </p>
          <div className="space-y-2">
            {sectorLegend.map(({ name, color }) => (
              <div key={name} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0 ring-1 ring-white/10"
                  style={{ backgroundColor: color }}
                />
                <span className="text-[11px] text-[hsl(var(--foreground))]/75 truncate max-w-[140px]">
                  {name}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Funding size legend */}
      <div className="absolute bottom-3 left-3 px-3.5 py-2.5 rounded-xl glass border border-[hsl(var(--border))] shadow-xl">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]/70 mb-2">
          Node Size = Funding
        </p>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-white/30" />
            <span className="text-[10px] text-[hsl(var(--muted-foreground))]">Low</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-3.5 h-3.5 rounded-full bg-white/30" />
            <span className="text-[10px] text-[hsl(var(--muted-foreground))]">High</span>
          </div>
        </div>
      </div>

      {/* Tooltip on hover */}
      {hoveredNode && (
        <div
          className="fixed z-50 pointer-events-none px-4 py-3 rounded-xl shadow-2xl border border-[hsl(var(--border))] glass-strong"
          style={{
            left: tooltipPos.x + 14,
            top: tooltipPos.y - 12,
          }}
        >
          <p className="text-sm font-semibold text-[hsl(var(--foreground))] mb-1">{hoveredNode.name}</p>
          <div className="space-y-0.5">
            {hoveredNode.sub_sector && (
              <p className="text-[11px] text-blue-400">{hoveredNode.sub_sector}</p>
            )}
            {hoveredNode.funding && (
              <p className="text-[11px] text-[hsl(var(--muted-foreground))]">
                <span className="text-[hsl(var(--foreground))] font-medium">{hoveredNode.funding}</span> raised
              </p>
            )}
            {hoveredNode.funding_stage && (
              <p className="text-[11px] text-[hsl(var(--muted-foreground))]">
                Stage: {hoveredNode.funding_stage}
              </p>
            )}
            {hoveredNode.founding_year && (
              <p className="text-[11px] text-[hsl(var(--muted-foreground))]">
                Founded {hoveredNode.founding_year}
              </p>
            )}
            {hoveredNode.headquarters && (
              <p className="text-[11px] text-[hsl(var(--muted-foreground))]">
                {hoveredNode.headquarters}
              </p>
            )}
          </div>
          <p className="text-[9px] text-[hsl(var(--muted-foreground))]/60 mt-2 pt-1.5 border-t border-[hsl(var(--border))]/30">
            Click for details
          </p>
        </div>
      )}
    </div>
  );
}
