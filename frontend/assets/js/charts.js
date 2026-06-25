// charts.js — pure vanilla SVG charts without any external libraries

function createSVGElement(tag) {
  return document.createElementNS("http://www.w3.org/2000/svg", tag);
}

function drawRadarChart(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const width = 360;
  const height = 320;
  const cx = width / 2;
  const cy = height / 2 + 10;
  const R = 110;

  const svg = createSVGElement('svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.style.overflow = 'visible';

  // Extract axes and values
  const n = data.length;
  const angles = [];
  for (let i = 0; i < n; i++) {
    angles.push((Math.PI * 2 * i / n) - Math.PI / 2);
  }

  // Draw background concentric polygon rings (5 rings)
  for (let ring = 1; ring <= 5; ring++) {
    const r = R * ring / 5;
    const polygon = createSVGElement('polygon');
    const points = [];
    for (let i = 0; i < n; i++) {
      const x = cx + Math.cos(angles[i]) * r;
      const y = cy + Math.sin(angles[i]) * r;
      points.push(`${x},${y}`);
    }
    polygon.setAttribute('points', points.join(' '));
    polygon.setAttribute('fill', 'none');
    polygon.setAttribute('stroke', 'var(--color-border)');
    polygon.setAttribute('stroke-width', '1');
    svg.appendChild(polygon);
  }

  // Draw axis lines and text labels
  for (let i = 0; i < n; i++) {
    const angle = angles[i];
    const x = cx + Math.cos(angle) * R;
    const y = cy + Math.sin(angle) * R;

    // Axis line
    const line = createSVGElement('line');
    line.setAttribute('x1', cx.toString());
    line.setAttribute('y1', cy.toString());
    line.setAttribute('x2', x.toString());
    line.setAttribute('y2', y.toString());
    line.setAttribute('stroke', 'var(--color-border)');
    line.setAttribute('stroke-width', '1');
    svg.appendChild(line);

    // Label
    const textX = cx + Math.cos(angle) * (R + 22);
    const textY = cy + Math.sin(angle) * (R + 15);
    const text = createSVGElement('text');
    text.setAttribute('x', textX.toString());
    text.setAttribute('y', textY.toString());
    text.setAttribute('font-size', '11px');
    text.setAttribute('font-family', 'var(--font-body)');
    text.setAttribute('fill', 'var(--color-muted)');
    text.setAttribute('text-anchor', Math.abs(Math.cos(angle)) < 0.1 ? 'center' : Math.cos(angle) > 0 ? 'start' : 'end');
    
    // Split multi-line labels if any
    const parts = data[i].axis.split('\n');
    if (parts.length > 1) {
      parts.forEach((p, idx) => {
        const tspan = createSVGElement('tspan');
        tspan.textContent = p;
        tspan.setAttribute('x', textX.toString());
        tspan.setAttribute('dy', idx === 0 ? '0' : '12');
        text.appendChild(tspan);
      });
    } else {
      text.textContent = data[i].axis;
    }
    svg.appendChild(text);
  }

  // Data Polygon (with animation)
  const dataPolygon = createSVGElement('polygon');
  dataPolygon.setAttribute('fill', 'rgba(0, 196, 154, 0.15)');
  dataPolygon.setAttribute('stroke', 'var(--color-accent)');
  dataPolygon.setAttribute('stroke-width', '2.5');
  svg.appendChild(dataPolygon);

  // Dots group
  const dotsGroup = createSVGElement('g');
  svg.appendChild(dotsGroup);

  container.appendChild(svg);

  // Animation logic
  const duration = 800;
  const start = performance.now();

  function animate(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3); // cubic ease out

    const points = [];
    dotsGroup.innerHTML = ''; // clear previous dots

    for (let i = 0; i < n; i++) {
      const val = data[i].value * ease;
      const r = R * val;
      const x = cx + Math.cos(angles[i]) * r;
      const y = cy + Math.sin(angles[i]) * r;
      points.push(`${x},${y}`);

      // Data point circle
      const circle = createSVGElement('circle');
      circle.setAttribute('cx', x.toString());
      circle.setAttribute('cy', y.toString());
      circle.setAttribute('r', '5');
      const pointColor = data[i].value > 0.5 ? 'var(--color-risk-high)' : data[i].value > 0.3 ? 'var(--color-risk-moderate)' : 'var(--color-risk-low)';
      circle.setAttribute('fill', pointColor);
      circle.setAttribute('stroke', 'var(--color-surface)');
      circle.setAttribute('stroke-width', '2');
      circle.style.cursor = 'pointer';

      // Tooltip behavior
      circle.addEventListener('mouseover', (e) => {
        circle.setAttribute('r', '7');
        const tooltipText = `${data[i].axis}: ${(data[i].value * 100).toFixed(0)}%`;
        if (window.app && window.app.showTooltip) {
          window.app.showTooltip(e, tooltipText);
        }
      });
      circle.addEventListener('mouseout', () => {
        circle.setAttribute('r', '5');
        if (window.app && window.app.hideTooltip) {
          window.app.hideTooltip();
        }
      });

      dotsGroup.appendChild(circle);
    }

    dataPolygon.setAttribute('points', points.join(' '));

    if (progress < 1) {
      requestAnimationFrame(animate);
    }
  }

  requestAnimationFrame(animate);
}

