// Amendator Formatting Utilities
// Based on European Parliament amendment drafting conventions

import type { TextChange, AmendmentType } from '../pages/amendator_page';

/**
 * Formats text with bold italic for changed portions
 * Returns HTML string with <strong><em> tags for changed text
 */
export const formatTextWithChanges = (
  text: string,
  changes: TextChange[] | undefined,
  column: 'original' | 'amendment'
): string => {
  if (!changes || changes.length === 0) {
    return text;
  }

  // Sort changes by start position to process in order
  const sortedChanges = [...changes].sort((a, b) => a.start - b.start);

  let result = '';
  let lastIndex = 0;

  sortedChanges.forEach((change) => {
    // Add unchanged text before this change
    result += text.substring(lastIndex, change.start);

    // Add the changed text with bold italic formatting
    const changedText = column === 'original' ? change.oldText : change.newText;
    result += `<strong><em>${changedText}</em></strong>`;

    lastIndex = change.end;
  });

  // Add remaining unchanged text
  result += text.substring(lastIndex);

  return result;
};

/**
 * Formats the original column text based on amendment type
 */
export const formatOriginalColumn = (
  originalText: string,
  type: AmendmentType,
  changes?: TextChange[],
  isCompleteSupression?: boolean
): string => {
  switch (type) {
    case 'addition':
      // Addition: Show "No original text" in italic
      return '<em>No original text</em>';

    case 'suppression':
      if (isCompleteSupression) {
        // Complete suppression: Show all text in bold italic
        return `<strong><em>${originalText}</em></strong>`;
      } else {
        // Partial suppression: Show deleted portion in bold italic
        return formatTextWithChanges(originalText, changes, 'original');
      }

    case 'modification':
      // Modification: Show old words in bold italic
      return formatTextWithChanges(originalText, changes, 'original');

    default:
      return originalText;
  }
};

/**
 * Formats the amendment column text based on amendment type
 */
export const formatAmendmentColumn = (
  proposedText: string,
  type: AmendmentType,
  changes?: TextChange[],
  isCompleteSupression?: boolean
): string => {
  switch (type) {
    case 'addition':
      // Addition: Show new text in bold italic
      return `<strong><em>${proposedText}</em></strong>`;

    case 'suppression':
      if (isCompleteSupression) {
        // Complete suppression: Show "Suppressed text" in italic
        return '<em>Suppressed text</em>';
      } else {
        // Partial suppression: Show remaining text (deleted portion absent)
        return proposedText;
      }

    case 'modification':
      // Modification: Show new words in bold italic
      return formatTextWithChanges(proposedText, changes, 'amendment');

    default:
      return proposedText;
  }
};

/**
 * Detects changes between original and proposed text using LCS-based word diff.
 * Returns two arrays: changes mapped to original text positions, and changes mapped to proposed text positions.
 * The returned TextChange[] uses `start`/`end` relative to the original text,
 * and `oldText`/`newText` for the replaced content.
 */
