<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\PreliminaryConditionQueryInterface;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;

/**
 * WordPress implementation of the PreliminaryConditionQueryInterface.
 */
class PreliminaryConditionQuery implements PreliminaryConditionQueryInterface {

  /** @phpstan-var QueryHandlerInterface<int, int|null> */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPrepare;


  /**
   * @phpstan-param QueryHandlerInterface<int, int|null> $queryHandler
   * @param QueryPrepareInterface $queryPrepare
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare
  ) {
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
  }


  /**
   * {@inheritdoc}
   */
  public function hasNonNullTranslationPackages(): bool {
    $table = $this->queryPrepare->prefix() . 'icl_translation_status';
    $query = "SELECT 1 FROM {$table} WHERE translation_package IS NOT NULL LIMIT 1";

    try {
      $result = $this->queryHandler->querySingle( $query );
      return $result !== null;
    } catch ( \Throwable $e ) {
      // If query fails, assume there are no non-null values
      return false;
    }
  }


}
