<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

interface StoreRepositoryInterface {


  /**
   * @param Post $post
   * @return void
   */
  public function save( Post $post );


  /**
   * @param int $idPost
   * @return ?Post
   */
  public function get( $idPost );


}
