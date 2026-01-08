<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\CompletedRecordsStorageInterface;
use WPML\Core\Port\Persistence\DatabaseSchemaInfoInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\PHP\Exception\InvalidArgumentException;

class CompletedRecordsStorage implements CompletedRecordsStorageInterface {

  /** @var \wpdb */
  private $wpdb;

  const TMP_TABLE_NAME = 'icl_translation_prevstate_processed';

  /** @var DatabaseSchemaInfoInterface */
  private $databaseSchemaInfo;


  /**
   * @param \wpdb $wpdb
   */
  public function __construct( $wpdb, DatabaseSchemaInfoInterface $databaseSchemaInfo ) {
    $this->wpdb               = $wpdb;
    $this->databaseSchemaInfo = $databaseSchemaInfo;
  }


  /**
   * @inheritDoc
   */
  public function create() {
    try {
      if ( ! $this->databaseSchemaInfo->doesTableExist( self::TMP_TABLE_NAME ) ) {
        $table = $this->wpdb->prefix . self::TMP_TABLE_NAME;

        $this->wpdb->query(
          "CREATE TABLE {$table} (
            translation_id BIGINT UNSIGNED NOT NULL,
            processed TINYINT(1) NOT NULL DEFAULT 0,
            PRIMARY KEY (translation_id)
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        );
      }
    } catch ( DatabaseErrorException $e ) {
      return;
    } catch ( InvalidArgumentException $e ) {
      return;
    }
  }


  /**
   * @inheritDoc
   */
  public function delete() {
    $this->wpdb->query( 'DROP TABLE IF EXISTS ' . $this->wpdb->prefix . self::TMP_TABLE_NAME );
  }


  /**
   * @inheritDoc
   */
  public function markAsCompleted( array $recordIds ) {
    if ( empty( $recordIds ) ) {
      return;
    }

    $values = [];
    foreach ( $recordIds as $translationId ) {
      $values[] = $this->wpdb->prepare( '(%d, 1)', $translationId );
    }

    $table = $this->wpdb->prefix . self::TMP_TABLE_NAME;
    /** @var string[] $values */
    $sql = "INSERT INTO {$table} (translation_id, processed)
      VALUES " . implode( ', ', $values ) . "
      ON DUPLICATE KEY UPDATE processed = 1";

    $this->wpdb->query( $sql );
  }


}
