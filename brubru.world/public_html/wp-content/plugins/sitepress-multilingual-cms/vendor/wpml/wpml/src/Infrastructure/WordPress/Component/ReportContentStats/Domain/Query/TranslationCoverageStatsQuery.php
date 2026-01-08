<?php

namespace WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Query;

use WPML\Core\Component\ReportContentStats\Domain\Query\TranslationCoverageStatsQueryInterface;
use WPML\Core\Component\ReportContentStats\Domain\TranslationCoverageStats;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;

/**
 * @phpstan-type TranslationCoverageStatsRow array{
 *   post_type: string,
 *   language_code: string,
 *   translated_original_content_chars_count: int,
 *   translated_original_content_count: int,
 * }
 */
class TranslationCoverageStatsQuery implements TranslationCoverageStatsQueryInterface {

  /** @phpstan-var  QueryHandlerInterface<int, TranslationCoverageStatsRow> $queryHandler */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPrepare;


  /**
   * @phpstan-param  QueryHandlerInterface<int, TranslationCoverageStatsRow> $queryHandler
   *
   * @param QueryPrepareInterface $queryPrepare
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare
  ) {
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
  }


  /**
   * @param string $defaultLanguageCode
   * @param string $postTypeName
   *
   * @return TranslationCoverageStats[]
   */
  public function get( string $defaultLanguageCode, string $postTypeName ): array {
    $sql = "
    SELECT
    langs.code AS language_code,
    COUNT(icl1.element_id) AS translated_original_content_count,
    p.post_type as post_type,
    SUM(
    CHAR_LENGTH(CONCAT(p.post_content, p.post_title, p.post_excerpt))
    ) as translated_original_content_chars_count
    FROM {$this->queryPrepare->prefix()}icl_languages langs
      LEFT JOIN {$this->queryPrepare->prefix()}icl_translations icl1
        ON langs.code = icl1.language_code
             AND icl1.element_type = %s
      LEFT JOIN {$this->queryPrepare->prefix()}icl_translations icl2
        ON icl1.trid = icl2.trid
             AND icl2.source_language_code IS NULL
             AND icl2.element_type = %s
      LEFT JOIN {$this->queryPrepare->prefix()}posts p
        ON icl2.element_id = p.ID
             AND p.post_status = 'publish'
             AND p.post_type = %s
    WHERE p.post_type IS NOT NULL
      AND langs.active = 1
      AND langs.code != %s
    GROUP BY langs.code, p.post_type;
    ";

    $sqlPrepared = $this->queryPrepare->prepare(
      $sql,
      'post_' . $postTypeName,
      'post_' . $postTypeName,
      $postTypeName,
      $defaultLanguageCode
    );

    try {
      $results = $this->queryHandler->query( $sqlPrepared )->getResults();
    } catch ( DatabaseErrorException $e ) {
      return [];
    }

    return array_map(
      function ( array $row ) {
        return new TranslationCoverageStats(
          $row['post_type'],
          $row['language_code'],
          $row['translated_original_content_chars_count'],
          $row['translated_original_content_count']
        );
      },
      $results
    );
  }


}
