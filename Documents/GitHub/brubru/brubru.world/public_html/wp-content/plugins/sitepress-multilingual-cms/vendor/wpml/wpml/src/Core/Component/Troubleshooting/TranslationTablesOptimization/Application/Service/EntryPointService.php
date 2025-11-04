<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service\MigrationStatus\MigrationStatusService;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\Factory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState\Factory as PreviousStateFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\Compress\Factory as CompressFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\CompressFix\Factory as CompressFixFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\RemoveOld\Factory as RemoveOldFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationPackageColumnInterface;

final class EntryPointService {

  /** @var PreviousStateFactory */
  private $previousStateFactory;

  /** @var CompressFactory */
  private $compressFactory;

  /** @var RemoveOldFactory */
  private $removeOldFactory;

  /** @var TranslationPackageColumnInterface */
  private $translationStatusSchemaManager;

  /** @var MigrationStatusService */
  private $migrationStatusService;

  /** @var CompressFixFactory */
  private $compressFixFactory;


  public function __construct(
    PreviousStateFactory $previousStateFactory,
    CompressFactory $compressFactory,
    RemoveOldFactory $removeOldFactory,
    TranslationPackageColumnInterface $translationStatusSchemaManager,
    MigrationStatusService $migrationStatusService,
    CompressFixFactory $compressFixFactory
  ) {
    $this->previousStateFactory           = $previousStateFactory;
    $this->compressFactory                = $compressFactory;
    $this->removeOldFactory               = $removeOldFactory;
    $this->translationStatusSchemaManager = $translationStatusSchemaManager;
    $this->migrationStatusService         = $migrationStatusService;
    $this->compressFixFactory             = $compressFixFactory;
  }


  /**
   * @inheritDoct
   */
  public function run( string $migrationToRun, bool $isInitialRequest = false ): int {
    switch ( $migrationToRun ) {
      case 'previous-state':
        return $this->runPreviousStateMigration( $isInitialRequest );

      case 'translation-elements':
        return $this->runTranslationElementsMigration( $isInitialRequest );

      case 'truncate-translation-package':
        $this->runTruncateTranslationPackage();
        break;
    }

    return 0;
  }


  private function runPreviousStateMigration( bool $isInitialRequest ): int {
    $migrationStatus = $this->migrationStatusService->getMigrationStatus();
    if ( $migrationStatus->isPrevStateCompleted() ) {
      return 0;
    }

    return $this->runMigration(
      $this->previousStateFactory,
      $isInitialRequest
    );
  }


  private function runTranslationElementsMigration( bool $isInitialRequest ): int {
    $migrationStatus = $this->migrationStatusService->getMigrationStatus();
    if ( ! $migrationStatus->isObsoleteTranslationElementsRemovalCompleted() ) {
      return $this->runObsoleteTranslationElementsRemovalMigration( $isInitialRequest );
    } elseif ( ! $migrationStatus->isTranslationElementsCompressionCompleted() ) {
      return $this->runTranslationElementsCompressionMigration( $isInitialRequest );
    } elseif ( ! $migrationStatus->isTranslationElementsCompressionFixedCompleted() ) {
      return $this->runTranslationElementsCompressionFixMigration( $isInitialRequest );
    }

    return 0;
  }


  private function runObsoleteTranslationElementsRemovalMigration( bool $isInitialRequest ): int {
    $compressMigrationService = new MigrateDataService( $this->compressFactory );

    // Initialize compression migration if this is the initial request
    if ( $isInitialRequest ) {
      // JS script combines both obsolete translation elements removal and compression into one request families.
      // It sends only one first request with $isInitialRequest = true.
      // So we need to init both migrations.
      $compressMigrationService->initProcessAndGetTotalElements();
    }

    // Run the removal migration using the helper method
    $remainingRecords = $this->runMigration(
      $this->removeOldFactory,
      $isInitialRequest
    );

    // Return the sum of remaining records from both migrations
    return $remainingRecords + $compressMigrationService->countRemaining();
  }


  private function runTranslationElementsCompressionMigration( bool $isInitialRequest ): int {
    return $this->runMigration(
      $this->compressFactory,
      $isInitialRequest
    );
  }


  private function runTranslationElementsCompressionFixMigration( bool $isInitialRequest ): int {
    return $this->runMigration(
      $this->compressFixFactory,
      $isInitialRequest
    );
  }


  /**
   * Runs the truncate translation package migration if conditions are met
   *
   * @return void
   */
  private function runTruncateTranslationPackage() {
    $migrationStatus = $this->migrationStatusService->getMigrationStatus();
    if (
      $migrationStatus->isPrevStateCompleted() &&
      $migrationStatus->areTranslationElementsCompleted() &&
      ! $migrationStatus->isTranslationPackageCompleted()
    ) {
      $this->translationStatusSchemaManager->truncate();
      $this->migrationStatusService->markTranslationPackageCompleted();
    }
  }


  /**
   * Common method to run a migration process with a specific factory
   *
   * @param Factory $factory The factory to use for the migration
   * @param bool    $isInitialRequest Whether this is the initial request
   *
   * @return int Number of remaining records
   */
  private function runMigration( Factory $factory, bool $isInitialRequest ): int {
    $migrateDataService = new MigrateDataService( $factory );

    if ( $isInitialRequest ) {
      $remainingRecords = $migrateDataService->initProcessAndGetTotalElements();
    } else {
      $migrateDataService->run( 1000 );
      $remainingRecords = $migrateDataService->countRemaining();
    }

    if ( $remainingRecords === 0 ) {
      $migrateDataService->finalize();
    }

    return $remainingRecords;
  }


}
