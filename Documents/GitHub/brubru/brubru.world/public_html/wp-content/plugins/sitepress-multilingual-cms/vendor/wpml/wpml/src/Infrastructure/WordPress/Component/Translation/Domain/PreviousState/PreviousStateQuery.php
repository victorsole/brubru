<?php

namespace WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousState;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateQueryInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;
use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;

/**
 *
 * @phpstan-type PreviousStateData array{
 *    status?: string,
 *    translator_id?: int|string,
 *    needs_update?: bool|int,
 *    md5?: string,
 *    translation_service?: string,
 *    timestamp?: string,
 *    links_fixed?: bool|int
 * }
 */
class PreviousStateQuery implements PreviousStateQueryInterface {

  /** @phpstan-var QueryHandlerInterface<int, string|null> $queryHandler */
  private $queryHandler;

  /** @var QueryPrepareInterface $queryPrepare */
  private $queryPrepare;

  /** @var DataCompressInterface */
  private $dataCompress;


  /**
   * @phpstan-param QueryHandlerInterface<int, string|null> $queryHandler
   *
   * @param QueryPrepareInterface                           $queryPrepare
   * @param DataCompressInterface                           $dataCompress
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare,
    DataCompressInterface $dataCompress
  ) {
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
    $this->dataCompress = $dataCompress;
  }


  /**
   * Get previous state by job ID
   *
   * @param int $jobId
   *
   * @return PreviousState|null
   */
  public function getByJobId( int $jobId ) {
    $query = "
            SELECT ts._prevstate
            FROM {$this->queryPrepare->prefix()}icl_translation_status ts
            INNER JOIN {$this->queryPrepare->prefix()}icl_translate_job tj 
                ON tj.rid = ts.rid
            WHERE tj.job_id = %d
            LIMIT 1
        ";

    try {
      $result = $this->queryHandler->querySingle(
        $this->queryPrepare->prepare( $query, $jobId )
      );

      return $this->createDomainFromSerializedData( $result );
    } catch ( DatabaseErrorException $e ) {
      return null;
    }
  }


  /**
   * Get previous state by RID
   *
   * @param int $rid
   *
   * @return PreviousState|null
   */
  public function getByRID( int $rid ) {
    $query = "
            SELECT _prevstate
            FROM {$this->queryPrepare->prefix()}icl_translation_status
            WHERE rid = %d
            LIMIT 1
        ";

    try {
      $result = $this->queryHandler->querySingle(
        $this->queryPrepare->prepare( $query, $rid )
      );

      return $this->createDomainFromSerializedData( $result );
    } catch ( DatabaseErrorException $e ) {
      return null;
    }
  }


  /**
   * Get previous state by translation ID
   *
   * @param int $translationId
   *
   * @return PreviousState|null
   */
  public function getByTranslationId( int $translationId ) {
    $query = "
            SELECT _prevstate
            FROM {$this->queryPrepare->prefix()}icl_translation_status
            WHERE translation_id = %d
            LIMIT 1
        ";

    try {
      $result = $this->queryHandler->querySingle(
        $this->queryPrepare->prepare( $query, $translationId )
      );

      return $this->createDomainFromSerializedData( $result );
    } catch ( DatabaseErrorException $e ) {
      return null;
    }
  }


  /**
   * Creates a PreviousState from serialized data
   *
   * @param string|null $compressedData
   *
   * @return PreviousState|null
   */
  private function createDomainFromSerializedData( $compressedData ) {
    if ( ! $compressedData ) {
      return null;
    }

    $data = $this->dataCompress->decompress( $compressedData );
    if ( empty( $data ) ) {
      return null;
    }

    $data = $this->getDataWithDefaults( $data );

    return new PreviousState(
      new TranslationStatus( (int) $data['status'] ),
      $data['translator_id'],
      $data['needs_update'],
      $data['md5'],
      $data['translation_service'],
      $data['timestamp'],
      $data['links_fixed']
    );
  }


  /**
   * Ensures all required fields are present with default values
   *
   * @phpstan-param PreviousStateData $data
   *
   * @return array{
   *    status: string,
   *    translator_id: int,
   *    needs_update: bool,
   *    md5: string,
   *    translation_service: string,
   *    timestamp: string,
   *    links_fixed: bool
   * }
   */
  private function getDataWithDefaults( array $data ): array {
    return [
      'status'              => $data['status'] ?? '',
      'translator_id'       => (int) ( $data['translator_id'] ?? 0 ),
      'needs_update'        => (bool) ( $data['needs_update'] ?? false ),
      'md5'                 => $data['md5'] ?? '',
      'translation_service' => $data['translation_service'] ?? '',
      'timestamp'           => $data['timestamp'] ?? '0',
      'links_fixed'         => (bool) ( $data['links_fixed'] ?? false ),
    ];
  }


}
