import { useRef, useMemo, useCallback, useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

const SUB_SECTOR_COLORS = [
  "#5B8DEF", "#6FCF97", "#F2994A", "#BB6BD9", "#56CCF2",
  "#EB5757", "#F2C94C", "#27AE60", "#9B51E0", "#2D9CDB",
];

function getSectorColor(subSector, sectorMap) {
  if (!subSector) return SUB_SECTOR_COLORS[0];
  if (!sectorMap.has(subSector)) {
    sectorMap.set(subSector, SUB_SECTOR_COLORS[sectorMap.size % SUB_SECTOR_COLORS.length]);
  }
  return sectorMap.get(subSector);
}

function fundingToRadius(funding, maxFunding) {
  if (!funding || !maxFunding) return 8;
  const normalized = Math.min(funding / maxFunding, 1);
  return 6 + normalized * 28;
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

  const maxFunding = useMemo(() => {
    return Math.max(...companies.map((c) => c.funding_numeric || 0), 1);
  }, [companies]);

  const graphData = useMemo(() => {
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
      radius: fundingToRadius(c.funding_numeric, maxFunding),
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

    return { nodes, links, sectorColorMap };
  }, [companies, maxFunding]);

  // Extract legend from sector color map
  const sectorLegend = useMemo(() => {
    const entries = [];
    if (graphData.sectorColorMap) {
      graphData.sectorColorMap.forEach((color, name) => {
        entries.push({ name, color });
      });
    }
    return entries;
  }, [graphData]);

  const nodeCanvasObject = useCallback(
    (node, ctx) => {
      const r = node.radius || 8;
      const isSelected = selectedNode && (selectedNode === node.id || selectedNode === node.name);
      const isHovered = hoveredNode && (hoveredNode.id === node.id);

      // Glow effect for hovered/selected nodes
      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 6, 0, 2 * Math.PI);
        const gradient = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r + 6);
        gradient.addColorStop(0, `${node.color}44`);
        gradient.addColorStop(1, `${node.color}00`);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      // Main circle with gradient
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      const grad = ctx.createRadialGradient(
        node.x - r * 0.3, node.y - r * 0.3, r * 0.1,
        node.x, node.y, r
      );
      grad.addColorStop(0, `${node.color}FF`);
      grad.addColorStop(1, `${node.color}AA`);
      ctx.fillStyle = grad;
      ctx.fill();

      // Border
      ctx.strokeStyle = isSelected ? "#FFFFFF" : `${node.color}88`;
      ctx.lineWidth = isSelected ? 2.5 : 1;
      ctx.stroke();

      // Initial letter
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#FFFFFF";
      ctx.font = `bold ${Math.max(r * 0.65, 9)}px -apple-system, system-ui, sans-serif`;
      ctx.fillText(node.initial, node.x, node.y);

      // Company name label below node
      ctx.fillStyle = "rgba(255,255,255,0.7)";
      ctx.font = `${Math.max(Math.min(r * 0.5, 11), 8)}px -apple-system, system-ui, sans-serif`;
      ctx.fillText(node.name, node.x, node.y + r + 10);
    },
    [selectedNode, hoveredNode]
  );

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const r = node.radius || 8;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  }, []);

  const linkColor = useCallback(() => "rgba(255,255,255,0.04)", []);

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
      className="relative w-full h-full bg-[hsl(var(--background))]"
      onMouseMove={handleMouseMove}
    >
      <ForceGraph2D
        ref={graphRef}
        graphData={{ nodes: graphData.nodes, links: graphData.links }}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={nodePointerAreaPaint}
        linkColor={linkColor}
        linkWidth={0.5}
        onNodeHover={handleNodeHover}
        onNodeClick={handleNodeClick}
        d3AlphaDecay={0.03}
        d3VelocityDecay={0.3}
        warmupTicks={50}
        cooldownTicks={100}
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />

      {/* Sector legend */}
      {sectorLegend.length > 0 && (
        <div className="absolute top-3 left-3 px-3 py-2.5 rounded-lg bg-[hsl(var(--card))]/90 backdrop-blur-sm border border-[hsl(var(--border))] shadow-lg">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2">
            Sectors
          </p>
          <div className="space-y-1.5">
            {sectorLegend.map(({ name, color }) => (
              <div key={name} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-[11px] text-[hsl(var(--foreground))]/80 truncate max-w-[140px]">
                  {name}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Funding size legend */}
      <div className="absolute bottom-3 left-3 px-3 py-2 rounded-lg bg-[hsl(var(--card))]/90 backdrop-blur-sm border border-[hsl(var(--border))] shadow-lg">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-1.5">
          Node Size = Funding
        </p>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-white/40" />
            <span className="text-[10px] text-[hsl(var(--muted-foreground))]">Low</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block w-3.5 h-3.5 rounded-full bg-white/40" />
            <span className="text-[10px] text-[hsl(var(--muted-foreground))]">High</span>
          </div>
        </div>
      </div>

      {/* Tooltip on hover */}
      {hoveredNode && (
        <div
          className="fixed z-50 pointer-events-none px-3.5 py-2.5 rounded-lg shadow-xl border border-[hsl(var(--border))] bg-[hsl(var(--popover))] text-[hsl(var(--popover-foreground))]"
          style={{
            left: tooltipPos.x + 14,
            top: tooltipPos.y - 12,
          }}
        >
          <p className="text-sm font-semibold mb-1">{hoveredNode.name}</p>
          <div className="space-y-0.5">
            {hoveredNode.sub_sector && (
              <p className="text-[11px] text-[hsl(217,91%,60%)]">{hoveredNode.sub_sector}</p>
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
          <p className="text-[9px] text-[hsl(var(--muted-foreground))] mt-1.5 pt-1 border-t border-[hsl(var(--border))]/50">
            Click for details
          </p>
        </div>
      )}
    </div>
  );
}
