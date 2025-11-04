<?php

namespace WPML\Legacy\Component\WordsToTranslate\Domain\StringPackage;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\JobQueryInterface;
use WPML\Legacy\Component\WordsToTranslate\Domain\JobPackageTrait;


class JobQuery implements JobQueryInterface {
  use JobPackageTrait;

  /** @var array<int, mixed> */
  private $jobPackages = [];


  public function getContent( Item $stringPackage, string $lang ) {
    $jobPackage = $this->getJobPackage( $stringPackage, $lang );
    $jobPackage = $this->getTranslatableFields( $jobPackage );

    $content = '';

    foreach ( $jobPackage as $data ) {
      $content .= $content ? ' ' . $data : $data;
    }

    return $content;
  }


  /**
   * @param Item $stringPackage
   * @param string|null $lang
   *
   * @return mixed
   */
  private function getJobPackage( Item $stringPackage, $lang = null ) {
    $package = isset( $this->jobPackages[ $stringPackage->getId() ] )
      ? $this->jobPackages[ $stringPackage->getId() ]
      : false;

    if ( ! $package ) {
      $wpmlPackage = new \WPML_Package( $stringPackage->getId() );
      $this->wpmlElementTranslationPackage()
          ->do_action_before_creating_translation_package( $wpmlPackage );

      /** @var array<string, string>|false $package */
      $package = $this->wpmlElementTranslationPackage()
          ->create_translation_package( $wpmlPackage, true ) ?: false;

      $this->jobPackages[ $stringPackage->getId() ] = $package;
    }

    return $lang
      ? $this->wpmlElementTranslationPackage()
        ->filter_translation_package_for_lang(
          $package,
          $this->getElement( $stringPackage->getId() ),
          $lang
        )
      : $package;
  }


  public function useThisContentForItem( $idItem, $content ) {
    $data = [ 'contents' => [] ];

    foreach ( $content as $part ) {
      $data['contents'][ $part->getType() ] = [
        'translate' => 1,
        'data'   => $part->getContent(),
        'format' => $part->getFormat(),
      ];
    }

    $this->jobPackages[ $idItem ] = $data;
  }


  /**
   * @param int $id
   *
   * @return mixed
   */
  private function getElement( $id ) {
    $tm = $GLOBALS['iclTranslationManagement'] ?? null;

    if ( ! $tm ) {
      return null;
    }

    if (
      ! is_object( $tm )
        || ! method_exists( $tm, 'get_post' )
    ) {
      return null;
    }

    return $tm->get_post( $id, 'package' );
  }


}
