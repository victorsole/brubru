<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

trait NinjaFormFieldsTrait {


  /**
   * @param string $text
   *
   * @return string
   */
  protected function removeNinjaFormFields( $text ) {
    return preg_replace( '/\{([a-z0-9\-_]*:.*|all_fields_table|fields_table)\}/uiU', '', $text ) ?? '';
  }


}
