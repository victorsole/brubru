<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Post\Post;
use WPML\PHP\Exception\InvalidItemIdException;

interface PostQueryInterface {


  /**
   * @param int $id
   *
   * @return Post
   *
   * @throws InvalidItemIdException
   */
  public function getById( $id );


}
