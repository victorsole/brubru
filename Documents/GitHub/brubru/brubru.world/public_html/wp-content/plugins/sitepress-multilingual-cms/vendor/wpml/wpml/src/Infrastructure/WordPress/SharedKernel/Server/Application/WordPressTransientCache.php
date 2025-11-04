<?php

namespace WPML\Infrastructure\WordPress\SharedKernel\Server\Application;

use WPML\Core\SharedKernel\Component\Server\Domain\CacheInterface;

class WordPressTransientCache implements CacheInterface {


  public function get( $key ) {
    return get_transient( $key );
  }


  public function set( $key, $value, int $expiration = 0 ) {
    return set_transient( $key, $value, $expiration );
  }


  public function delete( $key ): bool {
    return delete_transient( $key );
  }


}
