<?php

namespace WPML\Legacy\Component\ReportContentStats\Application\Hook;

use WPML\Core\SharedKernel\Component\Post\Application\Hook\PostTypeFilterInterface;

class ContentStatsTranslatableTypesFilter implements PostTypeFilterInterface {

  const NAME = 'wpml_tm_dashboard_translatable_types';


  /**
   * @param array<string, mixed> $postTypes
   *
   * @return array<string, mixed>
   */
  public function filter( array $postTypes ) {
    if ( isset( $postTypes['attachment'] ) ) {
      unset( $postTypes['attachment'] );
    }

    return apply_filters( self::NAME, $postTypes );
  }


}