function drawHealthGauge(containerId, score) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const size = 160;
  const cx = size / 2;
  const cy = size / 2;
  const r = 62;
  const strokeWidth = 12;

  // Arc angles: start 135 deg, end 405 deg (which spans 270 deg)
  const startAngle = 135;
  const endAngle = 405;

  const svg = createSVGElement('svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', `0 0 ${size} ${size}`);

  // Helper for polar to cartesian coordinates
  function polarToCartesian(centerX, centerY, radius, angleInDegrees) {
    const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
    return {
      x: centerX + (radius * Math.cos(angleInRadians)),
      y: centerY + (radius * Math.sin(angleInRadians))
    };
  }

  // Draw arc description string
  function describeArc(x, y, radius, startAngle, endAngle) {
    const start = polarToCartesian(x, y, radius, endAngle);
    const end = polarToCartesian(x, y, radius, startAngle);
    const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
    return [
      "M", start.x, start.y, 
      "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y
    ].join(" ");
  }

  // Background track
  const track = createSVGElement('path');
  track.setAttribute('d', describeArc(cx, cy, r, startAngle, endAngle));
  track.setAttribute('fill', 'none');
  track.setAttribute('stroke', document.body.classList.contains('dark') ? '#30363D' : '#E2E8F0');
  track.setAttribute('stroke-width', strokeWidth.toString());
  track.setAttribute('stroke-linecap', 'round');
  svg.appendChild(track);

  // Active arc
  const activeArc = createSVGElement('path');
  activeArc.setAttribute('fill', 'none');
  activeArc.setAttribute('stroke-width', strokeWidth.toString());
  activeArc.setAttribute('stroke-linecap', 'round');
  svg.appendChild(activeArc);

  // Append gauge wrapper to container
  container.appendChild(svg);

  // Animation values
  const duration = 1000;
  const start = performance.now();
  const color = score >= 80 ? 'var(--color-risk-low)' : score >= 50 ? 'var(--color-risk-moderate)' : 'var(--color-risk-high)';
  activeArc.setAttribute('stroke', color);

  function animate(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // cubic ease out
    const currentScore = score * eased;

    const angleSpan = endAngle - startAngle;
    const currentEndAngle = startAngle + (angleSpan * (currentScore / 100.0));
    
    activeArc.setAttribute('d', describeArc(cx, cy, r, startAngle, currentEndAngle));

    // Update center number if element exists
    const scoreNum = document.getElementById('gaugeNumber');
    if (scoreNum) {
      scoreNum.textContent = Math.round(currentScore).toString();
    }

    if (progress < 1) {
      requestAnimationFrame(animate);
    }
  }

  requestAnimationFrame(animate);
}

