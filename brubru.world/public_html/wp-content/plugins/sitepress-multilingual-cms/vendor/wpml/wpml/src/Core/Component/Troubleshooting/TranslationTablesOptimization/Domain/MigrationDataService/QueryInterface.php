<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService;

interface QueryInterface {


  public function countRemaining(): int;


  /**
   * @param int $limit
   *
   * @return mixed[]
   */
  public function getRemaining( int $limit ): array;


}
