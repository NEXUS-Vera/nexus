export type ThemeColors = {
  bg: string;
  surface: string;
  surface2: string;
  surface3: string;
  border: string;
  text: string;
  textSec: string;
  textMuted: string;
  cobalt: string;
  cobaltTint: string;
  cobaltSelected: string;
};

export function themeColors(isDark: boolean): ThemeColors {
  return {
    bg: isDark ? '#0D1117' : '#F7F8FA',
    surface: isDark ? '#151B24' : '#FFFFFF',
    surface2: isDark ? '#1C2430' : '#EEF1F5',
    surface3: isDark ? '#222B38' : '#F3F5F8',
    border: isDark ? '#2C3543' : '#D9DEE7',
    text: isDark ? '#F3F5F7' : '#151A23',
    textSec: isDark ? '#99A3B3' : '#667085',
    textMuted: isDark ? '#768194' : '#8A94A3',
    cobalt: isDark ? '#6C8DFF' : '#3563E9',
    cobaltTint: isDark ? '#1B2A52' : '#EAF0FF',
    cobaltSelected: isDark ? '#1B2A52' : '#F1F5FF',
  };
}

export const LIFECYCLE_DOT: Record<string, string> = {
  drafted: '#8A94A3',
  ready: '#159A7A',
  affected: '#DC6B20',
  stale: '#858B98',
  blocked: '#D14343',
  superseded: '#858B98',
  archived: '#8A94A3',
  unavailable: '#8A94A3',
};
