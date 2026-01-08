<?php

namespace WPML\Core\Component\Translation\Domain\PreviousState;

use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;

/**
 * @phpstan-type PreviousStateData array{
 *     status?: string,
 *     translator_id?: int|string,
 *     needs_update?: bool|int,
 *     md5?: string,
 *     translation_service?: string,
 *     timestamp?: string,
 *     links_fixed?: bool|int
 *  }
 */
class PreviousState {

  /** @var TranslationStatus */
  private $status;

  /** @var int */
  private $translatorId;

  /** @var bool */
  private $needsUpdate;

  /** @var string */
  private $md5;

  /** @var string */
  private $translationService;

  /** @var string */
  private $timestamp;

  /** @var bool */
  private $linksFixed;


  public function __construct(
    TranslationStatus $status,
    int $translatorId,
    bool $needsUpdate,
    string $md5,
    string $translationService,
    string $timestamp,
    bool $linksFixed
  ) {
    $this->status             = $status;
    $this->translatorId       = $translatorId;
    $this->needsUpdate        = $needsUpdate;
    $this->md5                = $md5;
    $this->translationService = $translationService;
    $this->timestamp          = $timestamp;
    $this->linksFixed         = $linksFixed;
  }


  public function getStatus(): TranslationStatus {
    return $this->status;
  }


  public function getTranslatorId(): int {
    return $this->translatorId;
  }


  public function getNeedsUpdate(): bool {
    return $this->needsUpdate;
  }


  public function getMd5(): string {
    return $this->md5;
  }


  public function getTranslationService(): string {
    return $this->translationService;
  }


  public function getTimestamp(): string {
    return $this->timestamp;
  }


  public function getLinksFixed(): bool {
    return $this->linksFixed;
  }


  /**
   * @return array{
   *   status: int,
   *   translator_id: int,
   *   needs_update: bool,
   *   md5: string,
   *   translation_service: string,
   *   timestamp: int|string,
   *   links_fixed: bool
   * }
   */
  public function toArray(): array {
    return [
      'status'              => $this->status->get(),
      'translator_id'       => $this->translatorId,
      'needs_update'        => $this->needsUpdate,
      'md5'                 => $this->md5,
      'translation_service' => $this->translationService,
      'timestamp'           => $this->timestamp,
      'links_fixed'         => $this->linksFixed,
    ];

  }


  /**
   * @param PreviousStateData $data
   *
   * @return self
   */
  public static function fromArray( array $data ): self {
    $data = self::getDataWithDefaults( $data );

    return new PreviousState(
      new TranslationStatus( $data['status'] ),
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
   *    status: int,
   *    translator_id: int,
   *    needs_update: bool,
   *    md5: string,
   *    translation_service: string,
   *    timestamp: string,
   *    links_fixed: bool
   * }
   */
  private static function getDataWithDefaults( array $data ): array {
    return [
      'status'              => (int) ( $data['status'] ?? TranslationStatus::COMPLETE ),
      'translator_id'       => (int) ( $data['translator_id'] ?? 0 ),
      'needs_update'        => (bool) ( $data['needs_update'] ?? false ),
      'md5'                 => $data['md5'] ?? '',
      'translation_service' => $data['translation_service'] ?? '',
      'timestamp'           => $data['timestamp'] ?? '0',
      'links_fixed'         => (bool) ( $data['links_fixed'] ?? false ),
    ];
  }


}
