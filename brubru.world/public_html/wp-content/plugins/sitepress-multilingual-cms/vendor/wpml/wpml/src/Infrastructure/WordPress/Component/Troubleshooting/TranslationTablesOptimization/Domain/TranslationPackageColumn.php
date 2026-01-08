<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationPackageColumnInterface;
use WPML\Core\Port\Persistence\DatabaseAlterInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\PHP\Exception\InvalidArgumentException;

class TranslationPackageColumn implements TranslationPackageColumnInterface {
  const TABLE_NAME = 'icl_translation_status';
  const PACKAGE_COLUMN = 'translation_package';

  /** @var DatabaseAlterInterface */
  private $databaseAlter;


  public function __construct( DatabaseAlterInterface $databaseAlter ) {
    $this->databaseAlter      = $databaseAlter;
  }


  public function truncate(): bool {
    try {
      $this->databaseAlter->truncateColumn(
        self::TABLE_NAME,
        self::PACKAGE_COLUMN
      );

      return true;
    } catch ( DatabaseErrorException $e ) {
      return false;
    } catch ( InvalidArgumentException $e ) {
      return false;
    }
  }


}
