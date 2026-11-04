import type { InspectionImage } from "../types";

interface TileRank {
  /** Highest defect severity on the tile; 0 when no defect was graded. */
  severity: number;
  /** 1 when a verified defect holds that top severity (verified outweighs needs review at a tie). */
  verified: number;
  reinspect: number;
  needsReview: number;
  defects: number;
}

function rankTile({ defects }: InspectionImage): TileRank {
  const rank: TileRank = { severity: 0, verified: 0, reinspect: 0, needsReview: 0, defects: defects.length };
  for (const item of defects) {
    const severity = item.assessment?.severity ?? 0;
    const verified = item.verification?.verdict === "ok" ? 1 : 0;
    if (severity > rank.severity || (severity === rank.severity && verified > rank.verified)) {
      rank.severity = severity;
      rank.verified = verified;
    }
    if (item.verification?.verdict === "reinspect") rank.reinspect += 1;
    if (item.verification?.verdict === "needs_review") rank.needsReview += 1;
  }
  return rank;
}

/**
 * Tiles from most to least severe: top defect severity, then verified before needs review at the
 * same severity, then more reinspect, then more needs_review defects. Ties keep the original order
 * (Array.prototype.sort is stable) and tiles without defects go last. Returns a new array.
 */
export function sortTilesBySeverity(images: readonly InspectionImage[]): InspectionImage[] {
  const ranked = images.map((image) => ({ image, rank: rankTile(image) }));
  ranked.sort((a, b) => {
    if ((a.rank.defects === 0) !== (b.rank.defects === 0)) return a.rank.defects === 0 ? 1 : -1;
    return (
      b.rank.severity - a.rank.severity ||
      b.rank.verified - a.rank.verified ||
      b.rank.reinspect - a.rank.reinspect ||
      b.rank.needsReview - a.rank.needsReview
    );
  });
  return ranked.map(({ image }) => image);
}
