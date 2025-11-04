<?php

namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\StringBatch;

use WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Query\StringBatchQueryInterface;

class StringBatchQuery implements StringBatchQueryInterface {


  public function getStringsIdsById( $id ) {
    $wpdb = $GLOBALS['wpdb'];

    $strings = $wpdb->get_col(
      $wpdb->prepare(
        "SELECT string_id
        FROM {$wpdb->prefix}icl_string_batches
        WHERE batch_id = %d",
        $id
      )
    );

    return $strings ?: [];
  }


}