function drawTrendLine(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const width = 500;
  const height = 220;
  const paddingLeft = 40;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;

  const svg = createSVGElement('svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.style.overflow = 'visible';

  // Draw grid background and axes
  const gridGroup = createSVGElement('g');
  svg.appendChild(gridGroup);

  // Draw Y-axis markings (0%, 25%, 50%, 75%, 100%)
  const chartHeight = height - paddingTop - paddingBottom;
  for (let i = 0; i <= 4; i++) {
    const yVal = paddingTop + (chartHeight * i / 4);
    const gridLine = createSVGElement('line');
    gridLine.setAttribute('x1', paddingLeft.toString());
    gridLine.setAttribute('y1', yVal.toString());
    gridLine.setAttribute('x2', (width - paddingRight).toString());
    gridLine.setAttribute('y2', yVal.toString());
    gridLine.setAttribute('stroke', 'var(--color-border)');
    gridLine.setAttribute('stroke-width', '1');
    gridGroup.appendChild(gridLine);

    // Label
    const text = createSVGElement('text');
    text.setAttribute('x', (paddingLeft - 10).toString());
    text.setAttribute('y', (yVal + 4).toString());
    text.setAttribute('font-size', '10px');
    text.setAttribute('text-anchor', 'end');
    text.setAttribute('fill', 'var(--color-muted)');
    text.textContent = `${100 - (i * 25)}%`;
    gridGroup.appendChild(text);
  }

  // Draw X-axis text and compute points coordinates
  const n = data.length;
  const chartWidth = width - paddingLeft - paddingRight;
  const points = [];

  for (let i = 0; i < n; i++) {
    const xVal = paddingLeft + (chartWidth * i / (n - 1));
    const yVal = paddingTop + chartHeight * (1 - data[i].value); // Y goes down in SVG
    points.push({ x: xVal, y: yVal, label: data[i].label, rawValue: data[i].value });

    // X label
    const text = createSVGElement('text');
    text.setAttribute('x', xVal.toString());
    text.setAttribute('y', (height - paddingBottom + 20).toString());
    text.setAttribute('font-size', '10px');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('fill', 'var(--color-muted)');
    text.textContent = data[i].label;
    gridGroup.appendChild(text);
  }

  // Draw line path
  const linePath = createSVGElement('path');
  linePath.setAttribute('fill', 'none');
  linePath.setAttribute('stroke', 'var(--color-accent)');
  linePath.setAttribute('stroke-width', '3');
  svg.appendChild(linePath);

  // Area path below the line
  const areaPath = createSVGElement('path');
  areaPath.setAttribute('fill', 'rgba(0, 196, 154, 0.08)');
  svg.appendChild(areaPath);

  // Dots group
  const dots = createSVGElement('g');
  svg.appendChild(dots);

  container.appendChild(svg);

  // Animate drawing the line path
  const duration = 1000;
  const start = performance.now();

  function animate(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);

    const activePoints = [];
    dots.innerHTML = ''; // clear dots

    for (let i = 0; i < n; i++) {
      const pt = points[i];
      // Target Y coordinates starts at bottom (baseline) and slides up to computed Y
      const baselineY = height - paddingBottom;
      const currentY = baselineY - (baselineY - pt.y) * eased;
      activePoints.push({ x: pt.x, y: currentY });

      // Draw point dot
      const dot = createSVGElement('circle');
      dot.setAttribute('cx', pt.x.toString());
      dot.setAttribute('cy', currentY.toString());
      dot.setAttribute('r', '4');
      dot.setAttribute('fill', 'var(--color-accent)');
      dot.setAttribute('stroke', 'var(--color-surface)');
      dot.setAttribute('stroke-width', '2');
      dot.style.cursor = 'pointer';

      // Attach tooltip
      dot.addEventListener('mouseover', (e) => {
        dot.setAttribute('r', '6');
        const text = `${pt.label}: ${(pt.rawValue * 100).toFixed(0)}%`;
        if (window.app && window.app.showTooltip) {
          window.app.showTooltip(e, text);
        }
      });
      dot.addEventListener('mouseout', () => {
        dot.setAttribute('r', '4');
        if (window.app && window.app.hideTooltip) {
          window.app.hideTooltip();
        }
      });

      dots.appendChild(dot);
    }

    // Build SVG path strings
    let d = `M ${activePoints[0].x} ${activePoints[0].y}`;
    for (let i = 1; i < n; i++) {
      d += ` L ${activePoints[i].x} ${activePoints[i].y}`;
    }
    linePath.setAttribute('d', d);

    // Area path ends down at the bottom margin line
    const areaD = d + ` L ${activePoints[n-1].x} ${height - paddingBottom} L ${activePoints[0].x} ${height - paddingBottom} Z`;
    areaPath.setAttribute('d', areaD);

    if (progress < 1) {
      requestAnimationFrame(animate);
    }
  }

  requestAnimationFrame(animate);
}

