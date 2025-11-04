<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\PHP\Exception\InvalidItemIdException;

interface StringPackageQueryInterface {


  /**
   * @param int $id
   *
   * @return Item
   *
   * @throws InvalidItemIdException
   */
  public function getById( $id );


}
