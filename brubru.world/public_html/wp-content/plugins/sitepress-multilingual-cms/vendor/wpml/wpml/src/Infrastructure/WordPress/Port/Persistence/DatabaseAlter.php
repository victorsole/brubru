<?php

namespace WPML\Infrastructure\WordPress\Port\Persistence;

use WPML\Core\Port\Persistence\DatabaseAlterInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryPrepareInterface;
use WPML\PHP\Exception\InvalidArgumentException;


class DatabaseAlter implements DatabaseAlterInterface {

  /** @var \wpdb $wpdb */
  private $wpdb;

  /** @var QueryPrepareInterface $queryPrepare */
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
  public function addIndex( string $table, $fields, string $name = null ) {
    // Validate the fields.
    if ( empty( $fields ) ) {
      throw new InvalidArgumentException( 'No fields provided for index creation.' );
    }

    $fields = ! is_array( $fields ) ? [ $fields ] : $fields;
    foreach ( $fields as &$field ) {
      /** @psalm-suppress DocblockTypeContradiction */
      if ( empty( $field ) || ! is_string( $field ) ) {
        throw new InvalidArgumentException( 'Field names must be a non-empty string.' );
      }
      $field = $this->queryPrepare->escString( $field );
    }

    /** @var string $name */
    $name = $name ? $this->queryPrepare->escString( $name ) : $fields[0];

    /** @var string $table */
    $table = $this->wpdb->prefix . $this->queryPrepare->escString( $table );

    // Check if the index already exists.
    $indexExists = $this->wpdb->get_results(
      "SHOW INDEX FROM `$table` WHERE Key_name = '$name'"
    );

    if ( $indexExists ) {
      return true;
    }

    // Create the index.
    $this->wpdb->query(
      "ALTER TABLE `$table` ADD INDEX `$name` ( `" . implode( '`, `', $fields ) . "` )"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return true;
  }


  /**
   * @inheritDoc
   */
  public function addColumn( string $table, string $column, $type, $default = null ) {
    $column = $this->queryPrepare->escString( $column );

    /** @var string $table */
    $table = $this->wpdb->prefix . $this->queryPrepare->escString( $table );

    // Check if the index already exists.
    $fieldExists = $this->wpdb->get_results(
      "SHOW COLUMNS FROM `$table` LIKE '$column'"
    );

    if ( $fieldExists ) {
      return true;
    }

    $default = $default !== null
      ? "DEFAULT $default"
      : 'NULL';

    // Add the column.
    $this->wpdb->query(
      "ALTER TABLE `$table` ADD $column $type $default"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return true;
  }


  /**
   * @inheritDoc
   */
  public function dropColumn( string $table, string $column ) {
    if ( empty( $table ) || empty( $column ) ) {
      throw new InvalidArgumentException( 'Table and column names must be non-empty strings.' );
    }

    $table  = $this->wpdb->prefix . $this->queryPrepare->escString( $table );
    $column = $this->queryPrepare->escString( $column );

    // Check if the column exists
    $columnExists = $this->wpdb->get_results(
      "SHOW COLUMNS FROM `$table` LIKE '$column'"
    );

    if ( ! $columnExists ) {
      return true;
    }

    // Drop the column
    $this->wpdb->query(
      "ALTER TABLE `$table` DROP COLUMN `$column`"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return true;
  }


  /**
   * @inheritDoc
   */
  public function truncateColumn( string $table, string $column ) {
    if ( empty( $table ) || empty( $column ) ) {
      throw new InvalidArgumentException( 'Table and column names must be non-empty strings.' );
    }

    $table  = $this->wpdb->prefix . $this->queryPrepare->escString( $table );
    $column = $this->queryPrepare->escString( $column );

    // Truncate the column by setting all values to NULL
    $this->wpdb->query(
      "UPDATE `$table` SET `$column` = NULL"
    );

    if ( $this->wpdb->last_error ) {
      throw new DatabaseErrorException( $this->wpdb->last_error );
    }

    return true;
  }


}
