<?php

namespace WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Repository;

use WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesToCalculateRepositoryInterface;
use WPML\Infrastructure\WordPress\Port\Persistence\Options;

class PostTypesToCalculateRepository implements
  PostTypesToCalculateRepositoryInterface {

  const OPTION_KEY = 'wpml-stats-calculate-post-types';

  /** @var Options */
  private $options;


  public function __construct( Options $options ) {
    $this->options = $options;
  }


  /**
   * @return string[]|null
   */
  public function get() {
    /** @var string[]|null $postTypes */
    $postTypes = $this->options->get( self::OPTION_KEY, null );

    return $postTypes;
  }


  /**
   * @param string[] $postTypes
   *
   * @return void
   */
  public function init( array $postTypes ) {
    $this->options->save( self::OPTION_KEY, $postTypes );
  }


  public function removePostType( string $postTypeName ) {
    $postTypes = $this->get();

    if ( ! $postTypes || ! in_array( $postTypeName, $postTypes ) ) {
      return;
    }

    $postTypeKey = array_search( $postTypeName, $postTypes );
    unset( $postTypes[ $postTypeKey ] );

    $this->options->save( self::OPTION_KEY, $postTypes );
  }


  public function delete() {
    $this->options->delete( self::OPTION_KEY );
  }


}
