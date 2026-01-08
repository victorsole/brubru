<?php

namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Strings;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\StringQueryInterface;
use WPML\PHP\Exception\InvalidItemIdException;

class StringQuery implements StringQueryInterface {


  public function getById( $id ) {
    $wpdb = $GLOBALS['wpdb'];

    $stringRaw = $wpdb->get_row(
      $wpdb->prepare(
        "SELECT * FROM {$wpdb->prefix}icl_strings WHERE id = %d",
        $id
      )
    );

    if ( ! $stringRaw ) {
      throw new InvalidItemIdException( 'String not found' );
    }

    $string = new Item(
      $stringRaw->id,
      $stringRaw->type,
      $stringRaw->language
    );

    $string->setContent( $stringRaw->value );

    return $string;
  }


}
