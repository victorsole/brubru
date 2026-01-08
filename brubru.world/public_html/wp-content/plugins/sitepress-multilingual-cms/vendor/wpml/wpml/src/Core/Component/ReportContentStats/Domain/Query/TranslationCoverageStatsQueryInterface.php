<?php

namespace WPML\Core\Component\ReportContentStats\Domain\Query;

use WPML\Core\Component\ReportContentStats\Domain\TranslationCoverageStats;

interface TranslationCoverageStatsQueryInterface {


  /**
   * @param string $defaultLanguageCode
   * @param string $postTypeName
   *
   * @return TranslationCoverageStats[]
   */
  public function get( string $defaultLanguageCode, string $postTypeName ): array;


}
