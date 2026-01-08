<?php

namespace WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Query;

use WPML\Core\Component\ReportContentStats\Domain\OriginalContentStats;
use WPML\Core\Component\ReportContentStats\Domain\Query\OriginalContentStatsQueryInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;

/**
 * @phpstan-type OriginalContentStatsRow array{
 *   post_type: string,
 *   all_count: int,
 *   all_chars_count: int,
 * }
 */
class OriginalContentStatsQuery implements OriginalContentStatsQueryInterface {

  /** @phpstan-var QueryHandlerInterface<int, OriginalContentStatsRow> $queryHandler */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPreparer;


  /**
   * @phpstan-param QueryHandlerInterface<int, OriginalContentStatsRow> $queryHandler
   *
   * @param QueryPrepareInterface $queryPrepare
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare
  ) {
    $this->queryHandler  = $queryHandler;
    $this->queryPreparer = $queryPrepare;
  }


  /**
   * @param string $defaultLanguageCode
   * @param string $postTypeName
   *
   * @return OriginalContentStats|null
   */
  public function get( string $defaultLanguageCode, string $postTypeName ) {
    $sql = "
    SELECT p.post_type, 
           COUNT(p.ID) as all_count,
           SUM(
           CHAR_LENGTH(CONCAT(p.post_content, p.post_title, p.post_excerpt))
           ) as all_chars_count
    FROM {$this->queryPreparer->prefix()}icl_translations iclt
      INNER JOIN {$this->queryPreparer->prefix()}posts p
        ON iclt.element_id = p.ID
    WHERE p.post_status = 'publish'
      AND p.post_type = %s
      AND iclt.element_type = %s
      AND iclt.source_language_code IS NULL
      AND iclt.language_code = %s
    GROUP BY p.post_type;
    ";

    $sqlPrepared = $this->queryPreparer->prepare(
      $sql,
      $postTypeName,
      'post_' . $postTypeName,
      $defaultLanguageCode
    );

    try {
      $result = $this->queryHandler->queryOne( $sqlPrepared );

      if ( ! $result ) {
        return null;
      }
    } catch ( DatabaseErrorException $e ) {
      return null;
    }

    return new OriginalContentStats(
      $result['post_type'],
      $result['all_count'],
      $result['all_chars_count']
    );
  }


}
