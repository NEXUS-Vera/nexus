import './NodeChip.css';

export type NodeType = 'concept' | 'question' | 'claim' | 'artifact' | 'source' | 'note';
export type SupportState = 'supported' | 'tentative' | 'unsupported' | 'contested' | 'phantom';
export type ConfidenceLevel = '1_00' | '0_85' | '0_75' | '0_65' | '0_55' | 'amb';
export type RimGlyph = 'single-method' | 'contested' | 'stale';

/**
 * ⭐ The glyph carries TYPE. Hue only narrows it to a family.
 *
 * F4 (docs/F4_RESULT.md) killed the six-hue palette — Question and Artifact
 * came out at dE 0.002 under deuteranopia, which is to say the same colour.
 * Six hues cannot separate inside the dark-mode lightness band once
 * protanopia and deuteranopia collapse the red-green axis, so hue was demoted
 * to four families and the glyph was promoted from redundant to load-bearing.
 *
 * ⚠️ Which means this map is not decoration. Remove a glyph and two node types
 * become indistinguishable for ~8% of men.
 */
const TYPE_GLYPH: Record<NodeType, string> = {
  concept: '◆',
  question: '?',
  claim: '▲',
  artifact: '■',
  source: '▪',
  note: '·',
};

interface NodeChipProps {
  label: string;
  type: NodeType;
  supportState?: SupportState;
  confidence?: ConfidenceLevel;
  rimGlyphs?: RimGlyph[];
  onClick?: () => void;
}

export function NodeChip({
  label,
  type,
  supportState = 'supported',
  confidence = '1_00',
  rimGlyphs = [],
  onClick,
}: NodeChipProps) {
  // ⚠️ Three is readable; five is a rash. Anything new competes for one of
  // these rather than adding a fourth (Frontend/07 §2.1).
  const glyphMap: Record<RimGlyph, string> = {
    'single-method': '◑',
    contested: '⚡',
    stale: '◷',
  };

  const cssVars = {
    '--node-hue': `var(--type-${type})`,
    '--node-vsup': `var(--vsup-${confidence})`,
  } as React.CSSProperties;

  const Tag = onClick ? 'button' : 'div';

  return (
    <Tag
      className={`node-chip state-${supportState}`}
      style={cssVars}
      onClick={onClick}
      title={`${type} · ${supportState}`}
      type={onClick ? 'button' : undefined}
    >
      <span className="node-type-glyph" aria-hidden>
        {TYPE_GLYPH[type]}
      </span>
      <span className="node-label">{label}</span>
      {rimGlyphs.length > 0 && (
        <span className="node-rim-glyphs">
          {rimGlyphs.map((g) => (
            <span key={g} className={`rim-glyph glyph-${g}`} title={g}>
              {glyphMap[g]}
            </span>
          ))}
        </span>
      )}
      {/* The type name is what a screen reader announces — colour and glyph are
          both visual channels and neither reaches assistive tech. */}
      <span className="sr-only">{type}, {supportState}</span>
    </Tag>
  );
}
