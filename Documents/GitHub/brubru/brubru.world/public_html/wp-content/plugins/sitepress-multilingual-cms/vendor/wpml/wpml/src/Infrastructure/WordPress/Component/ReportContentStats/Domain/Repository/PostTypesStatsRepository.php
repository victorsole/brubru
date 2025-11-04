<?php

namespace WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Repository;

use WPML\Core\Component\ReportContentStats\Domain\ContentStatsReport;
use WPML\Core\Component\ReportContentStats\Domain\PostTypeStats;
use WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesStatsRepositoryInterface;
use WPML\Infrastructure\WordPress\Port\Persistence\Options;

/**
 * @phpstan-import-type ContentStatsArray from ContentStatsReport
 */
class PostTypesStatsRepository implements PostTypesStatsRepositoryInterface {

  const OPTION_KEY = 'wpml-stats-post-types';

  /** @var Options */
  private $options;


  public function __construct( Options $options ) {
    $this->options = $options;
  }


  /**
   * @return PostTypeStats[]
   */
  public function get(): array {
    /** @var ContentStatsArray $postTypesStats */
    $postTypesStats = $this->options->get( self::OPTION_KEY, [] );

    $stats = [];

    foreach ( $postTypesStats as $postTypeId => $data ) {
      $stats[] = new PostTypeStats(
        $postTypeId,
        $data['postsCount'],
        $data['charactersCount'],
        $data['translationCoverage']
      );
    }

    return $stats;
  }


  /** @return void */
  public function update( PostTypeStats $postTypeStats ) {
    /** @phpstan-var ContentStatsArray $currentStats */
    $currentStats = $this->options->get( self::OPTION_KEY, [] );

    $currentStats[ $postTypeStats->getPostTypeId() ] = [
      'postsCount'          => $postTypeStats->getPostsCount(),
      'charactersCount'     => $postTypeStats->getCharactersCount(),
      'translationCoverage' => $postTypeStats->getTranslationCoverage(),
    ];

    $this->options->save( self::OPTION_KEY, $currentStats );
  }


  public function delete() {
    $this->options->delete( self::OPTION_KEY );
  }


}
