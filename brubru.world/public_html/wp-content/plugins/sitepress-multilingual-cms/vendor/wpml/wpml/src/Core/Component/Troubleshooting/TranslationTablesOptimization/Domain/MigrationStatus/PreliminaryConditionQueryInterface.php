<?php

namespace WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus;

/**
 * Interface for querying preliminary conditions for migration status.
 */
interface PreliminaryConditionQueryInterface {


  /**
   * Checks if there are any records with non-null translation_package values in the database.
   *
   * @return bool True if there are records with non-null translation_package values, false otherwise.
   */
  public function hasNonNullTranslationPackages(): bool;


}
