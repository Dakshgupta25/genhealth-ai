/**
 * GenHealth AI — Charts Module
 *
 * Pure Canvas/SVG chart implementations (no external libraries).
 * All charts respect the GenHealth design system color tokens.
 */

const Charts = (() => {
  // ─── Design tokens ────────────────────────────────────────────────────────
  const COLORS = {
    primary:  "#0A2540",
    accent:   "#00C49A",
    low:      "#22C55E",
    moderate: "#F59E0B",
    high:     "#EF4444",
    muted:    "#64748B",
    border:   "#E2E8F0",
    surface:  "#FFFFFF",
  };

  // ─── Health Score Gauge ───────────────────────────────────────────────────

  /**
   * Draw the animated arc health score gauge.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {number} score  - Value 0–100
   * @param {number} animMs - Animation duration in ms
   */
  function drawHealthGauge(canvas, score, animMs = 1200) {
    const ctx = canvas.getContext("2d");
    const cx = canvas.width / 2;
    const cy = canvas.height / 2 + 20;
    const radius = Math.min(cx, cy) * 0.72;
    const startAngle = Math.PI * 0.75;
    const sweepAngle = Math.PI * 1.5;

    const arcColor = score >= 75 ? COLORS.low : score >= 50 ? COLORS.moderate : COLORS.high;

    let start = null;
    function animate(ts) {
      if (!start) start = ts;
      const elapsed = ts - start;
      const progress = Math.min(elapsed / animMs, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentScore = score * eased;
      const endAngle = startAngle + sweepAngle * (currentScore / 100);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Background arc
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startAngle, startAngle + sweepAngle);
      ctx.strokeStyle = COLORS.border;
      ctx.lineWidth = 14;
      ctx.lineCap = "round";
      ctx.stroke();

      // Score arc
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startAngle, endAngle);
      ctx.strokeStyle = arcColor;
      ctx.lineWidth = 14;
      ctx.lineCap = "round";
      ctx.stroke();

      // Score text
      ctx.fillStyle = COLORS.primary;
      ctx.font = `700 ${Math.round(radius * 0.52)}px 'Inter', sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(Math.round(currentScore), cx, cy);

      // Label
      ctx.fillStyle = COLORS.muted;
      ctx.font = `400 ${Math.round(radius * 0.18)}px 'Inter', sans-serif`;
      ctx.fillText("Health Score", cx, cy + radius * 0.38);

      if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }

  // ─── Risk Radar Chart ─────────────────────────────────────────────────────

  /**
   * Draw an animated 6-axis radar (spider) chart.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {Array<{label: string, value: number}>} dataPoints - value 0–100
   * @param {number} animMs
   */
  function drawRiskRadar(canvas, dataPoints, animMs = 1000) {
    const ctx = canvas.getContext("2d");
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const maxR = Math.min(cx, cy) * 0.75;
    const sides = dataPoints.length;
    const angleStep = (2 * Math.PI) / sides;

    function getPoint(index, value, r) {
      const angle = angleStep * index - Math.PI / 2;
      return {
        x: cx + r * (value / 100) * Math.cos(angle),
        y: cy + r * (value / 100) * Math.sin(angle),
      };
    }

    function drawFrame(scale) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Grid rings
      [0.25, 0.5, 0.75, 1.0].forEach((fraction) => {
        ctx.beginPath();
        for (let i = 0; i < sides; i++) {
          const angle = angleStep * i - Math.PI / 2;
          const px = cx + maxR * fraction * Math.cos(angle);
          const py = cy + maxR * fraction * Math.sin(angle);
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.strokeStyle = COLORS.border;
        ctx.lineWidth = 1;
        ctx.stroke();
      });

      // Axis lines
      for (let i = 0; i < sides; i++) {
        const angle = angleStep * i - Math.PI / 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + maxR * Math.cos(angle), cy + maxR * Math.sin(angle));
        ctx.strokeStyle = COLORS.border;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Animated data polygon
      ctx.beginPath();
      dataPoints.forEach((point, i) => {
        const p = getPoint(i, point.value * scale, maxR);
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
      });
      ctx.closePath();
      ctx.fillStyle = "rgba(0, 196, 154, 0.2)";
      ctx.fill();
      ctx.strokeStyle = COLORS.accent;
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Data points
      dataPoints.forEach((point, i) => {
        const p = getPoint(i, point.value * scale, maxR);
        ctx.beginPath();
        ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.accent;
        ctx.fill();
      });

      // Labels (not scaled — always full size)
      ctx.fillStyle = COLORS.primary;
      ctx.font = `500 12px 'Inter', sans-serif`;
      ctx.textAlign = "center";
      dataPoints.forEach((point, i) => {
        const angle = angleStep * i - Math.PI / 2;
        const lx = cx + (maxR + 24) * Math.cos(angle);
        const ly = cy + (maxR + 24) * Math.sin(angle);
        ctx.fillText(point.label, lx, ly);
      });
    }

    let start = null;
    function animate(ts) {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / animMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      drawFrame(eased);
      if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }

  // ─── Bar Chart ────────────────────────────────────────────────────────────

  /**
   * Draw a simple horizontal bar chart for trend data.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {Array<{label: string, value: number}>} items
   */
  function drawBarChart(canvas, items) {
    const ctx = canvas.getContext("2d");
    const padding = { top: 20, right: 20, bottom: 20, left: 120 };
    const w = canvas.width - padding.left - padding.right;
    const maxVal = Math.max(...items.map((i) => i.value), 1);
    const barH = 22;
    const gap = 12;

    canvas.height = items.length * (barH + gap) + padding.top + padding.bottom;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    items.forEach((item, idx) => {
      const y = padding.top + idx * (barH + gap);
      const barW = (item.value / maxVal) * w;

      // Label
      ctx.fillStyle = COLORS.primary;
      ctx.font = "400 12px 'Inter', sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(item.label, padding.left - 8, y + barH / 2 + 4);

      // Bar
      ctx.beginPath();
      ctx.roundRect(padding.left, y, barW, barH, 4);
      ctx.fillStyle = COLORS.accent;
      ctx.fill();

      // Value
      ctx.fillStyle = COLORS.muted;
      ctx.textAlign = "left";
      ctx.fillText(item.value, padding.left + barW + 6, y + barH / 2 + 4);
    });
  }

  return { drawHealthGauge, drawRiskRadar, drawBarChart, COLORS };
})();

window.Charts = Charts;
