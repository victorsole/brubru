<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringBatch;

use WPML\Core\Component\WordsToTranslate\Domain\Item;

class StringBatch extends Item {

  /** @var Item[] */
  private $strings;


  /**
   * StringBatch constructor.
   *
   * @param int    $id
   * @param string $sourceLang
   * @param Item[] $strings
   */
  public function __construct(
    $id,
    $sourceLang,
    $strings
  ) {
    parent::__construct( $id, 'stringBatch', $sourceLang );
    $this->strings = $strings;
  }


  /** @return Item[] */
  public function getStrings() {
    return $this->strings;
  }


  /**
   * @param ?string $langCode
   *
   * @return int
   */
  public function getWordsToTranslate( $langCode = null ) {
    $wordsToTranslate = 0;

    foreach ( $this->strings as $string ) {
      $wordsToTranslate += $string->getWordsToTranslate( $langCode );
    }

    return $wordsToTranslate;
  }


}
