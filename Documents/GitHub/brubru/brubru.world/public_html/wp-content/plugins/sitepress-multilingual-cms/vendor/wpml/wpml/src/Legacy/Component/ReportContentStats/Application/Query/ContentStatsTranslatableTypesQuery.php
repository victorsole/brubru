<?php

namespace WPML\Legacy\Component\ReportContentStats\Application\Query;

use WPML\Core\Component\ReportContentStats\Application\Query\ContentStatsTranslatableTypesQueryInterface;
use WPML\Legacy\Component\Post\Application\Query\TranslatableTypesQuery;
use WPML\Legacy\Component\ReportContentStats\Application\Hook\ContentStatsTranslatableTypesFilter;

/**
 * @phpcs:disable Generic.CodeAnalysis.UselessOverridingMethod.Found
 */
class ContentStatsTranslatableTypesQuery
  extends TranslatableTypesQuery
  implements ContentStatsTranslatableTypesQueryInterface {


  public function __construct( \SitePress $sitepress, ContentStatsTranslatableTypesFilter $filter ) {
    parent::__construct( $sitepress, $filter );
  }


}
