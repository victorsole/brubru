<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\Compress;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\QueryInterface;

class Query implements QueryInterface {

  /** @var \wpdb */
  private $wpdb;


  /**
   * @param \wpdb $wpdb
   */
  public function __construct( $wpdb ) {
    $this->wpdb = $wpdb;
  }


  public function countRemaining(): int {
    $translateTable = $this->wpdb->prefix . 'icl_translate';
    $tmpTable       = $this->wpdb->prefix . CompletedRecordsStorage::TMP_TABLE_NAME;

    /** @var string $sql */
    $sql = $this->wpdb->prepare(
      'SELECT COUNT(*)
      FROM %i t
      LEFT JOIN %i tc ON t.tid = tc.tid
      WHERE t.field_format = %s
      AND (tc.tid IS NULL OR tc.compressed = 0)',
      $translateTable,
      $tmpTable,
      'base64'
    );

    /** @var string|int|null $count */
    $count = $this->wpdb->get_var( $sql );

    return (int) $count;
  }


  /**
   * @return array<object{tid: int, fieldData: string, fieldDataTranslated: string}>
   */
  public function getRemaining( int $limit ): array {
    $translateTable = $this->wpdb->prefix . 'icl_translate';
    $tmpTable       = $this->wpdb->prefix . CompletedRecordsStorage::TMP_TABLE_NAME;

    /** @var string $sql */
    $sql = $this->wpdb->prepare(
      'SELECT t.tid, t.field_data as fieldData, t.field_data_translated as fieldDataTranslated
      FROM %i t
      LEFT JOIN %i tc ON t.tid = tc.tid
      WHERE t.field_format = %s
      AND (tc.tid IS NULL OR tc.compressed = 0)
      LIMIT %d',
      $translateTable,
      $tmpTable,
      'base64',
      $limit
    );

    /** @var array<object{tid: int, fieldData: string, fieldDataTranslated: string}>|null $results */
    $results = $this->wpdb->get_results( $sql );

    return $results ?: [];
  }


}
