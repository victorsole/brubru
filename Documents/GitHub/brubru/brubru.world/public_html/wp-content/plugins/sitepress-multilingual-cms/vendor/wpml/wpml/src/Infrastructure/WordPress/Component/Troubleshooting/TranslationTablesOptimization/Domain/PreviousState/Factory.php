<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateRepositoryInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service\MigrationStatus\MigrationStatusService;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\CompletedRecordsStorageInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\ProcessorInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\QueryInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState\Factory as PreviousStateFactory;
use WPML\Core\Port\Persistence\DatabaseSchemaInfoInterface;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;

class Factory implements PreviousStateFactory {

  /** @var DatabaseSchemaInfoInterface */
  private $databaseSchemaInfo;

  /** @var QueryHandlerInterface<int, array{translationId: int, previousState: string}[]> */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPrepare;

  /** @var PreviousStateRepositoryInterface */
  private $repository;

  /** @var DataCompressInterface */
  private $dataCompress;

  /** @var \wpdb */
  private $wpdb;

  /** @var MigrationStatusService  */
  private $migrationStatusService;


  /**
   * @param QueryHandlerInterface<int, array{translationId: int, previousState: string}[]> $queryHandler
   * @param \wpdb $wpdb
   */
  public function __construct(
    DatabaseSchemaInfoInterface $databaseSchemaInfo,
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare,
    $wpdb,
    PreviousStateRepositoryInterface $repository,
    DataCompressInterface $dataCompress,
    MigrationStatusService $migrationStatusService
  ) {
    $this->databaseSchemaInfo = $databaseSchemaInfo;
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
    $this->wpdb = $wpdb;
    $this->repository   = $repository;
    $this->dataCompress = $dataCompress;
    $this->migrationStatusService = $migrationStatusService;
  }


  public function createQuery(): QueryInterface {
    return new Query(
      $this->queryHandler,
      $this->queryPrepare
    );
  }


  public function createCompletedRecordsStorage(): CompletedRecordsStorageInterface {
    return new CompletedRecordsStorage(
      $this->wpdb,
      $this->databaseSchemaInfo
    );
  }


  /**
   * @return ProcessorInterface<array{translationId: int, previousState: string}>
   * @psalm-suppress ImplementedReturnTypeMismatch
   */
  public function createProcessor(): ProcessorInterface {
    return new Processor(
      $this->repository,
      $this->dataCompress
    );
  }


  public function createMarkAsCompletedFunction(): callable {
    return [$this->migrationStatusService, 'markPrevStateCompleted'];
  }


}
