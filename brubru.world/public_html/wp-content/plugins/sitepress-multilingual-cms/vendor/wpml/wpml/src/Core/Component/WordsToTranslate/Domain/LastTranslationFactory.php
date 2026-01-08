<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

class LastTranslationFactory {

  /** @var array<string, LastTranslation> */
  private $lastTranslations = [];


  /** @return LastTranslation */
  public function createForItem( Item $item, string $lang ) {
    $key = $item->getId() . $item->getType() . $lang;

    if ( ! isset( $this->lastTranslations[ $key ] ) ) {
      $this->lastTranslations[ $key ] = new LastTranslation( $lang );
    }

    return $this->lastTranslations[ $key ];
  }


}
