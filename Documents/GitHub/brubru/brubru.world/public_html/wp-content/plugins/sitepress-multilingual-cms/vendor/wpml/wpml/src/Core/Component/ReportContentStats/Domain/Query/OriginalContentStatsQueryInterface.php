<?php

namespace WPML\Core\Component\ReportContentStats\Domain\Query;

use WPML\Core\Component\ReportContentStats\Domain\OriginalContentStats;

interface OriginalContentStatsQueryInterface {


  /**
   * @param string $defaultLanguageCode
   * @param string $postTypeName
   *
   * @return OriginalContentStats|null
   */
  public function get( string $defaultLanguageCode, string $postTypeName );


}
