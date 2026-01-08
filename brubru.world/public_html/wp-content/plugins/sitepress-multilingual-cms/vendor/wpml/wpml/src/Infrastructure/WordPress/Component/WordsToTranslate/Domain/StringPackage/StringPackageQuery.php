<?php
// phpcs:ignoreFile Squiz.NamingConventions.ValidVariableName.MemberNotCamelCaps
namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\StringPackage;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\StringPackageQueryInterface;
use WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\SourceLangQueryTrait;
use WPML\PHP\Exception\InvalidItemIdException;

class StringPackageQuery implements StringPackageQueryInterface {
  use SourceLangQueryTrait;


  public function getById( $id ) {
    $wpdb = $GLOBALS['wpdb'];

    $stringPackageRaw = $wpdb->get_row(
      $wpdb->prepare(
        "SELECT * FROM {$wpdb->prefix}icl_string_packages WHERE ID = %d",
        $id
      )
    );

    if ( ! $stringPackageRaw ) {
      throw new InvalidItemIdException(
        sprintf( 'String Package with ID %d not found', $id )
      );
    }

    $type = 'package_' . $stringPackageRaw->kind_slug;

    $stringPackage = new Item(
      $stringPackageRaw->ID,
      $type,
      $this->getSourceLang( (int) $stringPackageRaw->ID, $type )
    );

    return $stringPackage;
  }


}
