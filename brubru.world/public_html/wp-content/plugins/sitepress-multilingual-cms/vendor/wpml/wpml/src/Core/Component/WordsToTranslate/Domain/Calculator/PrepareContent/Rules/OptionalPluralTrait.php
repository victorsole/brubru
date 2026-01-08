<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

trait OptionalPluralTrait {


  /**
   * @param string $text
   *
   * @return string
   */
  protected function removeOptionalPlural( $text ) {
    $patterns = [
        '/\((s|es|aux|er|e|и|y|ات)\)/uiU', // Parenthetical plural markers
        '/\/(i|che)/uiU', // Slash-based plural markers
    ];

    return preg_replace( $patterns, '$1', $text ) ?? '';
  }


}
