<?php

namespace WPML\Core\Component\Translation\Domain\PreviousState;

/**
 * @phpstan-import-type   PreviousStateData from \WPML\Core\Component\Translation\Domain\PreviousState\PreviousState
 */
interface DataCompressInterface {


  /**
   * @param array<string, mixed> $data
   *
   * @return string
   */
  public function compress( array $data ): string;


  /**
   * @param string $data
   *
   * @return PreviousStateData
   */
  public function decompress( string $data ): array;


}
