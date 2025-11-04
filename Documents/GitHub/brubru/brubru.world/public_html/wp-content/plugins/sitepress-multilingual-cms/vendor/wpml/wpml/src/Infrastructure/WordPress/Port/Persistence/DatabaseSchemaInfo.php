<?php

namespace WPML\Infrastructure\WordPress\Port\Persistence;

use WPML\Core\Port\Persistence\DatabaseSchemaInfoInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryPrepareInterface;
use WPML\PHP\Exception\InvalidArgumentException;

class DatabaseSchemaInfo implements DatabaseSchemaInfoInterface {

  /** @var \wpdb */
  private $wpdb;

  /** @var QueryPrepareInterface */
  private $queryPrepare;


  /**
   * @param \wpdb                 $wpdb Type defined here to allow injecting the global.
   * @param QueryPrepareInterface $queryPrepare
   */
  public function __construct( $wpdb, QueryPrepareInterface $queryPrepare ) {
    $this->wpdb         = $wpdb;
    $this->queryPrepare = $queryPrepare;
  }


  /**
   * @inheritDoc
   */
  public function doesColumnExist( string $table, string $column ): bool {
    if ( empty( $table ) || empty( $column ) ) {
      throw new InvalidArgumentException( 'Table and column names must be non-empty strings.' );
    }

    $table  = $this->wpdb->prefix . $this->queryPrepare->escString( $table );
    $column = $this->queryPrepare->escString( $column );

    $result = $this->wpdb->get_results(
      "SHOW COLUMNS FROM `$table` LIKE '$column'"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return ! empty( $result );
  }


  /**
   * @inheritDoc
   */
  public function doesTableExist( string $table ): bool {
    if ( empty( $table ) ) {
      throw new InvalidArgumentException( 'Table name must be a non-empty string.' );
    }

    $table = $this->wpdb->prefix . $this->queryPrepare->escString( $table );

    $result = $this->wpdb->get_results(
      "SHOW TABLES LIKE '$table'"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return ! empty( $result );
  }


}
