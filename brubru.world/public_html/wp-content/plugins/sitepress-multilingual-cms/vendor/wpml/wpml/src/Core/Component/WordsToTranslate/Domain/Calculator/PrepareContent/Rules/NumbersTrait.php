<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

trait NumbersTrait {


  /**
   * @param string $text
   *
   * @return string
   */
  private function removeStandaloneNumbers( $text ) {
    // Remove standalone numbers.
    return preg_replace( '/\b\d+\b/u', '', $text ) ?? '';
  }


}
