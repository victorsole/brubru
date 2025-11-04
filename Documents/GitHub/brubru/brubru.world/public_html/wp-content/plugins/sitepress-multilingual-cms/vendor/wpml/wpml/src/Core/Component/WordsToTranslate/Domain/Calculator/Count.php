<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator;

class Count {


  /**
  * Returns the number of words to translate in a given diff.
  * The user is only charged for added words.
  *
  * @param array<int, string|array<string,string[]>> $diff
  *
  * @return int
  */
  public function wordsToTranslate( $diff ) {
    $wordsToTranslate = 0;
    foreach ( $diff as $part ) {
      if ( isset( $part[ Diff::DIFF_KEY_ADDED ] ) ) {
        $wordsToTranslate += count( $part[ Diff::DIFF_KEY_ADDED ] );
      }
    }
    return $wordsToTranslate;
  }


}
