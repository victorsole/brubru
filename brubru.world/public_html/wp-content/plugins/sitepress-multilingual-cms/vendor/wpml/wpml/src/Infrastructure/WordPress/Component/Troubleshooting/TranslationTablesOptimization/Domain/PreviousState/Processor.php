<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousState;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateRepositoryInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\ProcessorInterface;
use WPML\PHP\Exception\InvalidItemIdException;

/**
 * @implements ProcessorInterface<array{translationId: int, previousState: string}>
 */
class Processor implements ProcessorInterface {

  /** @var PreviousStateRepositoryInterface */
  private $repository;

  /** @var DataCompressInterface */
  private $dataCompress;


  public function __construct(
    PreviousStateRepositoryInterface $repository,
    DataCompressInterface $dataCompress
  ) {
    $this->repository   = $repository;
    $this->dataCompress = $dataCompress;
  }


  /**
   * @param array<array{translationId: int, previousState: string}> $records
   *
   * @return int[]
   */
  public function process( array $records ): array {
    $processed = [];

    foreach ( $records as $record ) {
      $data = $this->dataCompress->decompress( $record['previousState'] );
      if ( empty( $data ) ) {
        // The data are corrupted, but we mark it as processed, so we will not ask for it again.
        $processed[] = $record['translationId'];
        continue;
      }

      $previousState = PreviousState::fromArray( $data );
      try {
        $this->repository->update( $record['translationId'], $previousState );
      // @phpcs:ignore Generic.CodeAnalysis.EmptyStatement.DetectedCatch
      } catch ( InvalidItemIdException $e ) {
      } finally {
        // Even if it fails, we mark it as processed, so we will not ask for it again.
        $processed[] = $record['translationId'];
      }
    }

    return $processed;
  }


}
