// shapes.js
// Draws the six Qwirkle shapes (Circle, Star, Diamond, Square, Clover,
// Triangle) onto a canvas 2D context. Kept separate from gui.js so the
// art is easy to tweak without wading through layout code.
// Port of shapes.py (pygame.draw -> Canvas 2D).

const OUTLINE = "rgb(20, 20, 20)";

function starPoints(cx, cy, outerR, innerR, points = 5, rotationDeg = -90) {
  const pts = [];
  const step = Math.PI / points;
  let angle = (rotationDeg * Math.PI) / 180;
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
    angle += step;
  }
  return pts;
}

function fillStrokePolygon(ctx, pts, color, outline, outlineW) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = outline;
  ctx.lineWidth = outlineW;
  ctx.stroke();
}

// shape: one of Circle, Star, Diamond, Square, Clover, Triangle
// cx, cy: pixel center
// size: roughly the shape's radius/half-width in pixels
export function drawShape(ctx, shape, cx, cy, size, color, outline = OUTLINE, outlineW = 2) {
  switch (shape) {
    case "Circle": {
      ctx.beginPath();
      ctx.arc(cx, cy, size, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = outline;
      ctx.lineWidth = outlineW;
      ctx.stroke();
      break;
    }

    case "Square": {
      const s = size * 1.6;
      const x = cx - s / 2, y = cy - s / 2;
      const r = 3;
      roundRectPath(ctx, x, y, s, s, r);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = outline;
      ctx.lineWidth = outlineW;
      ctx.stroke();
      break;
    }

    case "Diamond": {
      const pts = [
        [cx, cy - size],
        [cx + size, cy],
        [cx, cy + size],
        [cx - size, cy],
      ];
      fillStrokePolygon(ctx, pts, color, outline, outlineW);
      break;
    }

    case "Star": {
      const pts = starPoints(cx, cy, size, size * 0.42, 5);
      fillStrokePolygon(ctx, pts, color, outline, outlineW);
      break;
    }

    case "Triangle": {
      const h = size * 1.3;
      const pts = [
        [cx, cy - h * 0.62],
        [cx - size, cy + h * 0.38],
        [cx + size, cy + h * 0.38],
      ];
      fillStrokePolygon(ctx, pts, color, outline, outlineW);
      break;
    }

    case "Clover": {
      // A 3-leaf clover: three overlapping circular "leaves" arranged in
      // a triangle around the center.
      const leafR = size * 0.55;
      const offset = size * 0.55;
      const angles = [-90, 30, 150]; // degrees, evenly spaced (3 leaves)
      const leaves = angles.map((a) => {
        const rad = (a * Math.PI) / 180;
        return [cx + offset * Math.cos(rad), cy + offset * Math.sin(rad)];
      });
      for (const [lx, ly] of leaves) {
        ctx.beginPath();
        ctx.arc(lx, ly, leafR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }
      for (const [lx, ly] of leaves) {
        ctx.beginPath();
        ctx.arc(lx, ly, leafR, 0, Math.PI * 2);
        ctx.strokeStyle = outline;
        ctx.lineWidth = outlineW;
        ctx.stroke();
      }
      break;
    }

    default:
      throw new Error(`Unknown shape: ${shape}`);
  }
}

// Manual rounded-rect path (works even on the rare browser without
// CanvasRenderingContext2D.roundRect).
export function roundRectPath(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.arcTo(x + w, y, x + w, y + rr, rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.arcTo(x + w, y + h, x + w - rr, y + h, rr);
  ctx.lineTo(x + rr, y + h);
  ctx.arcTo(x, y + h, x, y + h - rr, rr);
  ctx.lineTo(x, y + rr);
  ctx.arcTo(x, y, x + rr, y, rr);
  ctx.closePath();
}
