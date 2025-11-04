<?php

namespace WPML\Core\SharedKernel\Component\Server\Domain\Service;

/**
 * Class ByteSizeConverter
 *
 * Utility service for  size conversions and operations.
 * This class provides methods to convert memory strings (like '128M') to bytes
 * and perform other memory-related operations.
 *
 * @package WPML\Core\SharedKernel\Component\Server\Domain\Service
 */
class ByteSizeConverter {


  /**
   * Converts a string (like '128M') to bytes.
   * If the value is invalid, returns 0
   *
   * @param string|int $val The memory value with optional unit (K, M, G)
   *
   * @return int The value in bytes
   */
  public function toBytes( $val ) {
    $val = trim( (string) $val );

    $exponents = array(
      'k' => 1,
      'm' => 2,
      'g' => 3,
    );

    $last = strtolower( substr( $val, - 1 ) );

    if ( ! is_numeric( $last ) ) {
      $val = (int) substr( $val, 0, - 1 );

      if ( array_key_exists( $last, $exponents ) ) {
        $val *= pow( 1024, $exponents[ $last ] );
      }
    } else {
      $val = (int) $val;
    }

    return (int) $val;
  }


}
