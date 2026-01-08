<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

trait UnicodeTrait {


  /**
   * @param string $text
   *
   * @return string
   */
  private function replaceUnicode( $text ) {
    // Remove UTF-8 BOM (EF BB BF)
    $text = preg_replace( '/^\xEF\xBB\xBF/', '', $text ) ?? '';

    // Remove UTF-16 BOM (FE FF or FF FE)
    $text = preg_replace( '/^\xFE\xFF|\xFF\xFE/', '', $text ) ?? '';

    // Replace non-breaking spaces (U+00A0) with normal space
    $text = str_replace( "\xC2\xA0", ' ', $text );

    // Remove other potential control characters except \n and \t
    $text = preg_replace( '/[\x00-\x09\x0B\x0C\x0E-\x1F\x7F]/u', '', $text ) ?? '';

    return $text;
  }


}
