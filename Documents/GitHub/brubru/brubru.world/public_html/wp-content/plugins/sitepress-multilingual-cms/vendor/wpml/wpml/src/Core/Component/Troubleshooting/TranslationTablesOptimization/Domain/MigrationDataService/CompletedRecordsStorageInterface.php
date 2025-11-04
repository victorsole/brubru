<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService;

interface CompletedRecordsStorageInterface {


  /**
   * @return void
   */
  public function create();


  /**
   * @return void
   */
  public function delete();


  /**
   * @param int[] $recordIds
   *
   * @return void
   */
  public function markAsCompleted( array $recordIds );


}
