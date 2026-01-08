<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Letter;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\SplitterInterface;

class Splitter implements SplitterInterface {


  public function stringToArray( string $content ) {
    return preg_split( "/[\s]+/", trim( $content ) ) ?: [];
  }


}
