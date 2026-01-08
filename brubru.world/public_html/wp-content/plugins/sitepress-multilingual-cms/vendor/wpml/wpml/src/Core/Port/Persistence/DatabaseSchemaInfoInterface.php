<?php

namespace WPML\Core\Port\Persistence;

use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\PHP\Exception\InvalidArgumentException;

interface DatabaseSchemaInfoInterface {


  /**
   * @param string $table
   * @param string $column
   *
   * @return bool
   *
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function doesColumnExist( string $table, string $column ): bool;


  /**
   * @param string $table
   *
   * @return bool
   *
   * @throws DatabaseErrorException
   * @throws InvalidArgumentException
   */
  public function doesTableExist( string $table ): bool;


}