export const detectChanges = (original: string, proposed: string): TextChange[] => {
  // Split preserving whitespace tokens so we can reconstruct exact positions
  const originalTokens = original.split(/(\s+)/);
  const proposedTokens = proposed.split(/(\s+)/);

  // Build LCS table on word tokens (skip whitespace for comparison)
  const origWords: { text: string; pos: number }[] = [];
  const propWords: { text: string; pos: number }[] = [];

  let pos = 0;
  for (const token of originalTokens) {
    if (token.trim()) origWords.push({ text: token, pos });
    pos += token.length;
  }
  pos = 0;
  for (const token of proposedTokens) {
    if (token.trim()) propWords.push({ text: token, pos });
    pos += token.length;
  }

  // LCS dynamic programming
  const m = origWords.length;
  const n = propWords.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (origWords[i - 1].text === propWords[j - 1].text) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to get opcodes (equal, replace, insert, delete)
  type OpCode = { tag: 'equal' | 'replace' | 'insert' | 'delete'; i1: number; i2: number; j1: number; j2: number };
  const matched: [number, number][] = [];
  let i = m, j = n;
  while (i > 0 && j > 0) {
    if (origWords[i - 1].text === propWords[j - 1].text) {
      matched.unshift([i - 1, j - 1]);
      i--; j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }

  // Generate opcodes from matched pairs
  const opcodes: OpCode[] = [];
  let lastI = 0, lastJ = 0;
  for (const [mi, mj] of matched) {
    if (mi > lastI || mj > lastJ) {
      if (mi > lastI && mj > lastJ) {
        opcodes.push({ tag: 'replace', i1: lastI, i2: mi, j1: lastJ, j2: mj });
      } else if (mi > lastI) {
        opcodes.push({ tag: 'delete', i1: lastI, i2: mi, j1: lastJ, j2: lastJ });
      } else {
        opcodes.push({ tag: 'insert', i1: lastI, i2: lastI, j1: lastJ, j2: mj });
      }
    }
    opcodes.push({ tag: 'equal', i1: mi, i2: mi + 1, j1: mj, j2: mj + 1 });
    lastI = mi + 1;
    lastJ = mj + 1;
  }
  if (lastI < m || lastJ < n) {
    if (lastI < m && lastJ < n) {
      opcodes.push({ tag: 'replace', i1: lastI, i2: m, j1: lastJ, j2: n });
    } else if (lastI < m) {
      opcodes.push({ tag: 'delete', i1: lastI, i2: m, j1: lastJ, j2: lastJ });
    } else {
      opcodes.push({ tag: 'insert', i1: lastI, i2: lastI, j1: lastJ, j2: n });
    }
  }

  // Convert opcodes to TextChange array (positions relative to original text)
  const changes: TextChange[] = [];
  for (const op of opcodes) {
    if (op.tag === 'equal') continue;

    const oldTexts = origWords.slice(op.i1, op.i2).map(w => w.text);
    const newTexts = propWords.slice(op.j1, op.j2).map(w => w.text);

    const start = op.i1 < origWords.length ? origWords[op.i1].pos : original.length;
    const end = op.i2 > 0 && op.i2 <= origWords.length
      ? origWords[op.i2 - 1].pos + origWords[op.i2 - 1].text.length
      : start;

    changes.push({
      start,
      end,
      oldText: oldTexts.join(' '),
      newText: newTexts.join(' '),
    });
  }

  return changes;
};

/**
 * Gets the display name for amendment type
 */
export const getAmendmentTypeLabel = (type: AmendmentType): string => {
  switch (type) {
    case 'modification':
      return 'Modification';
    case 'suppression':
      return 'Suppression';
    case 'addition':
      return 'Addition';
    default:
      return type;
  }
};

/**
 * Gets the display name for structure level
 */
export const getStructureLevelLabel = (level: string): string => {
  switch (level) {
    case 'recital':
      return 'Recital';
    case 'article':
      return 'Article';
    case 'article-title':
      return 'Article Title';
    case 'point':
      return 'Point';
    case 'paragraph':
      return 'Paragraph';
    case 'subparagraph':
      return 'Subparagraph';
    default:
      return level;
  }
};

/**
 * Validates position reference format
 * e.g., "Recital 15", "Article 3", "Article 3, point 2, paragraph (a)"
 */
export const validatePositionReference = (position: string): boolean => {
  const patterns = [
    /^Recital \d+$/, // "Recital 15"
    /^Article \d+$/, // "Article 3"
    /^Article \d+, point \d+$/, // "Article 3, point 2"
    /^Article \d+, point \d+, paragraph \([a-z]\)$/, // "Article 3, point 2, paragraph (a)"
    /^Article \d+, point \d+, paragraph \([a-z]\), subparagraph \([ivxlcdm]+\)$/, // Full nested
  ];

  return patterns.some((pattern) => pattern.test(position));
};
