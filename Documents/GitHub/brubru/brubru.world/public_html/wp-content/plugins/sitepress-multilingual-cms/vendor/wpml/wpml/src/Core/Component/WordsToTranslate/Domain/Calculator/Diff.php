<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator;

class Diff {
  const DIFF_KEY_ADDED = '+';
  const DIFF_KEY_REMOVED = '-';


  /**
   * @param string $before
   * @param string $current
   *
   * @return array<int, string|array<string,string[]>>
   */
  public function diffStrings( string $before, string $current ) {
    return $this->diffArrays(
      preg_split( "/[\s]+/", $before ) ?: [],
      preg_split( "/[\s]+/", $current ) ?: []
    );
  }


  /**
   * Diff two arrays of strings.
   *
   * Input: $b: ['a', 'b', 'c', 'd', 'e'], $c: ['a', 'b', 'x', 'e']
   * Output:
   *  [
   *    '0' => 'a',
   *    '1' => 'b',
   *    '2' => [
   *      '-' => ['c'],
   *      '+' => ['x'],
   *    ],
   *    '3' => [
   *      '-' => ['d'],
   *      '+' => [],
   *    ],
   *    '4' => 'e',
   *  ]
   *
   * NOTE: This method is optimized for performance and not readability.
   *       See flow chart on ticket wpmldev-4871 for better understanding.
   *
   * phpcs:disable Generic.Metrics.CyclomaticComplexity.TooHigh
   *
   * @param string[] $b Before content.
   * @param string[] $c Current content.
   * @param int $bStart
   * @param ?int $bEnd
   * @param int $cStart
   * @param ?int $cEnd
   * @param ?array<string,int[]> $cValuesAsIndex
   *
   * @return array<int, string|array<string,string[]>>
   */
  public function diffArrays(
    $b,
    $c,
    // Following parameters are for performance reasons on recursion calls.
    $bStart = 0,
    $bEnd = null,
    $cStart = 0,
    $cEnd = null,
    $cValuesAsIndex = null
  ) {
    $bEnd = $bEnd ?? count( $b );
    $cEnd = $cEnd ?? count( $c );

    if ( $bStart >= $bEnd && $cStart >= $cEnd ) {
      // Nothing to check.
      return [];
    }

    if ( $cValuesAsIndex === null ) {
      // Flip the array to get the indexes of the values.
      $cValuesAsIndex = [];
      foreach ( $c as $index => $value ) {
        // Must be multidimensional as the same value can appear multiple times.
        $cValuesAsIndex[ $value ][] = $index;
      }
    }

    $maxMatchingWordsInARow = 0;
    $maxMatchAStart = $bStart;
    $maxMatchBstart = $cStart;

    /** @var array<int, array<int, int>> $matches */
    $matches = [];

    // Loop $b array to find the longest match (words in a row) in the $b array.
    for ( $bIndex = $bStart; $bIndex < $bEnd; $bIndex++ ) {
      $value = $b[ $bIndex ];

      // Check if the value is in the $b array.
      /** @var int[] $matchIndexes */
      $matchIndexes = $cValuesAsIndex[ $value ] ?? [];

      foreach ( $matchIndexes as $matchIndex ) {
        // The $b (before) value is also in the $c (current) array.

        if ( $matchIndex < $cStart || $matchIndex >= $cEnd ) {
          // The match is outside the current (recursion) range.
          continue;
        }

        $prevMatch = $matches[$bIndex - 1][ $matchIndex - 1 ] ?? 0;

        // Set current match count (count of words in a row).
        $matches[$bIndex][ $matchIndex ] = $prevMatch + 1;

        // Check if the current words in a row is greater than the max.
        if ( $matches[$bIndex][ $matchIndex ] > $maxMatchingWordsInARow ) {
          $maxMatchingWordsInARow = $matches[$bIndex][ $matchIndex ];
          $maxMatchAStart = $bIndex + 1 - $maxMatchingWordsInARow;
          $maxMatchBstart = $matchIndex + 1 - $maxMatchingWordsInARow;
        }
      }
    }

    if ( $maxMatchingWordsInARow === 0 ) {
      // No matches at all.
      // Current range of $b was removed and current rage of $b was added.
      return [
        [
          self::DIFF_KEY_REMOVED => array_slice( $b, $bStart, $bEnd - $bStart ),
          self::DIFF_KEY_ADDED => array_slice( $c, $cStart, $cEnd - $cStart ),
        ],
      ];
    }

    // There are matches, but we still need to check the parts left and right of the matched words.
    return array_merge(
      // Left: Everything before the $maxMatchingWordsInARow.
      $this->diffArrays(
        $b,
        $c,
        $bStart,
        $maxMatchAStart,
        $cStart,
        $maxMatchBstart,
        $cValuesAsIndex
      ),
      // ---
      // Middle: The matching words.
      array_slice( $c, $maxMatchBstart, $maxMatchingWordsInARow ),
      // ---
      // Right: Everything after the $maxMatchingWordsInARow.
      $this->diffArrays(
        $b,
        $c,
        $maxMatchAStart + $maxMatchingWordsInARow,
        $bEnd,
        $maxMatchBstart + $maxMatchingWordsInARow,
        $cEnd,
        $cValuesAsIndex
      )
    );
  }


}
