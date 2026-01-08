<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatus;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatusStorageInterface;
use WPML\Core\Port\Persistence\DatabaseWriteInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;
use function WPML\PHP\Logger\error;

/**
 * I don't use built-in WordPress functions like get_option or update_option because of the problem with caching
 * in parallel AJAX requests. I want to guarantee that we directly retrieve data
 * from the database and that the data is not cached.
 */
final class MigrationStatusStorage implements MigrationStatusStorageInterface {
  const OPTION_NAME = 'wpml_translation_tables_optimization_status';

  /** @var QueryHandlerInterface<int, string> */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPrepare;

  /** @var DatabaseWriteInterface */
  private $dbWriter;


  /**
   * @param QueryHandlerInterface<int, string> $queryHandler
   * @param QueryPrepareInterface              $queryPrepare
   * @param DatabaseWriteInterface             $dbWriter
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare,
    DatabaseWriteInterface $dbWriter
  ) {
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
    $this->dbWriter     = $dbWriter;
  }


  public function read(): MigrationStatus {
    $data = [];

    try {
      $query = $this->queryPrepare->prepare(
        "SELECT option_value FROM {$this->queryPrepare->prefix()}options WHERE option_name = %s LIMIT 1",
        self::OPTION_NAME
      );

      $optionValue = $this->queryHandler->querySingle( $query );

      if ( $optionValue ) {
        $data = \maybe_unserialize( $optionValue );

        if ( ! is_array( $data ) ) {
          $data = [];
        }
      }
    } catch ( DatabaseErrorException $e ) {
      error( 'Could not read migration status: ' . $e->getMessage() );
    }

    return new MigrationStatus(
      (bool) ( $data['prev_state_completed'] ?? false ),
      (bool) ( $data['translation_package_completed'] ?? false ),
      (bool) ( $data['obsolete_translation_elements_removal_completed'] ?? false ),
      (bool) ( $data['translation_elements_compression_completed'] ?? false ),
      (bool) ( $data['translation_elements_compression_fixed_completed'] ?? false )
    );
  }


  public function write( MigrationStatus $migrationStatus ) {
    $data = [
      'prev_state_completed'                            => $migrationStatus->isPrevStateCompleted(),
      'translation_package_completed'                   => $migrationStatus->isTranslationPackageCompleted(),
      'obsolete_translation_elements_removal_completed' =>
        $migrationStatus->isObsoleteTranslationElementsRemovalCompleted(),
      'translation_elements_compression_completed'      =>
        $migrationStatus->isTranslationElementsCompressionCompleted(),
      'translation_elements_compression_fixed_completed' =>
        $migrationStatus->isTranslationElementsCompressionFixedCompleted(),
    ];

    $serialized_data = maybe_serialize( $data );

    try {
      $query = $this->queryPrepare->prepare(
        "SELECT option_value FROM {$this->queryPrepare->prefix()}options WHERE option_name = %s LIMIT 1",
        self::OPTION_NAME
      );

      $exists = $this->queryHandler->querySingle( $query );

      if ( $exists ) {
        $this->dbWriter->update(
          'options',
          [ 'option_value' => $serialized_data ],
          [ 'option_name' => self::OPTION_NAME ]
        );
      } else {
        $this->dbWriter->insert(
          'options',
          [
            'option_name'  => self::OPTION_NAME,
            'option_value' => $serialized_data,
            'autoload'     => 'no'
          ]
        );
      }
    } catch ( DatabaseErrorException $e ) {
      error( 'Could not write migration status: ' . $e->getMessage() );
    }
  }


}
