<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Strings\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\PHP\Exception\InvalidItemIdException;

interface StringQueryInterface {


  /**
   * @param int $id
   *
   * @return Item
   *
   * @throws InvalidItemIdException
   */
  public function getById( $id );


}
