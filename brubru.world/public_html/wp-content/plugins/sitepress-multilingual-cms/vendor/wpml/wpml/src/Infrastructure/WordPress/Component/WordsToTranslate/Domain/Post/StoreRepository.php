<?php

namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Post;

use WPML\Core\Component\WordsToTranslate\Domain\Post\Post;
use WPML\Core\Component\WordsToTranslate\Domain\Post\StoreRepositoryInterface;

class StoreRepository implements StoreRepositoryInterface {


  public function save( Post $post ) {
    // Implement cache.
  }


  public function get( $idPost ) {
    // Implement cache.
    return null;
  }


}
