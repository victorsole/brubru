<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\Factory;

/**
 * @template T
 */
final class MigrateDataService {

  /** @var Factory */
  private $factory;


  public function __construct( Factory $factory ) {
    $this->factory = $factory;
  }


  /**
   * Initializes the compression process and returns the total number of elements to process
   *
   * @return int Total number of elements that need compression
   */
  public function initProcessAndGetTotalElements(): int {
    $this->factory->createCompletedRecordsStorage()->create();

    return $this->factory->createQuery()->countRemaining();
  }


  /**
   * Processes a batch of elements for compression
   *
   * @param int $numberOfElementsToProcess Number of elements to process in this batch
   *
   * @return void
   */
  public function run( int $numberOfElementsToProcess ) {
    $records      = $this->factory->createQuery()->getRemaining( $numberOfElementsToProcess );
    $processedIds = $this->factory->createProcessor()->process( $records );
    $this->factory->createCompletedRecordsStorage()->markAsCompleted( $processedIds );
  }


  public function countRemaining(): int {
    return $this->factory->createQuery()->countRemaining();
  }


  /**
   * Cleans up after the compression process
   *
   * @return void
   */
  public function finalize() {
    $this->factory->createCompletedRecordsStorage()->delete();
    call_user_func( $this->factory->createMarkAsCompletedFunction() );
  }


}
