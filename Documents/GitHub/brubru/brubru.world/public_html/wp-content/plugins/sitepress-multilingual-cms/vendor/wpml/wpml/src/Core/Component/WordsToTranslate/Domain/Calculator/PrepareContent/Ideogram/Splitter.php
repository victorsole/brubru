<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Ideogram;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\SplitterInterface;

class Splitter implements SplitterInterface {


  public function stringToArray( string $content ) {
    // Split string into individual UTF-8 characters
    return preg_split( '//u', $content, -1, PREG_SPLIT_NO_EMPTY ) ?: [];
  }


}
