<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

use WPML\PHP\Exception\InvalidArgumentException;

class Provider {

  /** @var ProviderInterface[] */
  private $providers = [];


  /**
   * @param ProviderInterface[] $providers
   */
  public function __construct( $providers ) {
    $this->providers = $providers;
  }


  /**
   * @param int $id
   * @param string $type
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getByIdAndTypeForLangs( $id, $type, $langs, $freshTranslation = false ) {
    foreach ( $this->providers as $provider ) {
      if ( $item = $provider->getByIdAndTypeForLangs( $id, $type, $langs, $freshTranslation ) ) {
        return $item;
      }
    }

    throw new InvalidArgumentException(
      sprintf(
        'Item with id %d and type %s not found',
        $id,
        $type
      )
    );
  }


}
