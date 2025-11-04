<?php

namespace WPML\Core\SharedKernel\Component\Server\Domain;

interface CacheInterface {


  /**
   * @param string $key
   *
   * @return mixed
   */
  public function get( $key );


  /**
   * @param string $key
   * @param mixed $value
   * @param int $expiration
   *
   * @return bool
   */
  public function set( $key, $value, int $expiration = 0 );


  /**
   * @param string $key
   *
   * @return bool
   */
  public function delete( $key ): bool;


}
