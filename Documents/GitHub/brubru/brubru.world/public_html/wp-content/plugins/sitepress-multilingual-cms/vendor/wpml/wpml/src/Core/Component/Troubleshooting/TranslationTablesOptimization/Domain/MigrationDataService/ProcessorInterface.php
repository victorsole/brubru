<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService;

/**
 * @template T
 */
interface ProcessorInterface {


  /**
   * @param T[] $records
   *
   * @return int[] Ids of processed records
   */
  public function process( array $records ): array;


}
