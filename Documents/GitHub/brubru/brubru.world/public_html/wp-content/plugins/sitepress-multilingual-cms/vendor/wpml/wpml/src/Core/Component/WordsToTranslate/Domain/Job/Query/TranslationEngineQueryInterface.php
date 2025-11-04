<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Job\Query;

use WPML\PHP\Exception\RuntimeException;

interface TranslationEngineQueryInterface {


  /**
   * Returns the cost per word for the given language code.
   *
   * @param string $langCode
   * @param ?string $sourceLang
   *
   * @return int|false The cost per word in cents, or false if the language does not support automatic translation.
   *
   * @throws RuntimeException The translation engine for the language is not available.
   */
  public function getCostsPerWordForLang( string $langCode, $sourceLang = null );


}
