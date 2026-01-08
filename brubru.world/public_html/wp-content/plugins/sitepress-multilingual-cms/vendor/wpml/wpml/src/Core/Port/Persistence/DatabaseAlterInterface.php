<?php

namespace WPML\Core\Port\Persistence;

use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\PHP\Exception\InvalidArgumentException;

interface DatabaseAlterInterface {
  const FIELD_TYPE_INT11_UNSIGNED = 'INT(11) UNSIGNED';


  /**
   * @param string          $table
   * @param string|string[] $fields
   * @parame string|null    $name   Optional. If not provided the first field name is used.
   *
   * @return bool
   *
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function addIndex( string $table, $fields, string $name = null );


  /**
   * @param string $table
   * @param string $column
   * @param self::FIELD_TYPE_* $type
   * @param string|int|float|null $default
   *
   * @return bool
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function addColumn( string $table, string $column, $type, $default = null );


  /**
   * @param string $table
   * @param string $column
   *
   * @return bool
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function dropColumn( string $table, string $column );


  /**
   * @param string $table
   * @param string $column
   *
   * @return bool
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function truncateColumn( string $table, string $column );


}
