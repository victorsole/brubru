<?php

namespace WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface;

/**
 * @phpstan-import-type   PreviousStateData from \WPML\Core\Component\Translation\Domain\PreviousState\PreviousState
 *
 */
class OnlyDataSerialization implements DataCompressInterface {


  /**
   * @inheritDoc
   */
  public function compress( array $data ): string {
    return serialize( $data );
  }


  /**
   * @inheritDoc
   */
  public function decompress( string $data ): array {
    if ( empty( $data ) ) {
      return [];
    }

    $unserialized = @unserialize( $data );
    if ( is_array( $unserialized ) ) {
      return $unserialized;
    }

    return [];
  }


}
