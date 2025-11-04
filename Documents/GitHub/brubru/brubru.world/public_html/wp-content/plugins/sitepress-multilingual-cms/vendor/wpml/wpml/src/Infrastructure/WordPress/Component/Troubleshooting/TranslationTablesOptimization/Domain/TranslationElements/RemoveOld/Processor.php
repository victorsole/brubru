<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\RemoveOld;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\ProcessorInterface;

/**
 * @implements ProcessorInterface<array{rid: int}>
 */
class Processor implements ProcessorInterface {

  /** @var \wpdb */
  private $wpdb;


  /**
   * @param \wpdb $wpdb
   */
  public function __construct( $wpdb ) {
    $this->wpdb = $wpdb;
  }


  /**
   * @param array<array{rid: int}> $records
   *
   * @return int[]
   */
  public function process( array $records ): array {
    $processed = [];

    foreach ( $records as $record ) {
      $sql = "
        DELETE t
        FROM {$this->wpdb->prefix}icl_translate t
        INNER JOIN (
          SELECT job_id
          FROM {$this->wpdb->prefix}icl_translate_job
          WHERE rid = %d
            AND job_id < (
              SELECT MAX(job_id)
              FROM {$this->wpdb->prefix}icl_translate_job
              WHERE rid = %d AND translated = 1
            )
        ) to_delete ON t.job_id = to_delete.job_id
      ";

      // @phpstan-ignore-next-line Parameter #1 $query of method wpdb::prepare() expects literal-string, string given.
      $sql = $this->wpdb->prepare( $sql, $record['rid'], $record['rid'] );
      /** @var string $sql */
      $this->wpdb->query( $sql );
      $processed[] = $record['rid'];
    }

    return $processed;
  }


}
