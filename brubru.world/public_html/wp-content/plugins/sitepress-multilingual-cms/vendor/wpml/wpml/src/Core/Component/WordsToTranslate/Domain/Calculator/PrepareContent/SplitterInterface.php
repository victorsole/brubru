<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent;

interface SplitterInterface {


  /** @return string[] */
  public function stringToArray( string $content );


}
