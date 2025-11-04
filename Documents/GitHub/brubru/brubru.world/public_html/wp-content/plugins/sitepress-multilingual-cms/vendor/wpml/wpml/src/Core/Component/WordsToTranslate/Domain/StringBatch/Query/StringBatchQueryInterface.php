<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Query;

use WPML\PHP\Exception\InvalidItemIdException;

interface StringBatchQueryInterface {


  /**
   * @param int $id
   *
   * @return int[]
   *
   * @throws InvalidItemIdException
   */
  public function getStringsIdsById( $id );


}
