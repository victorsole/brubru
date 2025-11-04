<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

trait PunctuationAndSpaceTrait {


  /**
   * @param string $text
   *
   * @return string
   */
  protected function removePunctuationAndSpaces( $text ) {
    return preg_replace( "/[^\p{L}\p{N}]/u", '', $text ) ?? '';
  }


  /**
   * @param string $text
   *
   * @return string
   */
  protected function replacePunctuationExceptApostrophesBySpace( $text ) {
    // Normalizesmart apostrophes.
    $text = str_replace( ["’", "`"], "'", $text );

    // Remove standalone apostrophes " ' ".
    $text = str_replace( " ' ", " ", $text );

    // Following would remove all punctuation except apostrophes and spaces.
    // return preg_replace( "/[^\p{L}\p{N}'\s]/u", ' ', $text ) ?? '';

    // BUT WPML must mimic ATE behavior, which does only remove a couple of signs.
    return preg_replace( "/[\s.,?!\/\\\\*\-_\+%$]+/u", ' ', $text ) ?? '';
  }


}
