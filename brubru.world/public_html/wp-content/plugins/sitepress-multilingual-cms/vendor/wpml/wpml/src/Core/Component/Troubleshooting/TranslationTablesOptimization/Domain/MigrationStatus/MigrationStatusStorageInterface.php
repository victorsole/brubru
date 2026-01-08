<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus;

interface MigrationStatusStorageInterface {


  public function read(): MigrationStatus;


  /**
   * @param MigrationStatus $migrationStatus
   *
   * @return void
   */
  public function write( MigrationStatus $migrationStatus );


}
