<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Strings\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Item;

interface TranslationQueryInterface {


  /**
   * Returns the last translated original content (original = source language).
   *
   * @return string
   */
  public function getLastTranslatedOriginalContent( Item $string, string $lang );


}
