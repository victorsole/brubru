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
 * Detects changes between original and proposed text
 * Returns array of TextChange objects
 */
export const detectChanges = (original: string, proposed: string): TextChange[] => {
  // Simple word-based diff algorithm
  const originalWords = original.split(/(\s+)/);
  const proposedWords = proposed.split(/(\s+)/);

  const changes: TextChange[] = [];
  let originalIndex = 0;
  let proposedIndex = 0;

  // Find differences (simplified - a full implementation would use a proper diff algorithm)
  for (let i = 0; i < Math.max(originalWords.length, proposedWords.length); i++) {
    const origWord = originalWords[i];
    const propWord = proposedWords[i];

    if (origWord !== propWord) {
      const start = originalIndex;
      const end = originalIndex + (origWord?.length || 0);

      changes.push({
        start,
        end,
        oldText: origWord || '',
        newText: propWord || '',
      });
    }

    originalIndex += origWord?.length || 0;
    proposedIndex += propWord?.length || 0;
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
