<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service\MigrationStatus;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatus;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatusStorageInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\PreliminaryConditionQueryInterface;

class MigrationStatusService {

  /** @var MigrationStatusStorageInterface */
  private $storage;

  /** @var PreliminaryConditionQueryInterface */
  private $preliminaryConditionQuery;


  public function __construct(
    MigrationStatusStorageInterface $storage,
    PreliminaryConditionQueryInterface $preliminaryConditionQuery
  ) {
    $this->storage                   = $storage;
    $this->preliminaryConditionQuery = $preliminaryConditionQuery;
  }


  public function getMigrationStatus(): MigrationStatusDTO {
    $status = $this->storage->read();

    if ( $status->isTotalProcessCompleted() ) {
      return MigrationStatusDTO::from( $status );
    }

    /**
     * If a user installed the WPML plugin already containing optimization fixes,
     * we can mark the migration as completed immediately. The easiest way to recognize such a case is
     * to check if any records in wp_icl_translation_status have non-null values in translation_package column.
     */
    if ( ! $this->preliminaryConditionQuery->hasNonNullTranslationPackages() ) {
      $status = MigrationStatus::createCompletedStatus();
      $this->storage->write( $status );
    }

    return MigrationStatusDTO::from( $status );
  }


  /**
   * @return void
   */
  public function markPrevStateCompleted() {
    $status = $this->storage->read();
    $status->setPrevStateCompleted( true );
    $this->storage->write( $status );
  }


  /**
   * @return void
   */
  public function markTranslationPackageCompleted() {
    $status = $this->storage->read();
    $status->setTranslationPackageCompleted( true );
    $this->storage->write( $status );
  }


  /**
   * @return void
   */
  public function markObsoleteTranslationElementsRemovalCompleted() {
    $status = $this->storage->read();
    $status->setObsoleteTranslationElementsRemovalCompleted( true );
    $this->storage->write( $status );
  }


  /**
   * @return void
   */
  public function markTranslationElementsCompressionCompleted() {
    $status = $this->storage->read();
    $status->setTranslationElementsCompressionCompleted( true );
    $this->storage->write( $status );
  }


  /**
   * @return void
   */
  public function markTranslationElementsCompressionFixedCompleted() {
    $status = $this->storage->read();
    $status->setTranslationElementsCompressionFixedCompleted( true );
    $this->storage->write( $status );
  }


}