function drawHeatmap(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const cellWidth = 14;
  const cellHeight = 14;
  const gap = 3;
  
  // Renders a grid of 52 weeks × 7 days (standard GitHub layout)
  const columns = 52;
  const rows = 7;

  const width = columns * (cellWidth + gap) + 40;
  const height = rows * (cellHeight + gap) + 30;

  const svg = createSVGElement('svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  // Create weeks array and map events data to the grid coordinates
  // Stub colors representing activity density
  // We can select shade opacity based on counts:
  // 0 counts = empty shade, 1 count = light accent, 2-3 count = medium, 4+ = high density
  const getShade = (count) => {
    if (!count || count === 0) return document.body.classList.contains('dark') ? '#21262d' : '#ebedf0';
    if (count === 1) return 'rgba(0, 196, 154, 0.25)';
    if (count === 2) return 'rgba(0, 196, 154, 0.5)';
    if (count === 3) return 'rgba(0, 196, 154, 0.75)';
    return 'var(--color-accent)';
  };

  // Convert month array count mappings
  const countsMap = {};
  if (data && Array.isArray(data)) {
    data.forEach(item => {
      // item: { date: 'YYYY-MM-DD', count: N } or { month: 'YYYY-MM', count: N }
      if (item.date) countsMap[item.date] = item.count;
    });
  }

  // Draw day of week labels (Mon, Wed, Fri)
  const dayLabels = ['Mon', '', 'Wed', '', 'Fri', '', ''];
  dayLabels.forEach((label, idx) => {
    if (label) {
      const text = createSVGElement('text');
      text.setAttribute('x', '5');
      text.setAttribute('y', (20 + idx * (cellHeight + gap) + 11).toString());
      text.setAttribute('font-size', '9px');
      text.setAttribute('font-family', 'var(--font-body)');
      text.setAttribute('fill', 'var(--color-muted)');
      text.textContent = label;
      svg.appendChild(text);
    }
  });

  // Plot cells
  const gridGroup = createSVGElement('g');
  gridGroup.setAttribute('transform', 'translate(30, 20)');

  // Let's iterate columns and rows
  const today = new Date();
  const startOffset = today.getDay(); // 0 is Sunday, etc.
  const totalDays = columns * rows;
  const startDate = new Date();
  startDate.setDate(today.getDate() - totalDays + 1);

  let cellIndex = 0;
  for (let col = 0; col < columns; col++) {
    for (let row = 0; row < rows; row++) {
      const cellDate = new Date(startDate.getTime());
      cellDate.setDate(startDate.getDate() + cellIndex);
      
      const dateString = cellDate.toISOString().split('T')[0];
      const count = countsMap[dateString] || 0;

      const rect = createSVGElement('rect');
      rect.setAttribute('x', (col * (cellWidth + gap)).toString());
      rect.setAttribute('y', (row * (cellHeight + gap)).toString());
      rect.setAttribute('width', cellWidth.toString());
      rect.setAttribute('height', cellHeight.toString());
      rect.setAttribute('rx', '2');
      rect.setAttribute('fill', getShade(count));
      rect.style.cursor = 'pointer';

      // Tooltip details
      rect.addEventListener('mouseover', (e) => {
        rect.setAttribute('stroke', '#000');
        rect.setAttribute('stroke-width', '1');
        const formattedDate = cellDate.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' });
        const tooltipVal = `${count} health record update(s) on ${formattedDate}`;
        if (window.app && window.app.showTooltip) {
          window.app.showTooltip(e, tooltipVal);
        }
      });

      rect.addEventListener('mouseout', () => {
        rect.removeAttribute('stroke');
        rect.removeAttribute('stroke-width');
        if (window.app && window.app.hideTooltip) {
          window.app.hideTooltip();
        }
      });

      gridGroup.appendChild(rect);
      cellIndex++;
    }
  }

  svg.appendChild(gridGroup);
  container.appendChild(svg);
}
