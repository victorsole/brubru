<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;

interface JobQueryInterface {


  /** @return string */
  public function getContent( Item $stringPackage, string $lang );


  /**
   * @param int $idItem
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $idItem, $content );


}
