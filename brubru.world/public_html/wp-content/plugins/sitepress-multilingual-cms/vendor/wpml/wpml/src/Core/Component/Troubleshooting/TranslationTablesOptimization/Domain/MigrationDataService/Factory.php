<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService;

interface Factory {


  public function createQuery(): QueryInterface;


  public function createCompletedRecordsStorage(): CompletedRecordsStorageInterface;


  /**
   * @template T
   * @return ProcessorInterface<T>
   * @phpstan-ignore-next-line Template type T is not referenced in a parameter
   */
  public function createProcessor(): ProcessorInterface;


  public function createMarkAsCompletedFunction(): callable;


}
